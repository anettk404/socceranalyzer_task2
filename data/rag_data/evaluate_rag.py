"""
RAG Evaluation ohne ragas-Abhängigkeit
=======================================
Bewertet die RAG-Pipeline (Pinecone + GPT) anhand von Testfragen.

Metriken (LLM-basiert, 0.0 – 1.0):
- faithfulness:       Ist die Antwort durch die Kontexte belegbar?
- answer_relevancy:   Beantwortet die Antwort die Frage?
- context_precision:  Sind die abgerufenen Chunks relevant für die Frage?

Aufruf: python data/rag_data/evaluate_rag.py
"""

import os
import sys
import json

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.agent_rag import _retrieve
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ─────────────────────────────────────────────
# TESTDATENSATZ
# ─────────────────────────────────────────────
TEST_CASES = [
    {
        "question": "Wann wurde Bayern München gegründet?",
        "ground_truth": "Bayern München wurde am 27. Februar 1900 gegründet.",
    },
    {
        "question": "Welche Titel hat Juventus FC gewonnen?",
        "ground_truth": "Juventus FC hat u.a. 36 Serie-A-Titel, 15 Coppa-Italia-Titel und 2 Champions-League-Titel gewonnen.",
    },
    {
        "question": "Was ist die Geschichte von Real Madrid?",
        "ground_truth": "Real Madrid wurde 1902 gegründet und ist einer der erfolgreichsten Fußballvereine der Welt mit zahlreichen Champions-League-Titeln.",
    },
    {
        "question": "Welche Erfolge hat Borussia Dortmund?",
        "ground_truth": "Borussia Dortmund hat 8 deutsche Meisterschaften und 1 Champions-League-Titel (1997) gewonnen.",
    },
    {
        "question": "Wann wurde der FC Barcelona gegründet?",
        "ground_truth": "Der FC Barcelona wurde am 29. November 1899 von Joan Gamper gegründet.",
    },
]


# ─────────────────────────────────────────────
# METRIKEN
# ─────────────────────────────────────────────
def _score(prompt: str) -> float:
    """Fragt das LLM nach einem Score zwischen 0.0 und 1.0."""
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        return float(response.content.strip())
    except ValueError:
        return 0.0


def faithfulness(question: str, answer: str, contexts: list[str]) -> float:
    context_text = "\n\n".join(contexts)
    prompt = f"""Bewerte ob die folgende Antwort ausschließlich durch die gegebenen Kontexte belegbar ist.
Antworte NUR mit einer Zahl zwischen 0.0 (gar nicht belegbar) und 1.0 (vollständig belegbar).

Frage: {question}
Antwort: {answer}
Kontexte:
{context_text}

Score (nur die Zahl):"""
    return _score(prompt)


def answer_relevancy(question: str, answer: str) -> float:
    prompt = f"""Bewerte wie gut die folgende Antwort die Frage beantwortet.
Antworte NUR mit einer Zahl zwischen 0.0 (gar nicht relevant) und 1.0 (vollständig relevant).

Frage: {question}
Antwort: {answer}

Score (nur die Zahl):"""
    return _score(prompt)


def context_precision(question: str, contexts: list[str]) -> float:
    context_text = "\n\n".join(contexts)
    prompt = f"""Bewerte wie relevant die folgenden Kontexte für die gegebene Frage sind.
Antworte NUR mit einer Zahl zwischen 0.0 (nicht relevant) und 1.0 (sehr relevant).

Frage: {question}
Kontexte:
{context_text}

Score (nur die Zahl):"""
    return _score(prompt)


# ─────────────────────────────────────────────
# HAUPTPROGRAMM
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("RAG Evaluation startet...\n")

    results = []

    for tc in TEST_CASES:
        question = tc["question"]
        print(f"Verarbeite: {question}")

        raw_context = _retrieve(question)
        context_chunks = [c for c in raw_context.split("\n\n---\n\n") if c.strip()]

        response = llm.invoke([
            SystemMessage(content="Du bist ein Fußball-Experte. Beantworte die Frage auf Basis der Wikipedia-Ausschnitte auf Deutsch."),
            HumanMessage(content=f"Frage: {question}\n\nKontext:\n{raw_context}"),
        ])
        answer = response.content.strip()

        f_score  = faithfulness(question, answer, context_chunks)
        ar_score = answer_relevancy(question, answer)
        cp_score = context_precision(question, context_chunks)

        results.append({
            "question":          question,
            "answer":            answer,
            "faithfulness":      f_score,
            "answer_relevancy":  ar_score,
            "context_precision": cp_score,
        })

    print("\n" + "=" * 70)
    print("ERGEBNISSE")
    print("=" * 70)
    print(f"{'Frage':<45} {'Faith':>7} {'Relev':>7} {'Prec':>7}")
    print("-" * 70)
    for r in results:
        q = r["question"][:44]
        print(f"{q:<45} {r['faithfulness']:>7.3f} {r['answer_relevancy']:>7.3f} {r['context_precision']:>7.3f}")

    print("-" * 70)
    avg_f  = sum(r["faithfulness"]      for r in results) / len(results)
    avg_ar = sum(r["answer_relevancy"]  for r in results) / len(results)
    avg_cp = sum(r["context_precision"] for r in results) / len(results)
    print(f"{'Durchschnitt':<45} {avg_f:>7.3f} {avg_ar:>7.3f} {avg_cp:>7.3f}")

    print("\nAntworten:")
    for r in results:
        print(f"\nFrage: {r['question']}")
        print(f"Antwort: {r['answer'][:300]}...")
