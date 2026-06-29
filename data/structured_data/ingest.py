"""Main ingestion script for OpenLigaDB, StatsBomb and Wikipedia wordcloud data."""
import importlib.util
import json
import sqlite3
import os
import sys
from pathlib import Path

# resolve project paths independent of current working directory
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = DATA_DIR.parent
DB_PATH = DATA_DIR / "soccer.db"
WORDCLOUD_OUTPUT_PATH = DATA_DIR / "haeufigkeiten_wortwolken.json"

# ensure data/ exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# import modules from this directory
sys.path.insert(0, os.path.dirname(__file__))
import load_openliga
import load_statsbomb


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    print(f"Verbinde mit {DB_PATH} ...")
    con = sqlite3.connect(DB_PATH)

    try:
        print("\n[1/3] OpenLigaDB")
        load_openliga.save_to_db(con)

        print("\n[2/3] StatsBomb")
        load_statsbomb.save_to_db(con)

        con.commit()

        # Zusammenfassung
        print("\nDatenbank-Übersicht:")
        cur = con.cursor()
        for table in ["openliga_matches", "openliga_table", "statsbomb_matches", "statsbomb_events"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:<25} {count:>8} Zeilen")
        # Saisons pro Tabelle anzeigen
        print("\nSaisons in der DB:")
        for table, col in [("openliga_matches", "season"), ("statsbomb_matches", "season_label")]:
            cur.execute(f"SELECT DISTINCT {col} FROM {table} ORDER BY {col}")
            saisons = [r[0] for r in cur.fetchall()]
            print(f"  {table:<25} {saisons}")

    finally:
        con.close()

    print("\n[3/3] Wikipedia Wortwolken")
    wordcloud_module = _load_module_from_path(
        "wordcloud_ingestion",
        DATA_DIR / "haeufigkeiten_wortwolken.py",
    )
    wordcloud_module.main()

    if WORDCLOUD_OUTPUT_PATH.exists():
        with WORDCLOUD_OUTPUT_PATH.open("r", encoding="utf-8") as handle:
            wordcloud_data = json.load(handle)
        print(
            f"  Wortwolken-Datei: {WORDCLOUD_OUTPUT_PATH} "
            f"({len(wordcloud_data)} Teams)"
        )
    else:
        print(f"  Warnung: Wortwolken-Datei nicht gefunden: {WORDCLOUD_OUTPUT_PATH}")

    print(f"\nFertig. Datenbank gespeichert unter: {DB_PATH}")


if __name__ == "__main__":
    main()
