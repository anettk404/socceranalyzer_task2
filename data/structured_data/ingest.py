"""Hauptscript: Lädt OpenLigaDB + StatsBomb Daten und speichert in SQLite."""
import sqlite3
import os
import sys

# sicherstellen dass data/ existiert
os.makedirs("data", exist_ok=True)
DB_PATH = "data/soccer.db"

# Module aus demselben Verzeichnis importieren
sys.path.insert(0, os.path.dirname(__file__))
import data.structured_data.load_openliga as load_openliga
import data.structured_data.load_statsbomb as load_statsbomb


def main():
    print(f"Verbinde mit {DB_PATH} ...")
    con = sqlite3.connect(DB_PATH)

    try:
        print("\n[1/2] OpenLigaDB — Bundesliga 2023/24")
        load_openliga.save_to_db(con)

        print("\n[2/2] StatsBomb — 1. Bundesliga 2023/24")
        load_statsbomb.save_to_db(con)

        con.commit()

        # Zusammenfassung
        print("\nDatenbank-Übersicht:")
        cur = con.cursor()
        for table in ["openliga_matches", "openliga_table", "statsbomb_matches", "statsbomb_events"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:<25} {count:>6} Zeilen")

    finally:
        con.close()

    print(f"\nFertig. Datenbank gespeichert unter: {DB_PATH}")


if __name__ == "__main__":
    main()
