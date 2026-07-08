# Autor: Selma Elezovic
"""
End-to-End Evaluation — Multi-Agenten-Pipeline
================================================
Testet die vollständige LangGraph-Pipeline:
  Frage → Question Rewriter → Supervisor → Agent(en) → Aggregator → Validator → Antwort

Metriken:
- Route Accuracy:                    Erwarteter Agent wurde aufgerufen
- Functional End-to-End Pass Rate:   Route + Keywords (Inhalt korrekt, unabhängig von Confidence)
- Strict Confidence-Gated Pass Rate: Route + Keywords + Confidence >= 0.4
- Confidence Pass Rate:              Anteil Tests mit Confidence >= 0.4
- Average Confidence:                Durchschnittlicher Validator-Score

Aufruf: python data/evaluate_end_to_end.py
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.orchestrator import app

# ─────────────────────────────────────────────
# TESTDATENSATZ — 13 Fragen
# expected_agent:    welcher Agent MUSS in steps auftauchen (None = egal)
# expected_keywords: mindestens einer muss in der Antwort vorkommen
# ─────────────────────────────────────────────
TEST_CASES = [
    # ── OpenLigaDB (Tabellen, Ergebnisse) ────────────────────────────────────
    # DB enthält Saison 2023/24, Spieltag 1–34. "Nächster Spieltag" existiert nicht.
    {
        "category": "openligadb",
        "question": "Welche Teams stehen in der Bundesliga-Tabelle auf den ersten drei Plätzen?",
        "expected_agent": "openligadb",
        "expected_keywords": ["leverkusen", "stuttgart", "bayern", "platz", "punkte"],
    },
    {
        "category": "openligadb",
        "question": "Wie hat Bayern München in der Saison 2023/24 abgeschnitten?",
        "expected_agent": "openligadb",
        "expected_keywords": ["Bayern", "sieg", "niederlage", "tor", "spiel", "punkte"],
    },
    {
        "category": "openligadb",
        "question": "Wie viele Punkte hat Bayer Leverkusen in der Saison 2023/24 geholt?",
        "expected_agent": "openligadb",
        "expected_keywords": ["leverkusen", "punkte", "90", "saison"],
    },

    # ── StatsBomb (xG, Schüsse, Spielphasen) ─────────────────────────────────
    # Verfügbare Teams: Leverkusen, Bochum, Darmstadt, Frankfurt, Freiburg, Hoffenheim, Union Berlin
    {
        "category": "statsbomb",
        "question": "Wie war die Chancenverwertung von Bayer Leverkusen laut xG-Daten?",
        "expected_agent": "statsbomb",
        "expected_keywords": ["xg", "leverkusen", "schuss", "tor", "chance"],
    },
    {
        "category": "statsbomb",
        "question": "Welche Mannschaft hatte gegen Bayer Leverkusen die meisten Schüsse?",
        "expected_agent": "statsbomb",
        "expected_keywords": ["schuss", "schüsse", "leverkusen", "spiel"],
    },
    {
        "category": "statsbomb",
        "question": "Welche Teams überperformen ihre erwarteten Tore in der Bundesliga 2023/24 am stärksten?",
        "expected_agent": "statsbomb",
        "expected_keywords": ["xg", "erwartet", "tore", "überperform", "effizienz", "team"],
    },

    # ── RAG (Vereinsgeschichte, Wikipedia-Wissen) ─────────────────────────────
    {
        "category": "rag",
        "question": "Wann wurde Bayern München gegründet?",
        "expected_agent": "rag",
        "expected_keywords": ["1900", "gegründet", "Bayern", "Februar"],
    },
    {
        "category": "rag",
        "question": "Welche Titel hat Juventus FC in seiner Geschichte gewonnen?",
        "expected_agent": "rag",
        "expected_keywords": ["Serie A", "serie a", "titel", "gewonnen", "Juventus", "Coppa"],
    },
    {
        "category": "rag",
        "question": "Was ist das Estadio Santiago Bernabéu?",
        "expected_agent": "rag",
        "expected_keywords": ["Bernabéu", "bernabeu", "Real Madrid", "stadion", "Madrid"],
    },

    # ── Combined (OpenLigaDB + StatsBomb) ────────────────────────────────────
    # Leverkusen ist in beiden Quellen vorhanden — ideal für Combined-Tests.
    {
        "category": "combined",
        "question": "Warum war Bayer Leverkusen 2023/24 so dominant — vergleiche Tabellenstand und xG-Werte?",
        "expected_agent": "combined",
        "expected_keywords": ["leverkusen", "tabelle", "xg", "punkte"],
    },
    {
        "category": "combined",
        "question": "Welche Teams stehen oben in der Bundesliga-Tabelle und haben gleichzeitig die besten xG-Werte?",
        "expected_agent": "combined",
        "expected_keywords": ["tabelle", "xg", "bundesliga", "punkte"],
    },

    # ── Out-of-domain / Fehlerfall ────────────────────────────────────────────
    {
        "category": "out_of_domain",
        "question": "Wer hat die Formel-1-WM 2023 gewonnen?",
        "expected_agent": None,
        "expected_keywords": ["nicht", "keine", "außerhalb", "domäne", "fußball", "verfügbar", "leider"],
    },
    {
        "category": "out_of_domain",
        "question": "Was weißt du über den Al-Hilal FC aus Saudi-Arabien?",
        "expected_agent": "rag",
        "expected_keywords": ["keine", "nicht", "wissensdatenbank", "informationen", "al-hilal", "saudi"],
    },
]

EMPTY_STATE = {
    "question": "", "chat_history": "", "route": "", "route_reason": "",
    "sql": "", "sql_result": "", "sub_answers": [], "steps": [],
    "active_agent": "", "answer": "", "confidence": 0.0,
}


def _keywords_found(answer: str, keywords: list[str]) -> list[str]:
    answer_lower = answer.lower()
    return [kw for kw in keywords if kw.lower() in answer_lower]


def _ood_passed(answer: str, confidence: float) -> bool:
    """Out-of-domain bestanden wenn Antwort Ablehnung signalisiert und Confidence <= 0.6."""
    rejection_words = ["nicht", "keine", "außerhalb", "domäne", "leider", "verfügbar", "wissensdatenbank"]
    return any(w in answer.lower() for w in rejection_words) and confidence <= 0.6


def _failure_reason(route_correct: bool, answer_ok: bool, confidence: float, category: str) -> str:
    if category == "out_of_domain":
        return ""
    if not route_correct:
        return "Routing failed"
    if not answer_ok:
        return "Answer content failed"
    if confidence < 0.4:
        return "Validator confidence too low"
    return ""


if __name__ == "__main__":
    print("End-to-End Evaluation — Pipeline startet...\n")
    print(f"{'Kategorie':<12} {'Erwartet':<12} {'Genutzt':<25} {'Conf':>5}  {'Status'}")
    print("-" * 75)

    results = []

    for tc in TEST_CASES:
        result = app.invoke({**EMPTY_STATE, "question": tc["question"]})

        used_agents   = result.get("steps", [])
        final_answer  = result.get("answer", "")
        confidence    = result.get("confidence", 0.0)

        route_correct = (tc["expected_agent"] is None) or (tc["expected_agent"] in used_agents)
        found_kws     = _keywords_found(final_answer, tc["expected_keywords"])
        answer_ok     = len(found_kws) >= 1  # mindestens 1 Keyword reicht
        conf_ok       = confidence >= 0.4

        if tc["category"] == "out_of_domain":
            # Out-of-domain: bestanden wenn System die Frage sauber ablehnt
            strict_passed     = _ood_passed(final_answer, confidence)
            functional_passed = strict_passed
        else:
            strict_passed     = route_correct and answer_ok and conf_ok
            functional_passed = route_correct and answer_ok

        reason = _failure_reason(route_correct, answer_ok, confidence, tc["category"])

        results.append({
            "category":         tc["category"],
            "question":         tc["question"],
            "expected_agent":   tc["expected_agent"] or "—",
            "used_agents":      ", ".join(used_agents) if used_agents else "—",
            "final_answer":     final_answer,
            "confidence":       confidence,
            "route_correct":    route_correct,
            "answer_ok":        answer_ok,
            "conf_ok":          conf_ok,
            "found_keywords":   found_kws,
            "strict_passed":    strict_passed,
            "functional_passed": functional_passed,
            "failure_reason":   reason,
        })

        status = "✓ PASS" if strict_passed else f"✗ {reason or 'FAIL'}"
        agents_str = ", ".join(used_agents)[:24] if used_agents else "—"
        print(f"{tc['category']:<12} {(tc['expected_agent'] or '—'):<12} {agents_str:<25} {confidence:>4.0%}  {status}")

    # ─────────────────────────────────────────────
    # METRIKEN
    # ─────────────────────────────────────────────
    total = len(results)
    # Out-of-domain-Fälle aus Routing/Keyword/Confidence-Metriken heraushalten,
    # da dort kein klar definierter erwarteter Agent oder Antwortinhalt existiert.
    non_ood = [r for r in results if r["category"] != "out_of_domain"]

    route_accuracy       = sum(r["route_correct"]    for r in non_ood) / len(non_ood) if non_ood else 0.0
    keyword_accuracy     = sum(r["answer_ok"]        for r in non_ood) / len(non_ood) if non_ood else 0.0
    conf_pass_rate       = sum(r["conf_ok"]          for r in non_ood) / len(non_ood) if non_ood else 0.0
    strict_pass_rate     = sum(r["strict_passed"]    for r in results) / total
    functional_pass_rate = sum(r["functional_passed"] for r in results) / total
    avg_conf             = sum(r["confidence"]       for r in results) / total

    print("\n" + "=" * 70)
    print("ERGEBNISSE")
    print("=" * 70)
    print(f"Tests gesamt:                    {total}")
    print()
    print(f"Route Accuracy:                  {route_accuracy:.1%}  — richtiger Agent aufgerufen")
    print(f"Answer Keyword Accuracy:         {keyword_accuracy:.1%}  — erwartete Keywords gefunden")
    print(f"Confidence Pass Rate:            {conf_pass_rate:.1%}  — Confidence >= 0.4")
    print(f"Strict End-to-End Pass Rate:     {strict_pass_rate:.1%}  — Route + Keywords + Confidence")
    print(f"Functional End-to-End Pass Rate: {functional_pass_rate:.1%}  — Route + Keywords")
    print(f"Average Confidence:              {avg_conf:.2f}")

    failures = [r for r in results if not r["strict_passed"]]
    if failures:
        print(f"\nFehlgeschlagene Tests ({len(failures)}):")
        for r in failures:
            print(f"\n  Frage:          {r['question'][:65]}")
            print(f"  Kategorie:      {r['category']}")
            print(f"  Fehlergrund:    {r['failure_reason'] or 'out_of_domain check failed'}")
            print(f"  Erwartet:       {r['expected_agent']}")
            print(f"  Genutzt:        {r['used_agents']}")
            print(f"  Confidence:     {r['confidence']:.0%}")
            if not r["answer_ok"]:
                print(f"  Keywords:       keine Treffer aus {r['found_keywords'] or '[]'}")

    print("\n── Ergebnisse ──────────────────────────────────────────")
    print(f"  Route Accuracy:                  {route_accuracy:.1%}")
    print(f"  Answer Keyword Accuracy:         {keyword_accuracy:.1%}")
    print(f"  Confidence Pass Rate:            {conf_pass_rate:.1%}")
    print(f"  Strict End-to-End Pass Rate:     {strict_pass_rate:.1%}")
    print(f"  Functional End-to-End Pass Rate: {functional_pass_rate:.1%}")
    print(f"  Average Confidence:              {avg_conf:.2f}")
