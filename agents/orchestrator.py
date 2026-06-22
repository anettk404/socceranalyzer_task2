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


def supervisor(state: GraphState) -> GraphState:
    """Entscheidet iterativ welcher Agent als nächstes gebraucht wird, oder FINISH."""
    sub_answers_text = "\n".join(state["sub_answers"]) if state["sub_answers"] else "Noch keine."
    steps_text = ", ".join(state["steps"]) if state["steps"] else "Noch keine."

    user_content = (
        f"Originalfrage: {state['question']}\n\n"
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


def aggregator(state: GraphState) -> GraphState:
    """Fasst alle sub_answers zu einer finalen Antwort zusammen."""
    if len(state["sub_answers"]) == 1:
        # Nur eine Quelle — direkt weitergeben ohne extra LLM-Call
        answer = state["sub_answers"][0].split("] ", 1)[-1]
        return {**state, "answer": answer}

    sub_answers_text = "\n\n".join(state["sub_answers"])
    messages = [
        SystemMessage(content=PROMPTS["aggregator"]["system"]),
        HumanMessage(content=f"Frage: {state['question']}\n\nTeilergebnisse:\n{sub_answers_text}"),
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

    graph.add_node("supervisor", supervisor)
    graph.add_node("openligadb_agent", openligadb_agent)
    graph.add_node("statsbomb_agent", statsbomb_agent)
    graph.add_node("combined_agent", combined_agent)
    graph.add_node("rag_agent", rag_agent)
    graph.add_node("aggregator", aggregator)
    graph.add_node("validator", validator_agent)

    graph.add_edge(START, "supervisor")
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
    ]
    empty_state = {"question": "", "route": "", "route_reason": "", "sql": "", "sub_answers": [], "steps": [], "answer": ""}
    for q in test_questions:
        print(f"\nFrage: {q}")
        result = app.invoke({**empty_state, "question": q})
        print(f"  → Steps:   {result['steps']}")
        print(f"  → Antwort: {result['answer']}")
