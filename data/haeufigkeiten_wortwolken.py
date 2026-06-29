"""
haeufigkeiten_wortwolken.py

Erzeugt eine JSON-Datei mit den Worthaeufigkeiten aus Wikipedia-Artikeln
fuer alle nationalen Fussballligen.

Ausfuehren:
    uv run python data/haeufigkeiten_wortwolken.py
"""

import json
import os
from collections import Counter
from pathlib import Path

import spacy


def lade_wiki_texte_aus_json(pfad: str) -> dict:
    """
    Liest die von wikipedia_collector.py bereits gesammelten Artikel
    (alle 5 europaeischen Top-Ligen) aus der JSON-Datei ein.
    Bevorzugt den deutschen Text (text_de), faellt sonst auf
    den englischen Text (text_en) zurueck.
    """
    with open(pfad, "r", encoding="utf-8") as f:
        artikel = json.load(f)

    texte = {}
    for eintrag in artikel:
        team_name = eintrag.get("team", "")
        text = eintrag.get("text_de", "").strip() or eintrag.get("text_en", "")
        if team_name and text:
            texte[team_name] = text
            print(f"{team_name} geladen ({len(text)} Zeichen)")
        else:
            print(f"Kein Text fuer: {team_name or '?'}")

    return texte


def bereinige_und_zaehle(texte: dict) -> dict:
    """Bereinigt Texte und zaehlt die 100 haeufigsten Lemmata pro Verein."""
    print("Lade spaCy-Modell fuer die Textbereinigung...")
    try:
        nlp = spacy.load("de_core_news_sm")
    except OSError:
        print("Fehler: Das spaCy-Modell 'de_core_news_sm' ist nicht installiert.")
        print("Bitte installiere es mit: uv run python -m spacy download de_core_news_sm")
        raise

    ergebnis = {}

    for team, text in texte.items():
        print(f"Verarbeite Text fuer: {team}...")
        doc = nlp(text)

        woerter = [
            token.lemma_.lower()
            for token in doc
            if not token.is_stop
            and not token.is_punct
            and not token.like_num
            and not token.is_space
            and len(token.text) > 2
        ]

        top_woerter = dict(Counter(woerter).most_common(100))
        ergebnis[team] = top_woerter

    return ergebnis


def speichere_haeufigkeiten(daten: dict, ausgabe_datei: str):
    """Speichert das berechnete Dictionary als JSON-Datei ab."""
    ordner = os.path.dirname(ausgabe_datei)

    if ordner and not os.path.exists(ordner):
        os.makedirs(ordner, exist_ok=True)
        print(f"Ordner erstellt: {ordner}")

    with open(ausgabe_datei, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)
    print(f"Ergebnisse erfolgreich gespeichert in: {ausgabe_datei}")


def main():
    # Dieses Skript liegt unter data/; daher ist parent der Projekt-Root.
    skript_ordner = Path(__file__).resolve().parent
    haupt_verzeichnis = skript_ordner.parent

    eingabe_pfad = str(haupt_verzeichnis / "data" / "wikipedia_articles.json")
    ausgabe_pfad = str(haupt_verzeichnis / "data" / "haeufigkeiten_wortwolken.json")

    print("=== Starte Wikipedia NLP-Pipeline ===")
    print(f"Ziel-Pfad: {ausgabe_pfad}")
    print(f"Lese Artikel aus: {eingabe_pfad}")

    rohtext_daten = lade_wiki_texte_aus_json(eingabe_pfad)

    if not rohtext_daten:
        print("Abbruch: Keine Texte von Wikipedia geladen.")
        return

    print(f"{len(rohtext_daten)} Teams aus allen Ligen geladen")

    haeufigkeiten_daten = bereinige_und_zaehle(rohtext_daten)
    speichere_haeufigkeiten(haeufigkeiten_daten, ausgabe_pfad)

    print("=== Pipeline erfolgreich beendet ===")


if __name__ == "__main__":
    main()
