"""OpenLigaDB loader — Bundesliga 2023/24: Matches & Tabelle."""
import sqlite3
import requests
import pandas as pd


OPENLIGA_BASE = "https://api.openligadb.de"
LEAGUE = "bl1"
SEASON = "2023"
DB_PATH = "data/soccer.db"


def fetch_matches() -> pd.DataFrame:
    url = f"{OPENLIGA_BASE}/getmatchdata/{LEAGUE}/{SEASON}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for m in raw:
        g = m.get("matchResults", [])
        # take final result (orderId 2) or first available
        final = next((r for r in g if r.get("resultOrderID") == 2), g[0] if g else None)
        rows.append({
            "match_id": m["matchID"],
            "match_datetime": m.get("matchDateTimeUTC"),
            "matchday": m.get("group", {}).get("groupOrderID"),
            "home_team": m["team1"]["teamName"],
            "away_team": m["team2"]["teamName"],
            "home_goals": final["pointsTeam1"] if final else None,
            "away_goals": final["pointsTeam2"] if final else None,
            "is_finished": m.get("matchIsFinished", False),
        })
    return pd.DataFrame(rows)


def fetch_table() -> pd.DataFrame:
    url = f"{OPENLIGA_BASE}/getbltable/{LEAGUE}/{SEASON}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for i, t in enumerate(raw, start=1):
        rows.append({
            "position": i,
            "team": t["teamName"],
            "team_id": t["teamInfoId"],
            "matches": t["matches"],
            "won": t["won"],
            "draw": t["draw"],
            "lost": t["lost"],
            "goals_for": t["goals"],
            "goals_against": t["opponentGoals"],
            "goal_diff": t["goalDiff"],
            "points": t["points"],
        })
    return pd.DataFrame(rows)


def save_to_db(con: sqlite3.Connection) -> None:
    print("  Lade OpenLigaDB Matches...")
    matches = fetch_matches()
    matches.to_sql("openliga_matches", con, if_exists="replace", index=False)
    print(f"    → {len(matches)} Matches gespeichert")

    print("  Lade OpenLigaDB Tabelle...")
    table = fetch_table()
    table.to_sql("openliga_table", con, if_exists="replace", index=False)
    print(f"    → {len(table)} Tabellenplätze gespeichert")
