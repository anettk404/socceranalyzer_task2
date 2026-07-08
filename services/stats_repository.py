"""
Titel: Statistik-Repository
Beschreibung: Dieses Modul liest Filteroptionen und OpenLigaDB-KPIs aus der lokalen
              soccer.db und liefert die Daten für die Statistik-Ansicht.
Wichtige Inhalte: Ligafilter, Saisonfilter, Teamfilter, KPI-Lookup aus SQLite.
Autorin: Annette Kufner

Hinweis: Dieses Skript wurde mithilfe von Gemini, Claude und Codex erstellt.
"""

import sqlite3
from pathlib import Path

from services.stats_constants import DB_PATH
from services.stats_mapping_service import normalize_openliga_season_label, normalize_openliga_team_name

# Fallback-Werte sorgen dafür, dass die UI auch ohne fertige Datenbank nutzbar bleibt.
DEFAULT_LIGA_OPTIONS = ["Alle Ligen", "1. Bundesliga", "La Liga", "Premier League", "Serie A", "Ligue 1"]
FALLBACK_TEAM_OPTIONS_BY_LIGA = {
    "Alle Ligen": ["Alle Teams"],
    "1. Bundesliga": [
        "Alle Teams", "FC Bayern München", "Borussia Dortmund", "Bayer 04 Leverkusen", "RB Leipzig",
        "VfB Stuttgart", "Eintracht Frankfurt", "SC Freiburg", "TSG Hoffenheim", "VfL Wolfsburg",
        "Borussia Mönchengladbach", "FC Augsburg", "Mainz 05", "Werder Bremen", "1. FC Heidenheim",
        "1. FC Union Berlin", "VfL Bochum", "SV Darmstadt 98",
    ],
    "La Liga": ["Alle Teams", "Real Madrid", "FC Barcelona", "Atlético Madrid", "Sevilla FC", "Villarreal CF", "Real Sociedad", "Athletic Club", "Valencia CF", "Celta Vigo"],
    "Premier League": ["Alle Teams", "Manchester City", "Liverpool FC", "Arsenal FC", "Chelsea FC", "Manchester United", "Tottenham Hotspur", "Newcastle United", "Aston Villa", "Leicester City"],
    "Serie A": ["Alle Teams", "Inter Mailand", "Juventus Turin", "AC Mailand", "AS Rom", "SSC Neapel", "Atalanta Bergamo", "Lazio Rom", "Fiorentina", "Bologna FC"],
    "Ligue 1": ["Alle Teams", "Paris Saint-Germain", "Olympique Marseille", "Olympique Lyon", "AS Monaco", "LOSC Lille", "Stade Rennais", "AJ Auxerre", "RC Lens", "FC Nantes"],
}

FALLBACK_ALL_TEAMS = ["Alle Teams", *sorted({
    team
# Hilfsfunktion zum Prüfen, welche Spalten in der aktuellen SQLite-Tabelle vorhanden sind.
    for liga, teams in FALLBACK_TEAM_OPTIONS_BY_LIGA.items()
    if liga != "Alle Ligen"
    for team in teams
    if team != "Alle Teams"
})]


def _table_columns(table_name: str, db_path: Path | None = None) -> set[str]:
    database_path = db_path or DB_PATH
    if not database_path.exists():
        return set()
    with sqlite3.connect(database_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def get_available_leagues(db_path: Path | None = None) -> list[str]:
    database_path = db_path or DB_PATH
    if not database_path.exists():
        return DEFAULT_LIGA_OPTIONS

    columns = _table_columns("openliga_table", db_path=database_path)
    if "league" not in columns:
        return DEFAULT_LIGA_OPTIONS

    with sqlite3.connect(database_path) as conn:
        leagues = [row[0] for row in conn.execute("SELECT DISTINCT league FROM openliga_table ORDER BY league").fetchall()]

    return ["Alle Ligen", *leagues] if leagues else DEFAULT_LIGA_OPTIONS


def get_available_seasons(liga: str, db_path: Path | None = None) -> list[str]:
    database_path = db_path or DB_PATH
    if not database_path.exists():
        return ["Alle Saisons", "2024/25", "2023/24", "2022/23"]

    columns = _table_columns("openliga_table", db_path=database_path)
    if "season" not in columns:
        return ["Alle Saisons", "2024/25", "2023/24", "2022/23"]

    where_sql = ""
    params: tuple = ()
    if liga not in (None, "", "Alle Ligen") and "league" in columns:
        where_sql = " WHERE league = ?"
        params = (liga,)

    with sqlite3.connect(database_path) as conn:
        seasons = [
            row[0]
            for row in conn.execute(
                f"SELECT DISTINCT season FROM openliga_table{where_sql} ORDER BY season DESC",
                params,
            ).fetchall()
        ]

    return ["Alle Saisons", *seasons] if seasons else ["Alle Saisons"]


def get_available_teams(liga: str, saison: str, db_path: Path | None = None) -> list[str]:
    database_path = db_path or DB_PATH
    if not database_path.exists():
        if liga == "Alle Ligen":
            return FALLBACK_ALL_TEAMS
        return FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])

    columns = _table_columns("openliga_table", db_path=database_path)
    if "team" not in columns:
        if liga == "Alle Ligen":
            return FALLBACK_ALL_TEAMS
        return FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])

    where_clauses = []
    params: list[str] = []
    if liga not in (None, "", "Alle Ligen") and "league" in columns:
        where_clauses.append("league = ?")
        params.append(liga)
    normalized_season = normalize_openliga_season_label(saison)
    if normalized_season and "season" in columns:
        where_clauses.append("season = ?")
        params.append(normalized_season)

    query = "SELECT DISTINCT team FROM openliga_table"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY team"

    with sqlite3.connect(database_path) as conn:
        teams = [row[0] for row in conn.execute(query, tuple(params)).fetchall()]

    if teams:
        return ["Alle Teams", *teams]

    if liga == "Alle Ligen":
        return FALLBACK_ALL_TEAMS
    return FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])


def load_top_kpis_from_db(liga: str, saison: str, team_name: str, db_path: Path | None = None) -> dict | None:
    """Liest Platz, Punkte, Siege, Niederlagen, Tore und Gegentore aus soccer.db."""
    # Die Statistik-Ansicht benötigt genau einen Datensatz passend zu den Filtern.
    database_path = db_path or DB_PATH
    if not database_path.exists():
        return None

    columns = _table_columns("openliga_table", db_path=database_path)
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row

        where_clauses = []
        params: list[str] = []

        if liga not in (None, "", "Alle Ligen") and "league" in columns:
            where_clauses.append("league = ?")
            params.append(liga)

        normalized_season = normalize_openliga_season_label(saison)
        if normalized_season and "season" in columns:
            where_clauses.append("season = ?")
            params.append(normalized_season)

        selected_team = normalize_openliga_team_name(team_name)
        if selected_team:
            where_clauses.append("team = ?")
            params.append(selected_team)

        select_fields = [
            "league" if "league" in columns else "'' AS league",
            "season" if "season" in columns else "'' AS season",
            "team",
            "position",
            "points",
            "matches" if "matches" in columns else "0 AS matches",
            "won",
            "lost",
            "goals_for",
            "goals_against",
        ]
        query = f"SELECT {', '.join(select_fields)} FROM openliga_table"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        order_by = ["position ASC"]
        if "season_start_year" in columns:
            order_by.insert(0, "season_start_year DESC")
        elif "season" in columns:
            order_by.insert(0, "season DESC")
        query += " ORDER BY " + ", ".join(order_by) + " LIMIT 1"

        row = conn.execute(query, tuple(params)).fetchone()

    if row is None:
        return None

    return {
        "league": row["league"] if "league" in row.keys() else liga,
        "season": row["season"] if "season" in row.keys() else saison,
        "team": row["team"],
        "Platz": int(row["position"]),
        "Punkte": int(row["points"]),
        "Spiele": int(row["matches"]),
        "Siege": int(row["won"]),
        "Unentschieden": max(int(row["matches"]) - int(row["won"]) - int(row["lost"]), 0),
        "Niederlagen": int(row["lost"]),
        "Tore": int(row["goals_for"]),
        "Gegentore": int(row["goals_against"]),
    }
