"""
build_database.py

Das zentrale Orchestrator-Skript. Es bereitet das gesamten Daten vor:
1. OpenLigaDB abrufen (CSV) KPIs Platz, Punkte, Siege, Tore, Gegentore
2. StatsBomb-Metriken berechnen (Saison-JSONs) KPIs Chancen-Verwertung, Druck-Resistenz
3. Wikipedia-Wortwolken
"""

import os
import sys
from pathlib import Path

# Importiere die Hauptfunktionen deiner Pipelines
from prepare_openliga_data import main as run_openliga_pipeline
from statsbomb_collector_statistics_tab import generiere_und_speichere_statsbomb_kpis
from haeufigkeiten_wortwolken import main as run_wortwolken_pipeline

def main():
    # Wechsle zum Hauptverzeichnis (Parent von Tab1_Statistiken)
    # Damit alle Pfade korrekt berechnet werden
    skript_ordner = Path(__file__).resolve().parent
    haupt_verzeichnis = skript_ordner.parent
    os.chdir(haupt_verzeichnis)
    print(f" Arbeitsverzeichnis: {os.getcwd()}\n")
    
    print(" Starte die Daten-Vorbereitung ... \n")
    
    # -------------------------------------------------------------
    # 1. OpenLigaDB Daten holen
    # -------------------------------------------------------------
    print("--- [1/3] OpenLigaDB Pipeline ---")
    run_openliga_pipeline()

    # -------------------------------------------------------------
    # 2. StatsBomb Daten berechnen & einheitlich benennen (Schritt A & B)
    # -------------------------------------------------------------
    print("\n--- [2/3] StatsBomb Pipeline ---")
    # Wir bereiten alle Saisons vor, damit die UI für jedes Label eine Datei findet!
    # Die Dateinamen passen exakt zu deinen OpenLigaDB-Labels (mit Unterstrich statt /)
    generiere_und_speichere_statsbomb_kpis("2022/23", "data/tab1_statistik/statsbomb_kpis_2022_23.json")
    generiere_und_speichere_statsbomb_kpis("2023/24", "data/tab1_statistik/statsbomb_kpis_2023_24.json")
    generiere_und_speichere_statsbomb_kpis("2024/25", "data/tab1_statistik/statsbomb_kpis_2024_25.json")
    
    # -------------------------------------------------------------
    # 3. Wikipedia Wortwolken
    # -------------------------------------------------------------
    print("\n--- [3/3] Wikipedia Wortwolken ---")
    run_wortwolken_pipeline()

    print("\n✓ Alle Backend-Daten sind in 'data/tab1_statistik/' erfolgreich generiert!")

if __name__ == "__main__":
    main()