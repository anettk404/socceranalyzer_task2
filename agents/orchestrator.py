"""
LangGraph Orchestrator — Supervisor-Pattern.

Graph:
  START → supervisor → [openligadb_agent | statsbomb_agent | combined_agent | rag_agent] → supervisor (loop)
                     → aggregator → validator → END
"""

import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from .shared import llm, PROMPTS, GraphState
from .agent_openligadb import openligadb_agent
from .agent_statsbomb import statsbomb_agent
from .agent_combined import combined_agent
from .agent_rag import rag_agent
from .agent_validator import validator_agent


def question_rewriter(state: GraphState) -> GraphState:
    """Reichert vage Folgefragen mit Kontext aus chat_history an.

    Aus 'was weißt du über den Verein?' + History Bayern → 'Was weißt du über Bayern München?'
    Konkrete Fragen werden unverändert durchgereicht.
    """
    history = state.get("chat_history", "")
    if not history:
        return state

    response = llm.invoke([
        SystemMessage(content=(
            "Du bist ein Assistent der Folgefragen in vollständige, eigenständige Fragen umschreibt.\n"
            "Wenn die Frage bereits einen konkreten Verein oder Spieler enthält, gib sie UNVERÄNDERT zurück.\n"
            "Wenn die Frage vage ist (z.B. 'was weißt du über den Verein', 'und die Statistiken?', "
            "'erzähl mehr', 'was noch?'), ersetze alle vagen Referenzen durch das konkrete Subjekt "
            "aus dem Gesprächsverlauf.\n"
            "Antworte NUR mit der umgeschriebenen Frage, kein weiterer Text."
        )),
        HumanMessage(content=f"Gesprächsverlauf:\n{history}\n\nFolgefrage: {state['question']}"),
    ])
    rewritten = response.content.strip()
    return {**state, "question": rewritten}


def supervisor(state: GraphState) -> GraphState:
    """Entscheidet iterativ welcher Agent als nächstes gebraucht wird, oder FINISH."""
    sub_answers_text = "\n".join(state["sub_answers"]) if state["sub_answers"] else "Noch keine."
    steps_text = ", ".join(state["steps"]) if state["steps"] else "Noch keine."

    history_text = state.get("chat_history", "")
    history_block = (
        f"GESPRÄCHSVERLAUF (für Kontext-Auflösung bei vagen Fragen):\n{history_text}\n\n"
        f"Wenn die aktuelle Frage keinen expliziten Verein/Spieler nennt, "
        f"beziehe sie auf das zuletzt besprochene Thema im Verlauf.\n\n"
    ) if history_text else ""

    user_content = (
        f"{history_block}"
        f"Aktuelle Frage: {state['question']}\n\n"
        f"Bereits aufgerufene Agenten: {steps_text}\n\n"
        f"Gesammelte Teilergebnisse:\n{sub_answers_text}"
    )
    messages = [
        SystemMessage(content=PROMPTS["supervisor"]["system"]),
        HumanMessage(content=user_content),
    ]
    response = llm.invoke(messages)
    raw = response.content.strip()

    try:
        parsed = json.loads(raw)
        route = parsed["route"]
        reason = parsed.get("reason", "")
    except (json.JSONDecodeError, KeyError):
        route = "FINISH"
        reason = f"Parsing-Fehler, Fallback auf FINISH. LLM-Antwort: {raw}"

    return {**state, "route": route, "route_reason": reason}


_EMPTY_INDICATORS = [
    "keine daten", "keine ergebnisse", "nicht gefunden", "leider", "kann ich nicht",
    "no data", "not found", "sql-fehler", "[]", "keine informationen",
]

def _all_empty(sub_answers: list[str]) -> bool:
    """Prüft ob alle Teilergebnisse inhaltsleer sind."""
    if not sub_answers:
        return True
    for answer in sub_answers:
        text = answer.lower()
        if not any(ind in text for ind in _EMPTY_INDICATORS):
            return False
    return True


def aggregator(state: GraphState) -> GraphState:
    """Fasst alle sub_answers zu einer finalen Antwort zusammen."""
    history_block = f"Bisheriger Gesprächsverlauf (zur Vermeidung von Wiederholungen):\n{state.get('chat_history', '')}\n\n" if state.get("chat_history") else ""

    if _all_empty(state["sub_answers"]):
        return {
            **state,
            "answer": (
                "Zu dieser Frage konnte ich leider keine Daten in meinen Quellen finden. "
                "Meine Datenquellen umfassen Bundesliga-Tabellen und -Ergebnisse (OpenLigaDB), "
                "detaillierte Ereignisdaten ausgewählter Ligen (StatsBomb) sowie "
                "Vereinsinformationen aus Wikipedia. Bitte formuliere die Frage anders "
                "oder frage nach einem Thema das diese Quellen abdecken."
            ),
        }

    if len(state["sub_answers"]) == 1:
        answer = state["sub_answers"][0].split("] ", 1)[-1]
        if not history_block:
            return {**state, "answer": answer}
        # Auch bei einzelner Quelle den Kontext nutzen um Wiederholungen zu vermeiden
        messages = [
            SystemMessage(content=PROMPTS["aggregator"]["system"]),
            HumanMessage(content=f"{history_block}Frage: {state['question']}\n\nTeilergebnis:\n{answer}"),
        ]
        response = llm.invoke(messages)
        return {**state, "answer": response.content.strip()}

    sub_answers_text = "\n\n".join(state["sub_answers"])
    messages = [
        SystemMessage(content=PROMPTS["aggregator"]["system"]),
        HumanMessage(content=f"{history_block}Frage: {state['question']}\n\nTeilergebnisse:\n{sub_answers_text}"),
    ]
    response = llm.invoke(messages)
    return {**state, "answer": response.content.strip()}


def supervisor_route(state: GraphState) -> Literal[
    "openligadb_agent", "statsbomb_agent", "combined_agent", "rag_agent", "aggregator"
]:
    route = state["route"]
    if route == "openligadb":
        return "openligadb_agent"
    if route == "statsbomb":
        return "statsbomb_agent"
    if route == "combined":
        return "combined_agent"
    if route == "rag":
        return "rag_agent"
    return "aggregator"


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("question_rewriter", question_rewriter)
    graph.add_node("supervisor", supervisor)
    graph.add_node("openligadb_agent", openligadb_agent)
    graph.add_node("statsbomb_agent", statsbomb_agent)
    graph.add_node("combined_agent", combined_agent)
    graph.add_node("rag_agent", rag_agent)
    graph.add_node("aggregator", aggregator)
    graph.add_node("validator", validator_agent)

    graph.add_edge(START, "question_rewriter")
    graph.add_edge("question_rewriter", "supervisor")
    graph.add_conditional_edges("supervisor", supervisor_route)

    # Alle Agenten gehen zurück zum Supervisor
    for agent in ["openligadb_agent", "statsbomb_agent", "combined_agent", "rag_agent"]:
        graph.add_edge(agent, "supervisor")

    graph.add_edge("aggregator", "validator")
    graph.add_edge("validator", END)

    return graph.compile()


app = build_graph()


if __name__ == "__main__":
    test_questions = [
        #"Wer steht gerade auf Platz 1 der Bundesliga im Jahre 2023?",
        #"Wie hoch ist der xG-Wert von Erling Haaland in der Champions League?",
        "Welche Teams aus der aktuellen Bundesliga-Tabelle kommen auch in den StatsBomb-Matches vor?",
        "Welche Titel hat Juventus FC gewonnen?",
        "Welcher Spieler hat den höchsten xG-Wert in der Bundesliga 2023/24?",
        "Wie viele Tore hat Harry Kane per Kopf erzielt?",
        "Welche Teams haben die meisten Schüsse abgegeben?",
    ]
    empty_state = {"question": "", "chat_history": "", "route": "", "route_reason": "", "sql": "", "sql_result": "", "sub_answers": [], "steps": [], "active_agent": "", "answer": "", "confidence": 0.0}
    for q in test_questions:
        print(f"\nFrage: {q}")
        result = app.invoke({**empty_state, "question": q})
        print(f"  → Steps:      {result['steps']}")
        print(f"  → Confidence: {result['confidence']:.0%}")
        print(f"  → Antwort:    {result['answer']}")
