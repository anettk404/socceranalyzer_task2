import json

from langchain_core.messages import HumanMessage, SystemMessage

from .shared import llm, PROMPTS, GraphState
from .db import run_query, SCHEMA


def openligadb_agent(state: GraphState) -> GraphState:
    """Generiert SQL auf openliga_* Tabellen und formuliert eine Antwort."""
    sql_prompt = f"""Du hast Zugriff auf folgende SQLite-Tabellen:

{SCHEMA}

Generiere ein SQL-SELECT-Query um die folgende Frage zu beantworten.
Nutze nur die Tabellen openliga_table und openliga_matches.
Antworte ausschließlich mit dem SQL-Query, ohne Erklärungen oder Markdown.

Frage: {state['question']}"""

    sql_response = llm.invoke([HumanMessage(content=sql_prompt)])
    sql = sql_response.content.strip().removeprefix("```sql").removesuffix("```").strip()

    try:
        rows = run_query(sql)
        db_result = json.dumps(rows, ensure_ascii=False)
    except Exception as e:
        db_result = f"SQL-Fehler: {e}"

    answer_messages = [
        SystemMessage(content=PROMPTS["openligadb"]["system"]),
        HumanMessage(content=f"Frage: {state['question']}\n\nDatenbankErgebnis:\n{db_result}"),
    ]
    response = llm.invoke(answer_messages)
    sub_answer = response.content.strip()
    return {
        **state,
        "sql": sql,
        "sub_answers": state["sub_answers"] + [f"[openligadb] {sub_answer}"],
        "steps": state["steps"] + ["openligadb"],
    }
