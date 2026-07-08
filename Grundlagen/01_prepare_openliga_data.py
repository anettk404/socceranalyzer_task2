"""
01_prepare_openliga_data.py

Lädt mehrere Bundesliga-Saisons von OpenLigaDB, bereinigt die Daten,
berechnet die finale Platzierung und speichert das Ergebnis als CSV
für den Statistik-Tab in Streamlit.

Diese Datei wurde aus dem Notebook "01_prepare_openliga_data.ipynb" entwickelt, um das Programmieren mit .py-Dateien zu üben.
Sie hat keine direkte Funktion im Streamlit-Frontend und ist nur als Übung zu verstehen.

Ausführen:
    uv run python 01_prepare_openliga_data.py
"""

import requests
import pandas as pd


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
# Hauptablauf
# ─────────────────────────────────────────────────────────────
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

    # Schritt 4: Als CSV speichern
    ausgabe_pfad = "openliga_tabellen.csv"
    df_gesamt.to_csv(ausgabe_pfad, index=False)
    print(f"  ✓ Gespeichert unter: {ausgabe_pfad}")

    print("\nVorschau:")
    print(df_gesamt.head(10).to_string(index=False))


if __name__ == "__main__":
    main()