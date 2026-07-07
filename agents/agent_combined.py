import json

from langchain_core.messages import HumanMessage, SystemMessage

from .shared import llm, PROMPTS, GraphState
from .db import run_query, SCHEMA


def combined_agent(state: GraphState) -> GraphState:
    """Generiert SQL auf allen Tabellen (openliga_* + statsbomb_*) und formuliert eine Antwort."""
    history_block = f"Gesprächskontext:\n{state.get('chat_history', '')}\n\n" if state.get("chat_history") else ""
    sql_prompt = f"""Du hast Zugriff auf folgende SQLite-Tabellen:

{SCHEMA}

Generiere ein SQL-SELECT-Query um die folgende Frage zu beantworten.
Du darfst alle Tabellen nutzen und JOINs über Tabellengrenzen hinweg verwenden.
Antworte ausschließlich mit dem SQL-Query, ohne Erklärungen oder Markdown.

{history_block}Frage: {state['question']}"""

    sql_response = llm.invoke([HumanMessage(content=sql_prompt)])
    sql = sql_response.content.strip().removeprefix("```sql").removesuffix("```").strip()

    try:
        rows = run_query(sql)
        db_result = json.dumps(rows, ensure_ascii=False)
    except Exception as e:
        db_result = f"SQL-Fehler: {e}"

    answer_messages = [
        SystemMessage(content=PROMPTS["combined"]["system"]),
        HumanMessage(content=f"Frage: {state['question']}\n\nDatenbankergebnis:\n{db_result}"),
    ]
    response = llm.invoke(answer_messages)
    sub_answer = response.content.strip()

    return {
        **state,
        "sql": sql,
        "sql_result": db_result,
        "sub_answers": state["sub_answers"] + [f"[combined] {sub_answer}"],
        "steps": state["steps"] + ["combined"],
        "active_agent": "combined",
    }
