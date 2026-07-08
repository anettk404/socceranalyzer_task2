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
# TESTDATENSATZ — 18 Fragen basierend auf Prof-Vorgaben
# Gültige Routen: "openligadb", "statsbomb", "combined", "rag"
# ─────────────────────────────────────────────
TEST_CASES = [
    # openligadb — aktuelle Tabellen, Ergebnisse, Spielpläne
    {"question": "Welche Spiele stehen am nächsten Bundesliga-Spieltag an?",               "expected": "openligadb"},
    {"question": "Wie hat Bayern München in den letzten 5 Spielen abgeschnitten?",         "expected": "openligadb"},
    {"question": "Welche Teams stehen aktuell in der Bundesliga-Tabelle oben?",            "expected": "openligadb"},
    {"question": "Wann hat der 1. FC Köln sein letztes Heimspiel gewonnen?",               "expected": "openligadb"},

    # statsbomb — xG, Schüsse, Spielphasen, Event-Daten
    {"question": "Warum hat Bayern München dieses Spiel laut Daten gewonnen?",             "expected": "statsbomb"},
    {"question": "Welche Mannschaft hatte im Spiel zwischen Dortmund und Bayern die besseren Torchancen?", "expected": "statsbomb"},
    {"question": "Wie sah die Schussverteilung im letzten Spiel von Borussia Dortmund aus?", "expected": "statsbomb"},
    {"question": "Welche Phase des Spiels war entscheidend für den Sieg von Bayern München?", "expected": "statsbomb"},
    {"question": "Welche Teams überperformen ihre erwarteten Tore am stärksten?",           "expected": "statsbomb"},
    {"question": "Welche Mannschaft hat die beste Defensive basierend auf zugelassenem xG?", "expected": "statsbomb"},
    {"question": "Wie effizient ist Borussia Dortmund im Vergleich zur Liga im Abschluss?", "expected": "statsbomb"},

    # combined — braucht OpenLigaDB + StatsBomb
    {"question": "Warum war Bayer Leverkusen 2023/24 so dominant im Vergleich zu Tabellenstand, Punkten und xG-Werten?","expected": "combined"},

    # rag — Vereinsgeschichte, Biografien, Wikipedia-Wissen
    {"question": "Wann wurde Bayern München gegründet?",                                   "expected": "rag"},
    {"question": "Welche Titel hat Juventus FC in seiner Geschichte gewonnen?",            "expected": "rag"},
    {"question": "Wann wurde der FC Barcelona gegründet und von wem?",                     "expected": "rag"},
    {"question": "Wie viele Champions-League-Titel hat Real Madrid insgesamt gewonnen?",   "expected": "rag"},
    {"question": "Was ist das Estadio Santiago Bernabéu?",                                 "expected": "rag"},
    {"question": "Welche Spieler gelten als die größten Legenden des FC Barcelona?",       "expected": "rag"},

    # Edge Case: zeitkritischer Fakt — sollte zu rag geroutet werden
    {"question": "Wer ist der aktuelle Trainer von FC Bayern München?",                    "expected": "rag"},
    # Edge Case: mehrdeutiger Vereinsname — testet ob Supervisor korrekt interpretiert
    {"question": "Was weißt du über Bayern?",                                              "expected": "rag"},
    # Edge Case: komplett außerhalb der Domäne — sollte trotzdem einen Agenten wählen (rag als Fallback)
    {"question": "Wer hat die Formel-1-WM 2023 gewonnen?",                                "expected": "rag"},
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
