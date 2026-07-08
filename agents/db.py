# Autor: Selma Elezovic
# Datenbankzugriff: Schema-Definition für den SQL-Generator und run_query() für alle Agenten.

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "soccer.db"

SCHEMA = """
Tabelle: openliga_table
Spalten: position, team, team_id, matches, won, draw, lost, goals_for, goals_against, goal_diff, points
Beispielwerte team: 'FC Bayern München', 'Borussia Dortmund', 'Bayer 04 Leverkusen', 'Borussia Mönchengladbach', 'VfL Wolfsburg', '1. FSV Mainz 05', 'Hertha BSC', '1. FC Köln', 'Hamburger SV', 'FC Schalke 04'
Hinweis: Enthält nur Bundesliga-Tabellendaten (Saison-Gesamtstand, keine Spieltags-Snapshots).

Tabelle: openliga_matches
Spalten: match_id, match_datetime, matchday, home_team, away_team, home_goals, away_goals, is_finished
Beispielwerte home_team/away_team: 'FC Bayern München', 'Borussia Dortmund', 'Bayer 04 Leverkusen', 'SV Werder Bremen', 'SV Darmstadt 98', 'VfB Stuttgart', 'FC Augsburg'
Hinweis: match_datetime Format '2025-05-17T13:30:00Z'. Matchdays 1–38. is_finished = 1 wenn gespielt.

Tabelle: statsbomb_matches
Spalten: match_id, match_date, kick_off, competition, season, home_team, away_team, home_score, away_score, match_status, referee, stadium, home_managers, away_managers
Beispielwerte competition: 'Germany - 1. Bundesliga', 'England - Premier League', 'Spain - La Liga', 'Italy - Serie A', 'France - Ligue 1'
Beispielwerte season: '2023/2024', '2022/2023', '2021/2022', '2016/2017', '2015/2016'
Beispielwerte home_team/away_team: 'Bayer Leverkusen', 'Borussia Mönchengladbach', 'Schalke 04', 'FC Köln', 'VfB Stuttgart', 'Augsburg', 'FSV Mainz 05', 'Darmstadt 98', 'Hoffenheim'
WICHTIG: Teamnamen in statsbomb_matches unterscheiden sich von openliga_table! Z.B. 'Bayer Leverkusen' (StatsBomb) vs 'Bayer 04 Leverkusen' (OpenLiga). Kein 'FC' Präfix bei StatsBomb.

Tabelle: statsbomb_events
Spalten: id, match_id, index, period, minute, second, type, possession, possession_team, play_pattern, team, player, position, duration, under_pressure, counterpress, shot_statsbomb_xg, shot_outcome, shot_technique, shot_body_part, pass_length, pass_angle, pass_outcome, pass_recipient, loc_x, loc_y
Beispielwerte type: 'Pass', 'Shot', 'Carry', 'Pressure', 'Duel', 'Clearance', 'Interception', 'Dribble', 'Block', 'Foul Committed', 'Ball Recovery', 'Starting XI'
Beispielwerte shot_outcome: 'Goal', 'Saved', 'Off T', 'Blocked', 'Wayward', 'Post'
Hinweis: shot_statsbomb_xg ist NULL für Nicht-Schuss-Events. xG-Abfragen immer mit WHERE type = 'Shot'.
"""


def run_query(sql: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        return [dict(row) for row in cursor.fetchall()]
