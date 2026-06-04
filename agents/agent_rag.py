from .shared import GraphState


def rag_agent(state: GraphState) -> GraphState:
    """RAG-Agent auf Basis von Chroma-Vektordatenbank (Wikipedia). Noch nicht implementiert."""
    sub_answer = (
        "Hintergrundinformationen aus der Wissensdatenbank sind noch nicht verfügbar "
        "(Chroma-Index wird in einem späteren Schritt befüllt)."
    )
    return {
        **state,
        "sub_answers": state["sub_answers"] + [f"[rag] {sub_answer}"],
        "steps": state["steps"] + ["rag"],
    }
