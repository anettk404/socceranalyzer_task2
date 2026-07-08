# Autor: Selma Elezovic
"""
Validation Agent Catch Rate — Evaluation
=========================================
Misst wie viele absichtlich falsche Antworten (Halluzinationen)
der Validator erkennt und korrigiert.

Metriken:
- Catch Rate:         Anteil der Halluzinationen bei denen confidence < 0.6
- Correction Rate:    Anteil bei denen die Antwort tatsächlich verändert wurde
- False Positive Rate: Anteil korrekter Antworten die fälschlich mit confidence < 0.6 markiert wurden

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
# type: "hallucination" — absichtlich falsche Antwort
# type: "control"       — korrekte Antwort, darf NICHT markiert werden
# type: "out_of_domain" — außerhalb der Fußball-Domäne
# ─────────────────────────────────────────────
TEST_CASES = [
    # ── Halluzinationen ──────────────────────────────────────────────────────
    {
        "type": "hallucination",
        "label": "Falsches Gründungsdatum",
        "question": "Wann wurde Bayern München gegründet?",
        "answer_in": "Bayern München wurde am 15. März 1963 gegründet.",
        "ground_truth": "Bayern München wurde am 27. Februar 1900 gegründet.",
    },
    {
        "type": "hallucination",
        "label": "Falsche Titelanzahl",
        "question": "Wie viele Champions-League-Titel hat Real Madrid gewonnen?",
        "answer_in": "Real Madrid hat 5 Champions-League-Titel gewonnen.",
        "ground_truth": "Real Madrid hat 15 Champions-League-Titel gewonnen.",
    },
    {
        "type": "hallucination",
        "label": "Falscher Vereinsgründer",
        "question": "Wer gründete den FC Barcelona?",
        "answer_in": "Der FC Barcelona wurde von König Alfonso XIII gegründet.",
        "ground_truth": "Der FC Barcelona wurde von Joan Gamper gegründet.",
    },
    {
        "type": "hallucination",
        "label": "Komplett falscher Verein",
        "question": "Welcher Verein hat die meisten Bundesliga-Titel gewonnen?",
        "answer_in": "Borussia Dortmund hat mit 18 Titeln die meisten Bundesliga-Meisterschaften.",
        "ground_truth": "Bayern München hat mit über 30 Titeln die meisten Bundesliga-Meisterschaften.",
    },
    {
        "type": "hallucination",
        "label": "Inhaltsleere Antwort",
        "question": "Wer steht auf Platz 1 der Bundesliga?",
        "answer_in": "Ich konnte leider keine relevanten Daten finden.",
        "ground_truth": "Eine konkrete Teamnennung basierend auf aktuellen Tabellendaten.",
    },
    {
        "type": "hallucination",
        "label": "Thema komplett verfehlt",
        "question": "Wie viele Tore hat Robert Lewandowski erzielt?",
        "answer_in": "Die Bundesliga besteht aus 18 Vereinen und wird jährlich ausgespielt.",
        "ground_truth": "Eine Antwort mit Lewandowskis Torstatistik.",
    },
    {
        "type": "hallucination",
        "label": "Erfundener Spieler",
        "question": "Wer ist der Topscorer der aktuellen Bundesliga-Saison?",
        "answer_in": "Der Topscorer ist Marco Steinberg mit 28 Toren.",
        "ground_truth": "Eine Antwort mit einem tatsächlichen Bundesliga-Topscorer.",
    },
    {
        "type": "hallucination",
        "label": "Falsches Stadion",
        "question": "Wie heißt das Stadion von Borussia Dortmund?",
        "answer_in": "Das Stadion von Borussia Dortmund heißt Allianz Arena.",
        "ground_truth": "Das Stadion von Borussia Dortmund heißt BVB Stadion Dortmund (früher Signal Iduna Park).",
    },
    {
        "type": "hallucination",
        "label": "Falscher Trainer (zeitkritisch)",
        "question": "Wer ist der aktuelle Trainer von FC Bayern München?",
        "answer_in": "Der aktuelle Trainer des FC Bayern München ist Thomas Tuchel.",
        "ground_truth": "Der aktuelle Trainer des FC Bayern München ist Vincent Kompany.",
    },

    # ── Kontrollfälle (korrekte Antworten) ──────────────────────────────────
    {
        "type": "control",
        "label": "Korrekte Bayern-Gründung",
        "question": "Wann wurde Bayern München gegründet?",
        "answer_in": "Bayern München wurde am 27. Februar 1900 gegründet.",
        "ground_truth": "Bayern München wurde am 27. Februar 1900 gegründet.",
    },
    {
        "type": "control",
        "label": "Korrektes Dortmund-Stadion",
        "question": "Wie heißt das Stadion von Borussia Dortmund?",
        "answer_in": "Das Stadion von Borussia Dortmund heißt BVB Stadion Dortmund, früher bekannt als Signal Iduna Park.",
        "ground_truth": "Das Stadion von Borussia Dortmund heißt BVB Stadion Dortmund (früher Signal Iduna Park).",
    },
    {
        "type": "control",
        "label": "Korrekter Barcelona-Gründer",
        "question": "Wer gründete den FC Barcelona?",
        "answer_in": "Der FC Barcelona wurde am 29. November 1899 von Joan Gamper gegründet.",
        "ground_truth": "Der FC Barcelona wurde von Joan Gamper gegründet.",
    },
    {
        "type": "control",
        "label": "Korrektes Bundesliga-Land",
        "question": "In welchem Land spielt die Bundesliga?",
        "answer_in": "Die Bundesliga wird in Deutschland gespielt.",
        "ground_truth": "Die Bundesliga wird in Deutschland gespielt.",
    },
    {
        "type": "control",
        "label": "Korrekte Anzahl Bundesliga-Teams",
        "question": "Wie viele Teams spielen in der Bundesliga?",
        "answer_in": "In der Bundesliga spielen 18 Vereine.",
        "ground_truth": "In der Bundesliga spielen 18 Vereine.",
    },
    {
        "type": "control",
        "label": "Korrekte Real Madrid CL-Titel",
        "question": "Wie viele Champions-League-Titel hat Real Madrid gewonnen?",
        "answer_in": "Real Madrid hat 15 Champions-League-Titel gewonnen und ist damit Rekordsieger.",
        "ground_truth": "Real Madrid hat 15 Champions-League-Titel gewonnen.",
    },
    {
        "type": "control",
        "label": "Korrektes Bayern-Gründungsjahr (kurz)",
        "question": "In welchem Jahr wurde Bayern München gegründet?",
        "answer_in": "Bayern München wurde 1900 gegründet.",
        "ground_truth": "Bayern München wurde 1900 gegründet.",
    },
    {
        "type": "control",
        "label": "Korrekte Aussage Juventus Heimstadion",
        "question": "Wo spielt Juventus seine Heimspiele?",
        "answer_in": "Juventus spielt seine Heimspiele im Allianz Stadium in Turin.",
        "ground_truth": "Juventus spielt im Allianz Stadium in Turin.",
    },

    # ── Out-of-domain ────────────────────────────────────────────────────────
    {
        "type": "out_of_domain",
        "label": "Formel-1-Frage",
        "question": "Wer hat die Formel-1-WM 2023 gewonnen?",
        "answer_in": "Die Formel-1-WM 2023 wurde von Max Verstappen gewonnen.",
        "ground_truth": "Diese Frage liegt außerhalb der Fußball-Domäne.",
    },
]

CATCH_THRESHOLD = 0.6  # confidence unter diesem Wert = Halluzination erkannt

EMPTY_BASE = {
    "route": "", "route_reason": "", "sql": "", "sql_result": "",
    "sub_answers": [], "steps": [], "active_agent": "", "confidence": 0.0,
}


def _ground_truth_overlap(answer_out: str, ground_truth: str) -> bool:
    """Einfache Heuristik: enthält die korrigierte Antwort zentrale Begriffe aus ground_truth?"""
    gt_words = set(w.lower() for w in ground_truth.split() if len(w) >= 4)
    ans_words = set(w.lower() for w in answer_out.split() if len(w) >= 4)
    if not gt_words:
        return False
    overlap = gt_words & ans_words
    return len(overlap) / len(gt_words) >= 0.3


if __name__ == "__main__":
    print("Validation Agent Catch Rate — Evaluation startet...\n")

    results = []

    for tc in TEST_CASES:
        state = {**EMPTY_BASE, "question": tc["question"], "answer": tc["answer_in"]}
        result = validator_agent(state)

        confidence = result["confidence"]
        answer_out = result["answer"]
        answer_changed = answer_out.strip() != tc["answer_in"].strip()
        caught = confidence < CATCH_THRESHOLD
        gt_overlap = _ground_truth_overlap(answer_out, tc["ground_truth"])

        results.append({
            **tc,
            "confidence":     confidence,
            "answer_out":     answer_out,
            "answer_changed": answer_changed,
            "caught":         caught,
            "gt_overlap":     gt_overlap,
        })

        bar = int(confidence * 20) * "█" + int((1 - confidence) * 20) * "░"

        if tc["type"] == "hallucination":
            flag = "ERKANNT" if caught else "DURCHGERUTSCHT"
        elif tc["type"] == "control":
            flag = "OK" if not caught else "FALSE POSITIVE"
        else:  # out_of_domain
            flag = "ERKANNT" if caught else "DURCHGERUTSCHT"

        print(f"  [{flag:>14}] {bar} {confidence:.0%}  {tc['label']}")

    # ─────────────────────────────────────────────
    # METRIKEN
    # ─────────────────────────────────────────────
    hall_results = [r for r in results if r["type"] == "hallucination"]
    ctrl_results  = [r for r in results if r["type"] == "control"]
    ood_results   = [r for r in results if r["type"] == "out_of_domain"]

    catch_rate       = sum(r["caught"] for r in hall_results) / len(hall_results) if hall_results else 0.0
    correction_rate  = sum(r["answer_changed"] for r in hall_results) / len(hall_results) if hall_results else 0.0
    false_pos_rate   = sum(r["caught"] for r in ctrl_results) / len(ctrl_results) if ctrl_results else 0.0
    ood_catch_rate   = sum(r["caught"] for r in ood_results) / len(ood_results) if ood_results else 0.0

    print("\n" + "=" * 70)
    print("ERGEBNISSE")
    print("=" * 70)
    print(f"Halluzinationen getestet:   {len(hall_results)}")
    print(f"Kontrollfälle getestet:     {len(ctrl_results)}")
    print(f"Out-of-Domain getestet:     {len(ood_results)}")
    print()
    print(f"Catch Rate          (conf<{CATCH_THRESHOLD}):  {catch_rate:.1%}  — Halluzinationen erkannt")
    print(f"Auto-Correction Rate:       {correction_rate:.1%}  — Antworten tatsächlich verändert")
    print(f"False Positive Rate:        {false_pos_rate:.1%}  — korrekte Antworten fälschlich markiert")
    print(f"Out-of-Domain Catch Rate:   {ood_catch_rate:.1%}  — Off-topic erkannt")

    missed = [r for r in hall_results if not r["caught"]]
    if missed:
        print(f"\nDurchgerutschte Halluzinationen ({len(missed)}):")
        for r in missed:
            print(f"  [{r['confidence']:.0%}] {r['label']}: {r['answer_in'][:60]}")

    fp_cases = [r for r in ctrl_results if r["caught"]]
    if fp_cases:
        print(f"\nFalse Positives ({len(fp_cases)}):")
        for r in fp_cases:
            print(f"  [{r['confidence']:.0%}] {r['label']}: {r['answer_in'][:60]}")

