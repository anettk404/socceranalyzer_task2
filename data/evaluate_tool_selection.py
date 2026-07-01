"""
Tool Selection Accuracy — Orchestrator Evaluation
==================================================
Misst ob der Supervisor den richtigen Agenten für eine Frage wählt.

Metrik: Prozentsatz der Fragen bei denen der erste geroutete Agent
        dem erwarteten Agenten entspricht.

Aufruf: python data/evaluate_tool_selection.py
"""

import os
import sys
import json

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_core.messages import HumanMessage, SystemMessage
from agents.shared import llm, PROMPTS

# ─────────────────────────────────────────────
# TESTDATENSATZ — 25 Fragen mit erwarteter Agent-Zuordnung
# Gültige Routen: "openligadb", "statsbomb", "combined", "rag"
# ─────────────────────────────────────────────
TEST_CASES = [
    # openligadb — aktuelle Tabellen, Ergebnisse, Spielpläne
    {"question": "Wer steht aktuell auf Platz 1 der Bundesliga?",                         "expected": "openligadb"},
    {"question": "Wie viele Punkte hat Bayern München in der aktuellen Saison?",           "expected": "openligadb"},
    {"question": "Was war das Ergebnis des letzten Spiels von Borussia Dortmund?",         "expected": "openligadb"},
    {"question": "Wer hat das letzte Bundesliga-Spiel gewonnen?",                          "expected": "openligadb"},
    {"question": "Wie ist die aktuelle Torschützenliste der Bundesliga?",                  "expected": "openligadb"},
    {"question": "Wann spielt Bayern München als nächstes?",                               "expected": "openligadb"},
    {"question": "Welche Teams stehen aktuell in der Abstiegszone?",                       "expected": "openligadb"},

    # statsbomb — xG, Pässe, Schüsse, Event-Daten
    {"question": "Wie hoch ist der xG-Wert von Erling Haaland?",                          "expected": "statsbomb"},
    {"question": "Wie viele Schüsse hat Lionel Messi in der Champions League abgegeben?",  "expected": "statsbomb"},
    {"question": "Welcher Spieler hat die meisten Pässe in einem Match gespielt?",         "expected": "statsbomb"},
    {"question": "Wie viele Tore wurden per Kopf in den StatsBomb-Daten erzielt?",         "expected": "statsbomb"},
    {"question": "Zeig mir die Pass-Genauigkeit von Toni Kroos.",                          "expected": "statsbomb"},
    {"question": "Welche Spieler haben den höchsten xG-Wert pro 90 Minuten?",             "expected": "statsbomb"},
    {"question": "Wie viele Zweikämpfe hat ein Spieler im Durchschnitt gewonnen?",         "expected": "statsbomb"},

    # combined — braucht beide Datenquellen
    {"question": "Welche Teams aus der aktuellen Bundesliga kommen auch in den StatsBomb-Daten vor?", "expected": "combined"},
    {"question": "Vergleiche die xG-Werte mit der aktuellen Tabellenposition der Teams.",  "expected": "combined"},
    {"question": "Welche Bundesliga-Spieler haben laut StatsBomb die meisten Schüsse und wie stehen ihre Teams gerade?", "expected": "combined"},

    # rag — Vereinsgeschichte, Biografien, Wikipedia-Wissen
    {"question": "Wann wurde Bayern München gegründet?",                                   "expected": "rag"},
   # {"question": "Was ist die Geschichte von Real Madrid?",                                "expected": "rag"},
    {"question": "Welche Titel hat Juventus FC in seiner Geschichte gewonnen?",            "expected": "rag"},
    {"question": "Wann wurde der FC Barcelona gegründet und von wem?",                     "expected": "rag"},
    {"question": "Wie viele Champions-League-Titel hat Real Madrid insgesamt gewonnen?",   "expected": "rag"},
    {"question": "Wer war der erste Trainer von Borussia Dortmund?",                       "expected": "rag"},
    {"question": "Was ist das Estadio Santiago Bernabéu?",                                 "expected": "rag"},
    {"question": "Welche Spieler gelten als die größten Legenden des FC Barcelona?",       "expected": "rag"},
]


def get_predicted_route(question: str) -> tuple[str, str]:
    """Ruft den Supervisor einmal auf und gibt (route, reason) zurück."""
    user_content = (
        f"Originalfrage: {question}\n\n"
        f"Bereits aufgerufene Agenten: Noch keine.\n\n"
        f"Gesammelte Teilergebnisse:\nNoch keine."
    )
    messages = [
        SystemMessage(content=PROMPTS["supervisor"]["system"]),
        HumanMessage(content=user_content),
    ]
    response = llm.invoke(messages)
    raw = response.content.strip()
    try:
        parsed = json.loads(raw)
        return parsed.get("route", "UNKNOWN"), parsed.get("reason", "")
    except (json.JSONDecodeError, KeyError):
        return "PARSE_ERROR", raw


if __name__ == "__main__":
    print("Tool Selection Accuracy — Evaluation startet...\n")

    results = []
    correct = 0

    for tc in TEST_CASES:
        question = tc["question"]
        expected = tc["expected"]
        predicted, reason = get_predicted_route(question)
        is_correct = predicted == expected
        if is_correct:
            correct += 1

        results.append({
            "question":  question,
            "expected":  expected,
            "predicted": predicted,
            "correct":   is_correct,
            "reason":    reason,
        })
        status = "✓" if is_correct else "✗"
        print(f"  {status} [{expected:>11}] → [{predicted:>11}]  {question[:55]}")

    accuracy = correct / len(TEST_CASES)

    print("\n" + "=" * 70)
    print("ERGEBNISSE")
    print("=" * 70)
    print(f"Korrekt:  {correct} / {len(TEST_CASES)}")
    print(f"Accuracy: {accuracy:.1%}")

    # Fehleranalyse
    errors = [r for r in results if not r["correct"]]
    if errors:
        print("\nFalsch geroutete Fragen:")
        for r in errors:
            print(f"  erwartet '{r['expected']}' → bekam '{r['predicted']}': {r['question'][:60]}")

    # Verwirrungsmatrix
    agents = ["openligadb", "statsbomb", "combined", "rag"]
    print("\nVerwirrungsmatrix (Zeile=erwartet, Spalte=vorhergesagt):")
    print(f"{'':>12}" + "".join(f"{a:>12}" for a in agents))
    for exp in agents:
        row = f"{exp:>12}"
        for pred in agents:
            count = sum(1 for r in results if r["expected"] == exp and r["predicted"] == pred)
            row += f"{count:>12}"
        print(row)
