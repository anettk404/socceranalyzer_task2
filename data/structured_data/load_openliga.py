"""OpenLigaDB loader — mehrere Ligen und Saisons: Matches & Tabelle."""
import sqlite3
import requests
import pandas as pd


OPENLIGA_BASE = "https://api.openligadb.de"
DB_PATH = "data/soccer.db"

OPENLIGA_COMPETITIONS = [
    {"league": "1. Bundesliga", "shortcut": "bl1", "seasons": [2015, 2022, 2023, 2024]},
    {"league": "Premier League", "shortcut": "PL", "seasons": [2015]},
    {"league": "Premier League", "shortcut": "pl1", "seasons": [2023]},
    {"league": "La Liga", "shortcut": "ll", "seasons": [2016]},
    {"league": "La Liga", "shortcut": "la", "seasons": [2022]},
    {"league": "Serie A", "shortcut": "SA", "seasons": [2015]},
    {"league": "Serie A", "shortcut": "seriea19", "seasons": [2019]},
    {"league": "Ligue 1", "shortcut": "lg1", "seasons": [2017]},
    {"league": "Ligue 1", "shortcut": "Lig", "seasons": [2018]},
]


def _season_label(start_year: int) -> str:
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def fetch_matches(league_name: str, league_code: str, season: int) -> pd.DataFrame:
    url = f"{OPENLIGA_BASE}/getmatchdata/{league_code}/{season}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for m in raw:
        g = m.get("matchResults", [])
        final = next((r for r in g if r.get("resultOrderID") == 2), g[0] if g else None)
        rows.append({
            "match_id": m["matchID"],
            "league": league_name,
            "league_code": league_code,
            "season": _season_label(season),
            "season_start_year": season,
            "match_datetime": m.get("matchDateTimeUTC"),
            "matchday": m.get("group", {}).get("groupOrderID"),
            "home_team": m["team1"]["teamName"],
            "away_team": m["team2"]["teamName"],
            "home_goals": final["pointsTeam1"] if final else None,
            "away_goals": final["pointsTeam2"] if final else None,
            "is_finished": m.get("matchIsFinished", False),
        })
    return pd.DataFrame(rows)


def fetch_table(league_name: str, league_code: str, season: int) -> pd.DataFrame:
    url = f"{OPENLIGA_BASE}/getbltable/{league_code}/{season}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    rows = []
    for i, t in enumerate(raw, start=1):
        rows.append({
            "position": i,
            "league": league_name,
            "league_code": league_code,
            "season": _season_label(season),
            "season_start_year": season,
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

    for competition in OPENLIGA_COMPETITIONS:
        league_name = competition["league"]
        league_code = competition["shortcut"]
        for season in competition["seasons"]:
            print(f"  Lade OpenLigaDB {league_name} {season}/{str(season + 1)[-2:]} ({league_code})...")
            matches = fetch_matches(league_name, league_code, season)
            if not matches.empty:
                all_matches.append(matches)
                print(f"    → {len(matches)} Matches")

            table = fetch_table(league_name, league_code, season)
            if not table.empty:
                all_tables.append(table)
                print(f"    → {len(table)} Tabellenplätze")

    df_matches = pd.concat(all_matches, ignore_index=True) if all_matches else pd.DataFrame()
    df_matches.to_sql("openliga_matches", con, if_exists="replace", index=False)
    print(f"  ✓ openliga_matches: {len(df_matches)} Zeilen gesamt")

    df_tables = pd.concat(all_tables, ignore_index=True) if all_tables else pd.DataFrame()
    df_tables.to_sql("openliga_table", con, if_exists="replace", index=False)
    print(f"  ✓ openliga_table: {len(df_tables)} Zeilen gesamt")
