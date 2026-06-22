"""
prepare_openliga_data.py

Lädt mehrere Bundesliga-Saisons von OpenLigaDB, bereinigt die Daten,
berechnet die finale Platzierung und speichert das Ergebnis als CSV
für den Statistik-Tab in Streamlit.

Ausführen:
    uv run python prepare_openliga_data.py
"""

import requests
import pandas as pd
from pathlib import Path
import json


# ─────────────────────────────────────────────────────────────
# Schritt 1: Eine Saison laden
# ─────────────────────────────────────────────────────────────
def hole_tabelle(start_jahr: int) -> pd.DataFrame:
    """Lädt die Tabelle einer Bundesliga-Saison von OpenLigaDB."""
    url = f"https://api.openligadb.de/getbltable/bl1/{start_jahr}"
    daten = requests.get(url).json()
    df = pd.DataFrame(daten)
    # Lesbares Label für den Filter erzeugen, z.B. "2023/24"
    df["saison_label"] = f"{start_jahr}/{str(start_jahr + 1)[-2:]}"
    return df


# ─────────────────────────────────────────────────────────────
# Schritt 2: Unnötige Spalten entfernen
# ─────────────────────────────────────────────────────────────
def bereinige_spalten(df: pd.DataFrame) -> pd.DataFrame:
    """Behält nur die für das Dashboard relevanten Spalten."""
    relevante_spalten = [
        "teamName",
        "saison_label",
        "points",
        "goals",
        "opponentGoals",
        "goalDiff",
        "won",
        "lost",
        "draw",
    ]
    return df[relevante_spalten]


# ─────────────────────────────────────────────────────────────
# Schritt 3: Finale Platzierung berechnen
# ─────────────────────────────────────────────────────────────
def berechne_platzierung(df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet die Tabellenplatzierung pro Saison.
    Sortierregel: erst Punkte, bei Gleichstand Tordifferenz.
    """
    df_mit_platz = []
    for saison in df["saison_label"].unique():
        df_saison = df[df["saison_label"] == saison].copy()
        df_saison = df_saison.sort_values(
            ["points", "goalDiff"], ascending=[False, False]
        ).reset_index(drop=True)
        df_saison["platzierung"] = df_saison.index + 1
        df_mit_platz.append(df_saison)
    return pd.concat(df_mit_platz, ignore_index=True)

# ─────────────────────────────────────────────────────────────
# Barcharts erstellen aus KPIs oben
# ─────────────────────────────────────────────────────────────

def erstelle_barchart_daten(df: pd.DataFrame) -> dict:
    """
    Erstellt die Datenbasis für einfache Barcharts im Streamlit-Dashboard.
    """
    
    # Nur aktuellste Saison
    aktuelle_saison = df["saison_label"].max()
    df_saison = df[df["saison_label"] == aktuelle_saison]

    return {
        "punkte_pro_team": {
            "labels": df_saison["teamName"].tolist(),
            "values": df_saison["points"].tolist()
        },

        "tore_pro_team": {
            "labels": df_saison["teamName"].tolist(),
            "values": df_saison["goals"].tolist()
        },

        "siege_pro_team": {
            "labels": df_saison["teamName"].tolist(),
            "values": df_saison["won"].tolist()
        },

        "gegentore_pro_team": {
            "labels": df_saison["teamName"].tolist(),
            "values": df_saison["opponentGoals"].tolist()
        }
    }

def speichere_barchart_daten(chart_daten: dict):
    skript_ordner = Path(__file__).resolve().parent
    haupt_verzeichnis = skript_ordner.parent

    data_ordner = haupt_verzeichnis / "data" / "tab1_statistik"
    data_ordner.mkdir(parents=True, exist_ok=True)

    chart_datei = data_ordner / "openliga_barcharts.json"

    with open(chart_datei, "w", encoding="utf-8") as f:
        json.dump(chart_daten, f, indent=4, ensure_ascii=False)

    print(f"✓ Barchart-Daten gespeichert: {chart_datei}")


# ──────────────────────────────────────────────────────────
# Hauptablauf
# ──────────────────────────────────────────────────────────
def main():
    # Schritt 1: Mehrere Saisons laden und zusammenführen
    print("Lade Saisons von OpenLigaDB...")
    saisons = [2022, 2023, 2024]
    df_liste = [hole_tabelle(jahr) for jahr in saisons]
    df_gesamt = pd.concat(df_liste, ignore_index=True)
    print(f"  ✓ {len(df_gesamt)} Zeilen aus {len(saisons)} Saisons geladen")

    # Schritt 2: Unnötige Spalten löschen
    df_gesamt = bereinige_spalten(df_gesamt)
    print(f"  ✓ Spalten bereinigt: {list(df_gesamt.columns)}")

    # Schritt 3: Finale Platzierung berechnen
    df_gesamt = berechne_platzierung(df_gesamt)
    print("  ✓ Platzierung berechnet")

    # Schritt 4: Barchart-Daten erzeugen
    chart_daten = erstelle_barchart_daten(df_gesamt)
    print("  ✓ Barchart-Daten erzeugt")

   
    # Schritt 5: CSV im data-Ordner speichern
    skript_ordner = Path(__file__).resolve().parent
    haupt_verzeichnis = skript_ordner.parent

    data_ordner = haupt_verzeichnis / "data" / "tab1_statistik"
    data_ordner.mkdir(parents=True, exist_ok=True)

    csv_datei = data_ordner / "openliga_tabellen.csv"

    df_gesamt.to_csv(csv_datei, index=False)

    print(f"✓ CSV gespeichert unter: {csv_datei}")

# Barchart-JSON speichern
    skript_ordner = Path(__file__).resolve().parent
    haupt_verzeichnis = skript_ordner.parent

    data_ordner = haupt_verzeichnis / "data" / "tab1_statistik"
    data_ordner.mkdir(parents=True, exist_ok=True)

    chart_datei = data_ordner / "openliga_barcharts.json"

    with open(chart_datei, "w", encoding="utf-8") as f:
        json.dump(chart_daten, f, indent=4, ensure_ascii=False)

    print(f"✓ Barchart-Daten gespeichert: {chart_datei}")

    print("\nVorschau:")
    print(df_gesamt.head(10).to_string(index=False))


if __name__ == "__main__":
    main()