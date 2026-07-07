"""SQL helpers for StatsBomb KPIs used in the statistics tab."""

import json
import sqlite3
from pathlib import Path

from services.stats_constants import DB_PATH, EXPORT_DIR, FILTERABLE_LEAGUES
from services.stats_mapping_service import (
    normalize_openliga_season_label,
    normalize_openliga_team_name,
    normalize_statsbomb_season_label,
    resolve_statsbomb_team_name,
)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _statsbomb_filter_supported(liga: str | None) -> bool:
    return liga in (None, "", "Alle Ligen") or liga in FILTERABLE_LEAGUES


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
        if not _table_exists(conn, "statsbomb_matches") or not _table_exists(conn, "statsbomb_events"):
            return None

        match_columns = _table_columns(conn, "statsbomb_matches")
        statsbomb_team = resolve_statsbomb_team_name(conn, team_name, liga, saison_label, match_columns)
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
                COUNT(*) AS event_count,
                COALESCE(SUM(CASE WHEN type = 'Shot' AND shot_outcome = 'Goal' THEN 1 ELSE 0 END), 0) AS tore,
                COALESCE(SUM(CASE WHEN type = 'Shot' THEN shot_xg ELSE 0 END), 0) AS xg_summe,
                COALESCE(SUM(CASE WHEN type = 'Pressure' THEN 1 ELSE 0 END), 0) AS druck_ereignisse,
                COALESCE(SUM(CASE WHEN type = 'Pressure' AND COALESCE(next_play_pattern, '') <> 'From Lost Ball' THEN 1 ELSE 0 END), 0) AS druck_entkommen
            FROM filtered_events
        """

        row = conn.execute(sql, params).fetchone()

    if row is None:
        return None

    # Avoid misleading "0" KPIs when the filter combination has no StatsBomb events.
    if int(row["event_count"] or 0) == 0:
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
