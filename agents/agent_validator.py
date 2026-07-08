# Autor: Selma Elezovic
# Validator-Agent: prüft die finale Antwort auf Halluzinationen und gibt einen
# Confidence-Score (0.0–1.0) zurück. Bei SQL-Daten wird direkt gegen die Rohdaten
# verglichen, bei faktischen Aussagen wird zusätzlich ein RAG-Fact-Check durchgeführt.

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from .shared import llm, PROMPTS, GraphState
from .agent_rag import _retrieve

# Bekannte Fußball-Entitäten — wenn keine davon in Frage/Antwort vorkommt,
# behandeln wir die Anfrage als out-of-domain und deckeln die Confidence.
_SOCCER_ENTITIES = [
    "bundesliga", "champions league", "fc ", " fc", "borussia", "bayern", "dortmund",
    "schalke", "leverkusen", "gladbach", "köln", "frankfurt", "stuttgart", "freiburg",
    "wolfsburg", "bochum", "augsburg", "berlin", "hoffenheim", "mainz", "bremen",
    "juventus", "real madrid", "barcelona", "arsenal", "chelsea", "liverpool",
    "manchester", "milan", "inter", "atletico", "paris", "juventus",
    "bundesliga", "serie a", "la liga", "premier league", "ligue 1",
    "spieler", "trainer", "tore", "xg", "schüsse", "pässe", "pressing",
    "meisterschaft", "pokal", "titel", "abstieg", "aufstieg", "tabelle",
    "stadion", "verein", "fußball", "fussball", "soccer", "weltmeister",
    "dfb", "fifa", "uefa", "cl-", "cl ", "em", "wm",
]

# Schlüsselbegriffe die auf faktische, prüfbare Aussagen hinweisen.
# Wird genutzt um zu entscheiden ob ein RAG-Abruf sinnvoll ist.
_FACT_INDICATORS = [
    "gegründet", "titel", "gewonnen", "geboren", "gestorben", "stadion",
    "champions", "meisterschaft", "rekord", "trainer", "gründer", "geschichte",
    "wurde", "hat", "ist", "sind", "war", "waren",
]

# Regex für Zahlen: trifft Jahreszahlen (4 Stellen) und kurze Zahlen (1–3 Stellen)
_NUMBER_PATTERN = re.compile(r'\b\d{4}\b|\b\d{1,3}\b')


def _needs_fact_check(answer: str) -> bool:
    """Heuristik: enthält die Antwort faktische Aussagen die überprüft werden sollten?

    Gibt True zurück wenn mindestens ein Wort aus _FACT_INDICATORS in der Antwort vorkommt.
    Bei True wird zusätzlich ein RAG-Abruf angestoßen um die Fakten zu verifizieren.
    """
    answer_lower = answer.lower()
    return any(word in answer_lower for word in _FACT_INDICATORS)


def _is_out_of_domain(question: str, answer: str) -> bool:
    """Prüft ob Frage/Antwort keinen Fußball-Bezug haben.

    Gibt True zurück wenn kein einziger Eintrag aus _SOCCER_ENTITIES in der
    kombinierten Frage+Antwort vorkommt. In diesem Fall wird die Confidence
    auf maximal 0.3 gedeckelt.
    """
    combined = (question + " " + answer).lower()
    return not any(ent in combined for ent in _SOCCER_ENTITIES)


def _extract_key_terms(text: str) -> list[str]:
    """Extrahiert Schlüsselbegriffe aus Frage/Antwort für den Quellenvergleich.

    Gibt Wörter mit >= 4 Zeichen zurück (filtert Füllwörter heraus),
    plus alle Zahlenfolgen (Jahreszahlen, Titelanzahlen, Statistikwerte).
    """
    words = re.findall(r'\b\w+\b', text.lower())
    # Kurzwörter (Artikel, Präpositionen etc.) herausfiltern
    meaningful = [w for w in words if len(w) >= 4]
    numbers = _NUMBER_PATTERN.findall(text)
    return list(set(meaningful + numbers))


def _entities_in_context(question: str, answer: str, context: str) -> bool:
    """Prüft ob zentrale Entitäten aus Frage/Antwort im Quellenkontext vorkommen.

    Gibt True zurück wenn mindestens 2 Schlüsselbegriffe aus Frage oder Antwort
    im Kontext gefunden werden — verhindert zu strenge Decklung bei breiten Fragen.
    """
    context_lower = context.lower()
    terms = _extract_key_terms(question + " " + answer)
    # Mindestens 2 Begriffe müssen im Kontext vorkommen
    hits = sum(1 for t in terms if t in context_lower)
    return hits >= 2


def _contains_numbers(text: str) -> bool:
    """True wenn die Antwort konkrete Zahlen oder Jahreszahlen enthält."""
    return bool(_NUMBER_PATTERN.search(text))


def _numbers_in_context(answer: str, context: str) -> bool:
    """Prüft ob die Zahlen aus der Antwort auch im Quellenkontext vorkommen.

    Gibt True zurück wenn keine Zahlen in der Antwort enthalten sind (kein Konflikt),
    oder wenn mindestens eine der Zahlen im Kontext auftaucht.
    """
    answer_numbers = _NUMBER_PATTERN.findall(answer)
    if not answer_numbers:
        # Keine Zahlen → kein Zahlenwiderspruch möglich
        return True
    context_lower = context.lower()
    return any(num in context_lower for num in answer_numbers)


def validator_agent(state: GraphState) -> GraphState:
    """Prüft die Antwort auf Halluzinationen und gibt einen Confidence-Score zurück.

    Ablauf in 5 Stufen:
    1. SQL-Ergebnis leer oder fehlerhaft → confidence 0.2 (kein Datenbankbefund)
    2. SQL-Daten vorhanden → LLM-Vergleich der Antwort gegen die Rohdaten
    3. Faktische Antwort ohne SQL → RAG-Retrieval mit Frage+Antwort als Query (top_k=10)
    4. Nachträgliche Confidence-Caps basierend auf Entitäts- und Zahlenpräsenz
    5. Out-of-domain → confidence wird auf maximal 0.3 gedrückt
    """
    system_prompt = PROMPTS["validator"]["system"]
    answer = state["answer"]
    question = state["question"]

    # ── 1. SQL-Kurzschluss ──────────────────────────────────────────────────
    # Wenn SQL ausgeführt wurde aber kein Ergebnis zurückgekommen ist oder ein
    # Fehler aufgetreten ist, kann nichts verifiziert werden → niedrige Confidence
    sql_result = state.get("sql_result", "")
    sql_empty = sql_result in ("", "[]", None) or "SQL-Fehler" in (sql_result or "")

    if sql_result and sql_empty:
        return {**state, "answer": answer, "confidence": 0.2, "active_agent": "validator"}

    # ── 2. Quellenkontext aufbauen ───────────────────────────────────────────
    # Entweder aus SQL-Daten oder aus RAG-Retrieval — niemals beides gleichzeitig
    source_context = ""
    source_label = ""

    if sql_result and not sql_empty:
        # SQL-Rohdaten als primäre Quelle nutzen; auf 2000 Zeichen kürzen
        # um den Kontext des LLM-Prompts nicht zu sprengen
        truncated = sql_result[:2000] + ("..." if len(sql_result) > 2000 else "")
        source_context = truncated
        source_label = "Datenbank"
    elif _needs_fact_check(answer):
        # Frage + Antwort als Query für bessere Chunk-Treffsicherheit beim RAG
        retrieval_query = f"{question} {answer}"
        retrieved = _retrieve(retrieval_query, top_k=10)
        if retrieved and "Keine relevanten" not in retrieved:
            source_context = retrieved
            source_label = "Wissensdatenbank (Wikipedia)"

    # ── 3. LLM-Prompt aufbauen ───────────────────────────────────────────────
    # Je nachdem ob Quelldaten vorhanden sind, erhält das LLM unterschiedliche Anweisungen
    if source_context:
        source_block = f"""
VERIFIZIERTE QUELLDATEN ({source_label}):
{source_context}

AUFGABE: Prüfe die Antwort anhand der Quelldaten.
- Vergleiche alle prüfbaren Fakten: Zahlen, Daten, Vereinsnamen, Spielernamen,
  Stadien, Trainer, Titel, Tabellenplätze, xG-Werte.
- Wenn der konkrete Fakt oder die zentrale Entität NICHT in den Quelldaten vorkommt:
  gilt der Fakt als NICHT VERIFIZIERBAR → Score maximal 0.4.
- Wenn Zahlen/Daten in der Antwort aber nicht in den Quellen vorkommen → Score maximal 0.3.
- Stimmen die zentralen Fakten überein → Score 0.8–1.0.
- Verwende AUSSCHLIESSLICH die Quelldaten — kein eigenes Modellwissen."""
    else:
        # Kein Quellenkontext: LLM soll keine eigenen Fakten einbringen
        source_block = """
KEINE QUELLDATEN VERFÜGBAR.
- Enthält die Antwort konkrete Fakten (Zahlen, Daten, Namen)? → Score maximal 0.4.
- Ist die Antwort inhaltslos oder am Thema vorbei? → Score 0.0–0.2.
- Verwende kein eigenes Modellwissen zur Bewertung."""

    # Vollständiger User-Prompt mit Frage, Antwort und Verifikationsanweisung
    user_content = f"""Frage: {question}

Antwort des Agenten:
{answer}
{source_block}

Antworte ausschließlich mit einem JSON-Objekt:
{{"answer": "<korrigierte oder originale Antwort>", "confidence": <0.0–1.0>, "reason": "<kurze Begründung>"}}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    response = llm.invoke(messages)
    raw = response.content.strip()

    # LLM-Antwort parsen — bei Fehler auf sichere Standardwerte zurückfallen
    try:
        parsed = json.loads(raw)
        validated_answer = parsed.get("answer", answer)
        confidence = float(parsed.get("confidence", 0.5))
        # Sicherstellen dass der Score im gültigen Bereich 0.0–1.0 liegt
        confidence = max(0.0, min(1.0, confidence))
    except (json.JSONDecodeError, ValueError, KeyError):
        # Ungültiges JSON oder fehlende Felder → ursprüngliche Antwort behalten
        validated_answer = answer
        confidence = 0.5

    # ── 4. Nachträgliche Confidence-Caps ────────────────────────────────────
    # Diese Caps überschreiben das LLM-Urteil wenn objektiv prüfbare Signale
    # auf ein hohes Halluzinationsrisiko hinweisen.

    # Out-of-domain: kein Fußball-Bezug erkennbar → hard cap bei 0.3
    if _is_out_of_domain(question, answer):
        confidence = min(confidence, 0.3)

    # Inhaltsleere oder Off-topic-Antwort: Agent hat offensichtlich keine Daten gefunden
    empty_indicators = ["keine daten", "leider", "kann ich nicht", "nicht gefunden", "keine informationen"]
    if any(ind in answer.lower() for ind in empty_indicators):
        confidence = min(confidence, 0.2)

    # Keine Quelle vorhanden aber faktische Aussagen → maximal 0.4
    # (LLM hat keine Möglichkeit die Fakten zu prüfen)
    if not source_context and _needs_fact_check(answer):
        confidence = min(confidence, 0.4)

    # Quelle vorhanden, aber zentrale Entitäten fehlen im Kontext → maximal 0.4
    # (Quelle passt nicht zur Frage — wahrscheinlich falscher Chunk abgerufen)
    if source_context and not _entities_in_context(question, answer, source_context):
        confidence = min(confidence, 0.4)

    # Zahlen in Antwort aber nicht in Quelle → maximal 0.3
    # (Starkes Signal für Halluzination — Zahlen sind besonders leicht zu erfinden)
    if source_context and _contains_numbers(answer) and not _numbers_in_context(answer, source_context):
        confidence = min(confidence, 0.3)

    return {**state, "answer": validated_answer, "confidence": confidence, "active_agent": "validator"}


if __name__ == "__main__":
    # Manuelle Smoke-Tests direkt aus dem Modul heraus ausführbar
    test_cases = [
        {
            "label": "Korrekte Antwort",
            "question": "Wann wurde Bayern München gegründet?",
            "answer": "Bayern München wurde am 27. Februar 1900 gegründet.",
        },
        {
            "label": "Halluzination (falsches Datum)",
            "question": "Wann wurde Bayern München gegründet?",
            "answer": "Bayern München wurde 1963 gegründet.",
        },
        {
            "label": "Inhaltsleere Antwort",
            "question": "Wer steht auf Platz 1 der Bundesliga?",
            "answer": "Ich habe leider keine Daten dazu gefunden.",
        },
        {
            "label": "Thema verfehlt",
            "question": "Wie viele Tore hat Robert Lewandowski erzielt?",
            "answer": "Die Bundesliga hat 18 Vereine und spielt im Ligasystem.",
        },
    ]

    # Basis-State ohne Datenbankbezug (reiner RAG/Heuristik-Pfad)
    empty_base = {
        "route": "", "route_reason": "", "sql": "", "sql_result": "",
        "sub_answers": [], "steps": [], "active_agent": "", "confidence": 0.0,
    }

    print("Validator Test\n" + "=" * 60)
    for tc in test_cases:
        state = {**empty_base, "question": tc["question"], "answer": tc["answer"]}
        result = validator_agent(state)
        # Balkendiagramm aus Block-Zeichen (20 Schritte = 5% pro Schritt)
        bar = int(result["confidence"] * 20) * "█" + int((1 - result["confidence"]) * 20) * "░"
        changed = result["answer"].strip() != tc["answer"].strip()
        print(f"\n[{tc['label']}]")
        print(f"  Frage:      {tc['question']}")
        print(f"  Original:   {tc['answer']}")
        print(f"  Validiert:  {result['answer']}")
        print(f"  Korrigiert: {'ja' if changed else 'nein'}")
        print(f"  Confidence: {bar} {result['confidence']:.0%}")
