from langchain_core.messages import HumanMessage, SystemMessage

from .shared import llm, PROMPTS, GraphState


def validator_agent(state: GraphState) -> GraphState:
    """Prüft die Antwort auf Halluzinationen und Konsistenz zur Frage."""
    system_prompt = PROMPTS["validator"]["system"]
    user_content = f"""Frage: {state['question']}

Antwort des Agenten:
{state['answer']}

Gibt die Antwort die Frage korrekt wieder? Wenn ja, gib die Antwort unverändert zurück.
Wenn nicht, korrigiere sie. Gib NUR die finale Antwort aus, keine Erklärungen."""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    response = llm.invoke(messages)
    return {**state, "answer": response.content.strip()}
