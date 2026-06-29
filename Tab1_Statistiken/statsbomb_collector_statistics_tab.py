"""SQL helpers for StatsBomb KPIs used in the statistics tab."""

import difflib
import json
import sqlite3
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "soccer.db"
EXPORT_DIR = PROJECT_ROOT / "data" / "tab1_statistik"
TEAM_NAME_OVERRIDES = {
    "FC Bayern München": "Bayern Munich",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "TSG Hoffenheim": "Hoffenheim",
    "1. FC Heidenheim 1846": "Heidenheim",
    "SC Freiburg": "Freiburg",
    "FC Augsburg": "Augsburg",
    "1. FSV Mainz 05": "FSV Mainz 05",
    "VfL Bochum": "Bochum",
    "1. FC Köln": "FC Köln",
    "SV Darmstadt 98": "Darmstadt 98",
    "FC Barcelona": "Barcelona",
    "Sevilla FC": "Sevilla",
    "Villarreal CF": "Villarreal",
    "Valencia CF": "Valencia",
    "Juventus Turin": "Juventus",
    "Inter Mailand": "Inter",
    "AC Mailand": "AC Milan",
    "Paris Saint-Germain": "Paris Saint-Germain",
}

UI_TO_OPENLIGA_TEAM = {
    "FC Bayern München": "FC Bayern München",
    "Bayer 04 Leverkusen": "Bayer 04 Leverkusen",
    "Borussia Dortmund": "Borussia Dortmund",
    "RB Leipzig": "RB Leipzig",
    "VfB Stuttgart": "VfB Stuttgart",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "SC Freiburg": "SC Freiburg",
    "TSG Hoffenheim": "TSG Hoffenheim",
    "VfL Wolfsburg": "VfL Wolfsburg",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach",
    "FC Augsburg": "FC Augsburg",
    "Mainz 05": "1. FSV Mainz 05",
    "Werder Bremen": "SV Werder Bremen",
    "1. FC Heidenheim": "1. FC Heidenheim 1846",
    "1. FC Union Berlin": "1. FC Union Berlin",
    "VfL Bochum": "VfL Bochum",
    "SV Darmstadt 98": "SV Darmstadt 98",
    "1. FC Köln": "1. FC Köln",
}

FILTERABLE_LEAGUES = {"1. Bundesliga", "La Liga", "Premier League", "Serie A", "Ligue 1"}


def normalize_openliga_team_name(team_name: str | None) -> str | None:
    if not team_name or team_name == "Alle Teams":
        return None
    return UI_TO_OPENLIGA_TEAM.get(team_name, team_name)


def normalize_statsbomb_team_name(team_name: str | None) -> str | None:
    openliga_team = normalize_openliga_team_name(team_name)
    if openliga_team is None:
        return None
    return TEAM_NAME_OVERRIDES.get(openliga_team, openliga_team)


def normalize_statsbomb_season_label(saison_label: str | None) -> str | None:
    if not saison_label or saison_label == "Alle Saisons":
        return None
    if "/" not in saison_label:
        return saison_label
    start_year, end_year = saison_label.split("/", 1)
    if len(end_year) == 4:
        return f"{start_year}/{end_year}"
    return f"{start_year}/20{end_year}"


def normalize_openliga_season_label(saison_label: str | None) -> str | None:
    if not saison_label or saison_label == "Alle Saisons":
        return None
    if "/" not in saison_label:
        return saison_label
    start_year, end_year = saison_label.split("/", 1)
    if len(end_year) == 2:
        return f"{start_year}/{end_year}"
    return f"{start_year}/{end_year[-2:]}"


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _statsbomb_filter_supported(liga: str | None) -> bool:
    return liga in (None, "", "Alle Ligen") or liga in FILTERABLE_LEAGUES


def _normalize_name_for_matching(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    for token in ["fc", "cf", "ac", "as", "ssc", "sv", "vfl", "vfb", "club", ".", "-", "'"]:
        normalized = normalized.replace(token, " ")
    normalized = normalized.replace("munchen", "munich")
    normalized = normalized.replace("koln", "cologne")
    normalized = normalized.replace("mainz 05", "mainz")
    normalized = normalized.replace("borussia monchengladbach", "monchengladbach")
    normalized = normalized.replace("paris saint germain", "paris sg")
    return " ".join(normalized.split())


def _resolve_statsbomb_team_name(
    conn: sqlite3.Connection,
    team_name: str,
    liga: str,
    saison_label: str,
    match_columns: set[str],
) -> str | None:
    mapped_name = normalize_statsbomb_team_name(team_name)
    statsbomb_season = normalize_statsbomb_season_label(saison_label)
    openliga_season = normalize_openliga_season_label(saison_label)

    where_clauses = []
    params: dict[str, str] = {}

    if "league" in match_columns and liga not in (None, "", "Alle Ligen"):
        where_clauses.append("league = :league")
        params["league"] = liga

    if statsbomb_season:
        if "season_label" in match_columns:
            where_clauses.append("season_label = :season_label")
            params["season_label"] = openliga_season or saison_label
        elif "season" in match_columns:
            where_clauses.append("season = :season")
            params["season"] = statsbomb_season

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    candidates_query = f"""
        SELECT DISTINCT team_name
        FROM (
            SELECT home_team AS team_name FROM statsbomb_matches {where_sql}
            UNION
            SELECT away_team AS team_name FROM statsbomb_matches {where_sql}
        )
        WHERE team_name IS NOT NULL AND team_name != ''
    """

    params_for_union = params | {f"{key}": value for key, value in params.items()}
    candidates = [row[0] for row in conn.execute(candidates_query, params_for_union).fetchall()]
    if not candidates:
        return mapped_name

    if mapped_name in candidates:
        return mapped_name

    normalized_target = _normalize_name_for_matching(mapped_name)
    scored_candidates = []
    for candidate in candidates:
        normalized_candidate = _normalize_name_for_matching(candidate)
        similarity = difflib.SequenceMatcher(None, normalized_target, normalized_candidate).ratio()
        token_overlap = len(set(normalized_target.split()) & set(normalized_candidate.split()))
        scored_candidates.append((similarity + token_overlap * 0.1, candidate))

    best_score, best_candidate = max(scored_candidates, default=(0, None))
    if best_score >= 0.55:
        return best_candidate
    return None


def load_statsbomb_kpis_from_db(team_name: str, saison_label: str, liga: str, db_path: Path | None = None) -> dict | None:
    """Aggregate Chancenverwertung and Druckresistenz from soccer.db via SQL."""
    if not _statsbomb_filter_supported(liga):
        return None

    if team_name in (None, "", "Alle Teams"):
        return None

    database_path = db_path or DB_PATH
    if not database_path.exists():
        return None

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        match_columns = _table_columns(conn, "statsbomb_matches")
        statsbomb_team = _resolve_statsbomb_team_name(conn, team_name, liga, saison_label, match_columns)
        if statsbomb_team is None:
            return None

        where_clauses = ["e.team = :team"]
        params: dict[str, str] = {"team": statsbomb_team}

        if "league" in match_columns and liga not in (None, "", "Alle Ligen"):
            where_clauses.append("m.league = :league")
            params["league"] = liga

        statsbomb_season = normalize_statsbomb_season_label(saison_label)
        if statsbomb_season:
            if "season_label" in match_columns:
                where_clauses.append("m.season_label = :season_label")
                params["season_label"] = normalize_openliga_season_label(saison_label)
            elif "season" in match_columns:
                where_clauses.append("m.season = :season")
                params["season"] = statsbomb_season

        sql = f"""
            WITH filtered_events AS (
                SELECT
                    e.match_id,
                    e."index" AS event_index,
                    e.type,
                    CAST(COALESCE(e.shot_statsbomb_xg, 0) AS REAL) AS shot_xg,
                    e.shot_outcome,
                    e.play_pattern,
                    LEAD(e.play_pattern) OVER (
                        PARTITION BY e.match_id
                        ORDER BY e."index"
                    ) AS next_play_pattern
                FROM statsbomb_events e
                JOIN statsbomb_matches m ON m.match_id = e.match_id
                WHERE {' AND '.join(where_clauses)}
            )
            SELECT
                COALESCE(SUM(CASE WHEN type = 'Shot' AND shot_outcome = 'Goal' THEN 1 ELSE 0 END), 0) AS tore,
                COALESCE(SUM(CASE WHEN type = 'Shot' THEN shot_xg ELSE 0 END), 0) AS xg_summe,
                COALESCE(SUM(CASE WHEN type = 'Pressure' THEN 1 ELSE 0 END), 0) AS druck_ereignisse,
                COALESCE(SUM(CASE WHEN type = 'Pressure' AND COALESCE(next_play_pattern, '') <> 'From Lost Ball' THEN 1 ELSE 0 END), 0) AS druck_entkommen
            FROM filtered_events
        """

        row = conn.execute(sql, params).fetchone()

    if row is None:
        return None

    pressure_events = int(row["druck_ereignisse"])
    pressure_escape = int(row["druck_entkommen"])
    pressure_rate = round((pressure_escape / pressure_events) * 100, 1) if pressure_events else 0.0
    chance_delta = round(float(row["tore"]) - float(row["xg_summe"]), 1)

    return {
        "team": team_name,
        "statsbomb_team": statsbomb_team,
        "Chancenverwertung": chance_delta,
        "Druckresistenz": pressure_rate,
        "Tore": int(row["tore"]),
        "xG": round(float(row["xg_summe"]), 1),
        "Druckereignisse": pressure_events,
    }


def generiere_und_speichere_statsbomb_kpis(saison_label: str, ausgabe_datei: str) -> None:
    """Export legacy JSON snapshots from soccer.db instead of from the API."""
    export_path = Path(ausgabe_datei)
    export_path.parent.mkdir(parents=True, exist_ok=True)

    saison_kpis: dict[str, dict] = {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        openliga_teams = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT team FROM openliga_table WHERE season = ? ORDER BY team",
                (normalize_openliga_season_label(saison_label),),
            ).fetchall()
        ]

    for openliga_team in openliga_teams:
        kpis = load_statsbomb_kpis_from_db(openliga_team, saison_label, "Alle Ligen")
        if kpis is not None:
            saison_kpis[openliga_team] = {
                "Verein": openliga_team,
                "Chancen_Qualitaet_xG": kpis["xG"],
                "Tor_Effizienz_Delta": kpis["Chancenverwertung"],
                "Druck_Resistenz_Prozent": kpis["Druckresistenz"],
            }

    if not saison_kpis:
        saison_kpis = {
            "status": "keine_datenbankdaten",
            "saison": saison_label,
        }

    with open(export_path, "w", encoding="utf-8") as file_handle:
        json.dump(saison_kpis, file_handle, indent=4, ensure_ascii=False)

    print(f"StatsBomb KPI-Export geschrieben: {export_path}")


if __name__ == "__main__":
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    generiere_und_speichere_statsbomb_kpis("2022/23", str(EXPORT_DIR / "statsbomb_kpis_2022_23.json"))
    generiere_und_speichere_statsbomb_kpis("2023/24", str(EXPORT_DIR / "statsbomb_kpis_2023_24.json"))
    generiere_und_speichere_statsbomb_kpis("2024/25", str(EXPORT_DIR / "statsbomb_kpis_2024_25.json"))
