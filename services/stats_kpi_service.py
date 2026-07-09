"""
Titel: StatsBomb-KPI-Service

Beschreibung: Dieses Modul berechnet StatsBomb-Kennzahlen aus SQLite-Tabellen oder
              Legacy-Exports und stellt die für die Statistik-Ansicht benötigten
              xG- und Tor-Kennzahlen bereit.
Wichtige Inhalte: SQL-Abfragen, Summary-Table-Fallback, xG pro Spiel, Tore,
                  saisonbezogene Export-Utilities.
                  
Autorin: Annette Kufner

Hinweis: Dieses Skript wurde mithilfe von Gemini, Claude und Codex erstellt.
"""

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


# Tabellen- und Datei-Checks halten die SQL-Logik robust gegenüber wechselnden DB-Schemata.
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


def _ensure_statsbomb_summary_table(conn: sqlite3.Connection) -> bool:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS statsbomb_kpis (
            season_label TEXT NOT NULL,
            team TEXT NOT NULL,
            xg_total REAL,
            xg_per_game REAL,
            tore INTEGER,
            spiele INTEGER,
            PRIMARY KEY (season_label, team)
        )
        """
    )

    existing_rows = conn.execute("SELECT COUNT(*) FROM statsbomb_kpis").fetchone()[0]
    if existing_rows:
        return True

    # Falls die Live-Tabellen fehlen, werden Kennzahlen aus den Export-JSONs rekonstruiert.
    export_files = sorted(EXPORT_DIR.glob("statsbomb_kpis_*.json"))
    inserted = 0

    for export_path in export_files:
        season_label = export_path.stem.replace("statsbomb_kpis_", "").replace("_", "/")
        with open(export_path, encoding="utf-8") as file_handle:
            payload = json.load(file_handle)

        if not isinstance(payload, dict):
            continue

        rows = []
        for team_name, team_payload in payload.items():
            if not isinstance(team_payload, dict):
                continue
            rows.append(
                (
                    season_label,
                    team_name,
                    team_payload.get("Chancen_Qualitaet_xG"),
                    team_payload.get("xG_Pro_Spiel", team_payload.get("Chancen_Qualitaet_xG")),
                    team_payload.get("Tore"),
                    team_payload.get("Spiele"),
                )
            )

        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO statsbomb_kpis (
                    season_label, team, xg_total, xg_per_game, tore, spiele
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            inserted += len(rows)

    conn.commit()
    return inserted > 0


def _load_statsbomb_kpis_from_summary_table(conn: sqlite3.Connection, team_name: str, saison_label: str) -> dict | None:
    if not _table_exists(conn, "statsbomb_kpis") and not _ensure_statsbomb_summary_table(conn):
        return None

    normalized_team = normalize_openliga_team_name(team_name)
    normalized_season = normalize_openliga_season_label(saison_label)
    if not normalized_team or not normalized_season:
        return None

    row = conn.execute(
        """
        SELECT season_label, team, xg_total, xg_per_game, tore, spiele
        FROM statsbomb_kpis
        WHERE season_label = ? AND team = ?
        """,
        (normalized_season, normalized_team),
    ).fetchone()

    if row is None:
        return None

    return {
        "team": team_name,
        "statsbomb_team": row[1],
        "Tore": row[4],
        "xG": row[2],
        "xG pro Spiel": row[3],
        "Chancenverwertung": round(float(row[4]) - float(row[2]), 1) if row[4] is not None and row[2] is not None else None,
        "Spiele": row[5],
    }


def load_statsbomb_kpis_from_db(team_name: str, saison_label: str, liga: str, db_path: Path | None = None) -> dict | None:
    """Aggregiert xG und Tore aus soccer.db via SQL."""
    # Erst versucht man die direkten Event-Tabellen, danach den Summary-Fallback.
    if not _statsbomb_filter_supported(liga):
        return None

    if team_name in (None, "", "Alle Teams"):
        return None

    database_path = db_path or DB_PATH
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row

        full_statsbomb_available = _table_exists(conn, "statsbomb_matches") and _table_exists(conn, "statsbomb_events")
        if not full_statsbomb_available:
            return _load_statsbomb_kpis_from_summary_table(conn, team_name, saison_label)

        match_columns = _table_columns(conn, "statsbomb_matches")
        statsbomb_team = resolve_statsbomb_team_name(conn, team_name, liga, saison_label, match_columns)
        if statsbomb_team is None:
            return _load_statsbomb_kpis_from_summary_table(conn, team_name, saison_label)

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
                COUNT(DISTINCT match_id) AS spiele,
                COALESCE(SUM(CASE WHEN type = 'Shot' AND shot_outcome = 'Goal' THEN 1 ELSE 0 END), 0) AS tore,
                COALESCE(SUM(CASE WHEN type = 'Shot' THEN shot_xg ELSE 0 END), 0) AS xg_summe
            FROM filtered_events
        """

        row = conn.execute(sql, params).fetchone()

    if row is None:
        with sqlite3.connect(database_path) as conn:
            return _load_statsbomb_kpis_from_summary_table(conn, team_name, saison_label)

    # Leere Filterkombinationen sollen nicht als echte 0er-KPIs erscheinen.
    if int(row["event_count"] or 0) == 0:
        with sqlite3.connect(database_path) as conn:
            return _load_statsbomb_kpis_from_summary_table(conn, team_name, saison_label)

    match_count = int(row["spiele"] or 0)
    xg_total = round(float(row["xg_summe"]), 1)
    xg_per_match = round(float(row["xg_summe"]) / match_count, 2) if match_count else None
    chancenverwertung = round(float(row["tore"]) - float(row["xg_summe"]), 1)

    return {
        "team": team_name,
        "statsbomb_team": statsbomb_team,
        "Tore": int(row["tore"]),
        "xG": xg_total,
        "xG pro Spiel": xg_per_match,
        "Chancenverwertung": chancenverwertung,
        "Spiele": match_count,
    }


def generiere_und_speichere_statsbomb_kpis(saison_label: str, ausgabe_datei: str) -> None:
    """Export legacy JSON snapshots from soccer.db instead of from the API."""
    # Diese Funktion erzeugt die JSON-Exports, die ältere Workflows weiterverwenden.
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
                "xG_Pro_Spiel": kpis["xG pro Spiel"],
                "Spiele": kpis["Spiele"],
                "Tore": kpis["Tore"],
            }

    if not saison_kpis:
        saison_kpis = {
            "status": "keine_datenbankdaten",
            "saison": saison_label,
        }

    with open(export_path, "w", encoding="utf-8") as file_handle:
        json.dump(saison_kpis, file_handle, indent=4, ensure_ascii=False)

    print(f"StatsBomb KPI-Export geschrieben: {export_path}")


def generiere_alle_statsbomb_kpis() -> None:
    """Schreibt KPI-Exports fuer alle in statsbomb_matches vorhandenen Saisons."""
    # Alle verfügbaren Saisons werden nacheinander exportiert.
    if not DB_PATH.exists():
        return

    with sqlite3.connect(DB_PATH) as conn:
        season_rows = conn.execute(
            "SELECT DISTINCT season_label FROM statsbomb_matches WHERE season_label IS NOT NULL ORDER BY season_label"
        ).fetchall()

    seasons = [row[0] for row in season_rows if row[0]]
    if not seasons:
        seasons = ["2022/23", "2023/24", "2024/25"]

    for saison_label in seasons:
        file_name = f"statsbomb_kpis_{normalize_openliga_season_label(saison_label).replace('/', '_')}.json"
        generiere_und_speichere_statsbomb_kpis(saison_label, str(EXPORT_DIR / file_name))


if __name__ == "__main__":
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    generiere_alle_statsbomb_kpis()
