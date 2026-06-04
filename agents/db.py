import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "soccer.db"

SCHEMA = """
Tabelle: openliga_table
Spalten: position, team, team_id, matches, won, draw, lost, goals_for, goals_against, goal_diff, points

Tabelle: openliga_matches
Spalten: match_id, match_datetime, matchday, home_team, away_team, home_goals, away_goals, is_finished

Tabelle: statsbomb_matches
Spalten: match_id, match_date, kick_off, competition, season, home_team, away_team, home_score, away_score, match_status, referee, stadium, home_managers, away_managers

Tabelle: statsbomb_events
Spalten: id, match_id, index, period, minute, second, type, possession, possession_team, play_pattern, team, player, position, duration, under_pressure, counterpress, shot_statsbomb_xg, shot_outcome, shot_technique, shot_body_part, pass_length, pass_angle, pass_outcome, pass_recipient, loc_x, loc_y
"""


def run_query(sql: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
