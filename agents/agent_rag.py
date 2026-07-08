# Autor: Selma Elezovic
# RAG-Agent: sucht relevante Wikipedia-Textabschnitte über Pinecone (Vektordatenbank)
# und formuliert daraus eine Antwort zu Vereinsgeschichte, Titeln und Hintergrundwissen.

import os

from langchain_core.messages import HumanMessage, SystemMessage
from llama_index.embeddings.openai import OpenAIEmbedding
from pinecone import Pinecone

from .shared import llm, PROMPTS, GraphState

# Lazy-initialized on first call — Pinecone-Verbindung und Embedding-Modell
# werden nur einmal aufgebaut und dann wiederverwendet.
_pc: Pinecone | None = None
_index = None
_embed_model: OpenAIEmbedding | None = None

INDEX_NAME     = "gensocceranalyzer-wikipedia"
EMBEDDING_MODEL = "text-embedding-3-small"
TOP_K          = 5


def _get_pinecone_index():
    global _pc, _index
    if _index is None:
        _pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        _index = _pc.Index(INDEX_NAME)
    return _index


def _get_embed_model() -> OpenAIEmbedding:
    global _embed_model
    if _embed_model is None:
        _embed_model = OpenAIEmbedding(
            model=EMBEDDING_MODEL,
            api_key=os.environ["OPENAI_API_KEY"],
        )
    return _embed_model


def _retrieve(question: str, top_k: int = TOP_K) -> str:
    """Wandelt die Frage in einen Embedding-Vektor um und sucht die ähnlichsten
    Wikipedia-Chunks in Pinecone. Gibt die Texte mit Team/Liga-Metadaten zurück.

    top_k kann überschrieben werden — der Validator nutzt 10 statt 5 für bessere
    Faktentreffer bei der Verifikation.
    """
    embed_model = _get_embed_model()
    index = _get_pinecone_index()

    # Frage als Vektor kodieren und semantisch ähnliche Chunks suchen
    query_vector = embed_model.get_query_embedding(question)
    results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)

    if not results["matches"]:
        return "Keine relevanten Dokumente gefunden."

    # Metadaten (Team, Liga) als Kontext-Header vor jeden Chunk stellen
    chunks = []
    for match in results["matches"]:
        meta = match["metadata"]
        text = meta.get("text", "").strip()
        team = meta.get("team", "")
        liga = meta.get("liga", "")
        chunks.append(f"[{team} – {liga}]\n{text}")

    return "\n\n---\n\n".join(chunks)


def rag_agent(state: GraphState) -> GraphState:
    """Retrieval-Agent: sucht relevante Wikipedia-Chunks aus Pinecone und formuliert eine Antwort."""
    context = _retrieve(state["question"])

    messages = [
        SystemMessage(content=PROMPTS["rag"]["system"]),
        HumanMessage(content=(
            f"Frage: {state['question']}\n\n"
            f"Relevante Wikipedia-Ausschnitte:\n{context}"
        )),
    ]
    response = llm.invoke(messages)
    sub_answer = response.content.strip()

    return {
        **state,
        "sub_answers": state["sub_answers"] + [f"[rag] {sub_answer}"],
        "steps": state["steps"] + ["rag"],
        "active_agent": "rag",
    }
