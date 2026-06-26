"""OpenLigaDB loader — Bundesliga mehrere Saisons: Matches & Tabelle."""
import sqlite3
import requests
import pandas as pd


OPENLIGA_BASE = "https://api.openligadb.de"
LEAGUE = "bl1"
SEASONS = [2022, 2023, 2024]
DB_PATH = "data/soccer.db"


def fetch_matches(season: int) -> pd.DataFrame:
    url = f"{OPENLIGA_BASE}/getmatchdata/{LEAGUE}/{season}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for m in raw:
        g = m.get("matchResults", [])
        final = next((r for r in g if r.get("resultOrderID") == 2), g[0] if g else None)
        rows.append({
            "match_id": m["matchID"],
            "season": f"{season}/{str(season + 1)[-2:]}",
            "match_datetime": m.get("matchDateTimeUTC"),
            "matchday": m.get("group", {}).get("groupOrderID"),
            "home_team": m["team1"]["teamName"],
            "away_team": m["team2"]["teamName"],
            "home_goals": final["pointsTeam1"] if final else None,
            "away_goals": final["pointsTeam2"] if final else None,
            "is_finished": m.get("matchIsFinished", False),
        })
    return pd.DataFrame(rows)


def fetch_table(season: int) -> pd.DataFrame:
    url = f"{OPENLIGA_BASE}/getbltable/{LEAGUE}/{season}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for i, t in enumerate(raw, start=1):
        rows.append({
            "position": i,
            "season": f"{season}/{str(season + 1)[-2:]}",
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
    all_matches = []
    all_tables = []

    for season in SEASONS:
        print(f"  Lade OpenLigaDB {season}/{str(season + 1)[-2:]}...")
        matches = fetch_matches(season)
        all_matches.append(matches)
        print(f"    → {len(matches)} Matches")

        table = fetch_table(season)
        all_tables.append(table)
        print(f"    → {len(table)} Tabellenplätze")

    df_matches = pd.concat(all_matches, ignore_index=True)
    df_matches.to_sql("openliga_matches", con, if_exists="replace", index=False)
    print(f"  ✓ openliga_matches: {len(df_matches)} Zeilen gesamt")

    df_tables = pd.concat(all_tables, ignore_index=True)
    df_tables.to_sql("openliga_table", con, if_exists="replace", index=False)
    print(f"  ✓ openliga_table: {len(df_tables)} Zeilen gesamt")
