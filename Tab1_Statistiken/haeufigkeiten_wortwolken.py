"""
haeufigkeiten_wortwolken.py

Erzeugt eine JSON-Datei mit den Worthäufigkeiten aus Wikipedia-Artikeln
für alle nationalen Fußballligen.

Ausführen:
    uv run python haeufigkeiten_wortwolken.py
"""

import json
import os
from collections import Counter
import spacy
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# Schritt 1: Wikipedia-Artikel zu allen fünf Ligen aus wikipedia_articles.json beziehen
# ─────────────────────────────────────────────────────────────
# Wesentliche Schritte: 
# 1. JSON-Datei öffnen und einlesen
# 2. Durch jeden Artikel-Eintrag iterieren
# 3. Aus jedem Eintrag den Teamnamen und den Text holen
# 4. Ein Dictionary {team_name: text} zurückgeben


def lade_wiki_texte_aus_json(pfad: str) -> dict:
    """
    Liest die von wikipedia_collector.py bereits gesammelten Artikel
    (alle 5 europäischen Top-Ligen) aus der JSON-Datei ein.
    Bevorzugt den deutschen Text (text_de), fällt sonst auf
    den englischen Text (text_en) zurück.
    """
    with open(pfad, "r", encoding="utf-8") as f:
        artikel = json.load(f)

    texte = {}
    for eintrag in artikel:
        team_name = eintrag.get("team", "")
        text = eintrag.get("text_de", "").strip() or eintrag.get("text_en", "")
        if team_name and text:
            texte[team_name] = text
            print(f"✓ {team_name} geladen ({len(text)} Zeichen)")
        else:
            print(f"✗ Kein Text für: {team_name or '?'}")

    return texte



# ─────────────────────────────────────────────────────────────
# Schritt 2: Preprocessing (Bereinigen) und Zählen
# ─────────────────────────────────────────────────────────────
def bereinige_und_zaehle(texte: dict) -> dict:
    """Bereinigt die Texte (entfernt Stopwörter, Satzzeichen, Zahlen, Leerzeichen)

    und zählt die 100 häufigsten Lemmata pro Verein.
    """
    print("Lade spaCy-Modell für die Textbereinigung...")
    try:
        nlp = spacy.load("de_core_news_sm")
    except OSError:
        print(
            "Fehler: Das spaCy-Modell 'de_core_news_sm' ist nicht installiert."
        )
        print("Bitte installiere es mit: uv run python -m spacy download de_core_news_sm")
        raise

    ergebnis = {}

    for team, text in texte.items():
        print(f"Verarbeite Text für: {team}...")
        doc = nlp(text)

        # Schritt 2: Tokenisierung & Filterung (keine Stopwörter, Satzzeichen, Zahlen, Spaces)
        woerter = [
            token.lemma_.lower()
            for token in doc
            if not token.is_stop
            and not token.is_punct
            and not token.like_num
            and not token.is_space
            and len(token.text) > 2
        ]

        # Schritt 3: Worthäufigkeiten ermitteln (Top 100)
        top_woerter = dict(Counter(woerter).most_common(100))
        ergebnis[team] = top_woerter

    return ergebnis


# ─────────────────────────────────────────────────────────────
# Schritt 3: Speichern der Ergebnisse
# ─────────────────────────────────────────────────────────────

def speichere_haeufigkeiten(daten: dict, ausgabe_datei: str):
    """Speichert das berechnete Dictionary als JSON-Datei ab."""
    # Ermittelt den Ordner-Pfad aus dem übergebenen Dateipfad
    ordner = os.path.dirname(ausgabe_datei)
    
    # Erstellt den Ordner (und alle darüber liegenden), falls nicht vorhanden
    if ordner and not os.path.exists(ordner):
        os.makedirs(ordner, exist_ok=True)
        print(f"✓ Ordner erstellt: {ordner}")

    with open(ausgabe_datei, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)
    print(f"✓ Ergebnisse erfolgreich gespeichert in: {ausgabe_datei}")

# ─────────────────────────────────────────────────────────────
# Hauptablauf (Main)
# ─────────────────────────────────────────────────────────────
def main():
    
    # 1. Ermittle den Ordner, in dem dieses Skript liegt (Tab1_Statistiken)
    skript_ordner = Path(__file__).resolve().parent
    
    # 2. Gehe eine Ebene höher ins Hauptverzeichnis (Root) und setze den Pfad auf data/tab1_statistik/
    haupt_verzeichnis = skript_ordner.parent
    eingabe_pfad = str(haupt_verzeichnis / "data" / "wikipedia_articles.json")
    ausgabe_pfad = str(haupt_verzeichnis / "data" / "tab1_statistik" / "haeufigkeiten_wortwolken.json")

    print("=== Starte Wikipedia NLP-Pipeline ===")
    print(f"Ziel-Pfad: {ausgabe_pfad}")
    print(f"Lese Artikel aus: {eingabe_pfad}")

    # 1. Schritt: Wikipedia-Texte laden
    rohtext_daten = lade_wiki_texte_aus_json(eingabe_pfad)

    if not rohtext_daten:
        print("Abbruch: Keine Texte von Wikipedia geladen.")
        return
    
    print(f"✓ {len(rohtext_daten)} Teams aus allen Ligen geladen")

    # 2. & 3. Schritt: Bereinigen und Häufigkeiten zählen
    haeufigkeiten_daten = bereinige_und_zaehle(rohtext_daten)

    # 5. Schritt: Daten als JSON exportieren
    speichere_haeufigkeiten(haeufigkeiten_daten, ausgabe_pfad)

    print("=== Pipeline erfolgreich beendet ===")


if __name__ == "__main__":
    main()