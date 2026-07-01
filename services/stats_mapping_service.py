"""Mapping and normalization helpers for stats services."""

import difflib
import sqlite3
import unicodedata

from services.stats_constants import TEAM_NAME_OVERRIDES, UI_TO_OPENLIGA_TEAM


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


def resolve_statsbomb_team_name(
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

    candidates = [row[0] for row in conn.execute(candidates_query, params).fetchall()]
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
