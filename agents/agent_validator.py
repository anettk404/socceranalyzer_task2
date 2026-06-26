import json

from langchain_core.messages import HumanMessage, SystemMessage

from .shared import llm, PROMPTS, GraphState
from .agent_rag import _retrieve


def _needs_fact_check(answer: str) -> bool:
    """Heuristik: enthält die Antwort faktische Aussagen die überprüft werden sollten?"""
    fact_indicators = [
        "gegründet", "titel", "gewonnen", "geboren", "gestorben", "stadion",
        "champions", "meisterschaft", "rekord", "trainer", "gründer", "geschichte",
        "wurde", "hat", "ist", "sind", "war", "waren",
    ]
    answer_lower = answer.lower()
    return any(word in answer_lower for word in fact_indicators)


def validator_agent(state: GraphState) -> GraphState:
    """Prüft die Antwort auf Halluzinationen und gibt einen Confidence-Score zurück.

    Bei faktischen Aussagen wird zusätzlich ein RAG-Fact-Check gegen Pinecone durchgeführt.
    """
    system_prompt = PROMPTS["validator"]["system"]

    # Quellkontext aufbauen: SQL-Rohdaten haben Vorrang, danach RAG
    source_context = ""
    sql_result = state.get("sql_result", "")
    if sql_result and "SQL-Fehler" not in sql_result and sql_result != "[]":
        # Rohdaten aus der DB auf 2000 Zeichen kürzen damit der Prompt nicht zu lang wird
        truncated = sql_result[:2000] + ("..." if len(sql_result) > 2000 else "")
        source_context = f"\n\nVerifizierte Rohdaten aus der Datenbank (Quelldaten der Antwort):\n{truncated}"
    elif _needs_fact_check(state["answer"]):
        retrieved = _retrieve(state["question"])
        if retrieved and "Keine relevanten" not in retrieved:
            source_context = f"\n\nVerifizierte Fakten aus der Wissensdatenbank:\n{retrieved}"

    user_content = f"""Frage: {state['question']}

Antwort des Agenten:
{state['answer']}{source_context}

Antworte ausschließlich mit einem JSON-Objekt in diesem Format:
{{"answer": "<finale Antwort>", "confidence": <0.0–1.0>, "reason": "<kurze Begründung>"}}

Regeln für den confidence-Score:
- 0.9–1.0: Antwort ist klar, vollständig und alle Fakten sind dir sicher bekannt und korrekt.
- 0.6–0.89: Antwort ist weitgehend korrekt, leicht unvollständig oder einzelne Details unsicher.
- 0.3–0.59: Antwort enthält Fakten die du NICHT sicher bestätigen kannst, oder weicht von Quelldaten ab.
- 0.0–0.29: Antwort widerspricht bekannten Fakten, ist inhaltsleer oder komplett am Thema vorbei.

Wichtig:
- Wenn Quelldaten vorhanden sind und die Antwort davon abweicht → korrigiere und senke den Score.
- Wenn die Antwort konkrete Fakten enthält (Jahreszahlen, Titelanzahlen, Namen, Orte) die du
  nicht mit Sicherheit bestätigen kannst → Score maximal 0.5, auch wenn es plausibel klingt.
- Im Zweifel immer konservativ bewerten: lieber 0.4 als 0.9 bei unsicheren Fakten."""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    response = llm.invoke(messages)
    raw = response.content.strip()

    try:
        parsed = json.loads(raw)
        answer = parsed.get("answer", state["answer"])
        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (json.JSONDecodeError, ValueError, KeyError):
        answer = state["answer"]
        confidence = 0.5

    return {**state, "answer": answer, "confidence": confidence, "active_agent": "validator"}


if __name__ == "__main__":
    # Testfälle: (frage, antwort, erwartetes Verhalten)
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

    empty_base = {
        "route": "", "route_reason": "", "sql": "",
        "sub_answers": [], "steps": [], "active_agent": "", "confidence": 0.0,
    }

    print("Validator Test\n" + "=" * 60)
    for tc in test_cases:
        state = {**empty_base, "question": tc["question"], "answer": tc["answer"]}
        result = validator_agent(state)
        bar = int(result["confidence"] * 20) * "█" + int((1 - result["confidence"]) * 20) * "░"
        changed = result["answer"].strip() != tc["answer"].strip()
        print(f"\n[{tc['label']}]")
        print(f"  Frage:      {tc['question']}")
        print(f"  Original:   {tc['answer']}")
        print(f"  Validiert:  {result['answer']}")
        print(f"  Korrigiert: {'ja' if changed else 'nein'}")
        print(f"  Confidence: {bar} {result['confidence']:.0%}")
