# Autor: Selma Elezovic
# Agent für detaillierte Ereignisdaten (xG, Schüsse, Pässe) aus der StatsBomb-Datenbank.

import json

from langchain_core.messages import HumanMessage, SystemMessage

from .shared import llm, PROMPTS, GraphState
from .db import run_query, SCHEMA


def statsbomb_agent(state: GraphState) -> GraphState:
    """Generiert SQL auf statsbomb_* Tabellen und formuliert eine Antwort.

    Zwei LLM-Calls: erster generiert das SQL-Query, zweiter formuliert
    das Datenbankergebnis als natürlichsprachige Antwort.
    """
    history_block = f"Gesprächskontext:\n{state.get('chat_history', '')}\n\n" if state.get("chat_history") else ""

    # 1. LLM-Call: SQL-Query generieren — nur statsbomb_matches und statsbomb_events
    sql_prompt = f"""Du hast Zugriff auf folgende SQLite-Tabellen:

{SCHEMA}

Generiere ein SQL-SELECT-Query um die folgende Frage zu beantworten.
Nutze nur die Tabellen statsbomb_matches und statsbomb_events.
Antworte ausschließlich mit dem SQL-Query, ohne Erklärungen oder Markdown.

{history_block}Frage: {state['question']}"""

    sql_response = llm.invoke([HumanMessage(content=sql_prompt)])
    # Markdown-Codeblöcke entfernen falls das LLM sie trotzdem einfügt
    sql = sql_response.content.strip().removeprefix("```sql").removesuffix("```").strip()

    # SQL ausführen — Fehler werden als Text weitergegeben, nicht als Exception
    try:
        rows = run_query(sql)
        db_result = json.dumps(rows, ensure_ascii=False)
    except Exception as e:
        db_result = f"SQL-Fehler: {e}"

    # 2. LLM-Call: Datenbankergebnis als natürlichsprachige Antwort formulieren
    answer_messages = [
        SystemMessage(content=PROMPTS["statsbomb"]["system"]),
        HumanMessage(content=f"Frage: {state['question']}\n\nDatenbankergebnis:\n{db_result}"),
    ]
    response = llm.invoke(answer_messages)
    sub_answer = response.content.strip()
    return {
        **state,
        "sql": sql,
        "sql_result": db_result,
        "sub_answers": state["sub_answers"] + [f"[statsbomb] {sub_answer}"],
        "steps": state["steps"] + ["statsbomb"],
        "active_agent": "statsbomb",
    }
