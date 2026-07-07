"""
Validation Agent Catch Rate — Evaluation
=========================================
Misst wie viele absichtlich falsche Antworten (Halluzinationen)
der Validator erkennt und korrigiert.

Metriken:
- Catch Rate:   Anteil der Halluzinationen bei denen confidence < 0.6
- Correction Rate: Anteil bei denen die Antwort tatsächlich verändert wurde

Aufruf: python data/evaluate_validator.py
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.agent_validator import validator_agent

# ─────────────────────────────────────────────
# TESTDATENSATZ
# Jeder Fall hat eine absichtlich falsche Antwort (hallucination)
# und eine korrekte Referenzantwort (ground_truth) zum Vergleich
# ─────────────────────────────────────────────
TEST_CASES = [
    {
        "label": "Falsches Gründungsdatum",
        "question": "Wann wurde Bayern München gegründet?",
        "hallucination": "Bayern München wurde am 15. März 1963 gegründet.",
        "ground_truth": "Bayern München wurde am 27. Februar 1900 gegründet.",
    },
    {
        "label": "Falsche Titelanzahl",
        "question": "Wie viele Champions-League-Titel hat Real Madrid gewonnen?",
        "hallucination": "Real Madrid hat 5 Champions-League-Titel gewonnen.",
        "ground_truth": "Real Madrid hat 15 Champions-League-Titel gewonnen.",
    },
    {
        "label": "Falscher Vereinsgründer",
        "question": "Wer gründete den FC Barcelona?",
        "hallucination": "Der FC Barcelona wurde von König Alfonso XIII gegründet.",
        "ground_truth": "Der FC Barcelona wurde von Joan Gamper gegründet.",
    },
    {
        "label": "Komplett falscher Verein",
        "question": "Welcher Verein hat die meisten Bundesliga-Titel gewonnen?",
        "hallucination": "Borussia Dortmund hat mit 18 Titeln die meisten Bundesliga-Meisterschaften.",
        "ground_truth": "Bayern München hat mit über 30 Titeln die meisten Bundesliga-Meisterschaften.",
    },
    {
        "label": "Inhaltsleere Antwort",
        "question": "Wer steht auf Platz 1 der Bundesliga?",
        "hallucination": "Ich konnte leider keine relevanten Daten finden.",
        "ground_truth": "Eine konkrete Teamnennung basierend auf aktuellen Tabellendaten.",
    },
    {
        "label": "Thema komplett verfehlt",
        "question": "Wie viele Tore hat Robert Lewandowski erzielt?",
        "hallucination": "Die Bundesliga besteht aus 18 Vereinen und wird jährlich ausgespielt.",
        "ground_truth": "Eine Antwort mit Lewandowskis Torstatistik.",
    },
    {
        "label": "Erfundener Spieler",
        "question": "Wer ist der Topscorer der aktuellen Bundesliga-Saison?",
        "hallucination": "Der Topscorer ist Marco Steinberg mit 28 Toren.",
        "ground_truth": "Eine Antwort mit einem tatsächlichen Bundesliga-Topscorer.",
    },
    {
        "label": "Falsches Stadion",
        "question": "Wie heißt das Stadion von Borussia Dortmund?",
        "hallucination": "Das Stadion von Borussia Dortmund heißt Allianz Arena.",
        "ground_truth": "Das Stadion von Borussia Dortmund heißt BVB Stadion Dortmund (früher Signal Iduna Park).",
    },
    {
        "label": "Korrekte Antwort (Kontrollfall)",
        "question": "In welchem Land spielt die Bundesliga?",
        "hallucination": "Die Bundesliga wird in Deutschland gespielt.",
        "ground_truth": "Die Bundesliga wird in Deutschland gespielt.",
    },
    {
        "label": "Korrekte Antwort (Kontrollfall 2)",
        "question": "Wie viele Teams spielen in der Bundesliga?",
        "hallucination": "In der Bundesliga spielen 18 Vereine.",
        "ground_truth": "In der Bundesliga spielen 18 Vereine.",
    },
    # Edge Case: zeitkritischer Trainer-Fakt — genau der Bug der gefunden wurde
    {
        "label": "Falscher Trainer (zeitkritisch)",
        "question": "Wer ist der aktuelle Trainer von FC Bayern München?",
        "hallucination": "Der aktuelle Trainer des FC Bayern München ist Thomas Tuchel.",
        "ground_truth": "Der aktuelle Trainer des FC Bayern München ist Vincent Kompany.",
    },
    # Edge Case: außerhalb der Domäne — Validator soll niedrigen Score geben
    {
        "label": "Frage außerhalb der Domäne",
        "question": "Wer hat die Formel-1-WM 2023 gewonnen?",
        "hallucination": "Die Formel-1-WM 2023 wurde von Max Verstappen gewonnen.",
        "ground_truth": "Diese Frage liegt außerhalb der Fußball-Domäne.",
    },
]

HALLUCINATION_CASES = [tc for tc in TEST_CASES if not tc["label"].startswith("Korrekte")]
CONTROL_CASES = [tc for tc in TEST_CASES if tc["label"].startswith("Korrekte")]

EMPTY_BASE = {
    "route": "", "route_reason": "", "sql": "",
    "sub_answers": [], "steps": [], "active_agent": "", "confidence": 0.0,
}

CATCH_THRESHOLD = 0.6  # confidence unter diesem Wert = Halluzination erkannt


if __name__ == "__main__":
    print("Validation Agent Catch Rate — Evaluation startet...\n")

    results = []

    for tc in TEST_CASES:
        state = {**EMPTY_BASE, "question": tc["question"], "answer": tc["hallucination"]}
        result = validator_agent(state)

        confidence = result["confidence"]
        answer_changed = result["answer"].strip() != tc["hallucination"].strip()
        caught = confidence < CATCH_THRESHOLD

        is_control = tc["label"].startswith("Korrekte")
        results.append({
            **tc,
            "confidence":     confidence,
            "answer_out":     result["answer"],
            "answer_changed": answer_changed,
            "caught":         caught,
            "is_control":     is_control,
        })

        bar = int(confidence * 20) * "█" + int((1 - confidence) * 20) * "░"
        flag = "ERKANNT" if caught else ("OK" if is_control else "DURCHGERUTSCHT")
        print(f"  [{flag:>13}] {bar} {confidence:.0%}  {tc['label']}")

    # ─────────────────────────────────────────────
    # METRIKEN
    # ─────────────────────────────────────────────
    hall_results = [r for r in results if not r["is_control"]]
    ctrl_results  = [r for r in results if r["is_control"]]

    catch_rate      = sum(r["caught"] for r in hall_results) / len(hall_results)
    correction_rate = sum(r["answer_changed"] for r in hall_results) / len(hall_results)
    false_positive  = sum(r["caught"] for r in ctrl_results) / len(ctrl_results) if ctrl_results else 0.0

    print("\n" + "=" * 70)
    print("ERGEBNISSE")
    print("=" * 70)
    print(f"Halluzinationen getestet:  {len(hall_results)}")
    print(f"Catch Rate     (conf<{CATCH_THRESHOLD}): {catch_rate:.1%}  — wie viele erkannt")
    print(f"Correction Rate:           {correction_rate:.1%}  — wie viele Antworten verändert")
    print(f"False Positives:           {false_positive:.1%}  — korrekte Antworten fälschlich markiert")

    missed = [r for r in hall_results if not r["caught"]]
    if missed:
        print(f"\nDurchgerutschte Halluzinationen ({len(missed)}):")
        for r in missed:
            print(f"  [{r['confidence']:.0%}] {r['label']}: {r['hallucination'][:60]}")
