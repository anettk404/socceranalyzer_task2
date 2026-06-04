from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict

load_dotenv()

_PROMPTS_PATH = Path(__file__).parent / "prompts.yaml"


def _load_prompts() -> dict[str, Any]:
    with open(_PROMPTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


PROMPTS = _load_prompts()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class GraphState(TypedDict):
    question: str
    route: str
    route_reason: str
    sql: str
    sub_answers: list[str]  # Teilergebnisse der einzelnen Agenten
    steps: list[str]         # welche Agenten schon aufgerufen wurden
    answer: str
