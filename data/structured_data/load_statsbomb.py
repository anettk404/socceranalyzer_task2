"""
Autor: Selma Elezovic
Lädt Matches und detaillierte Ereignisdaten (Schüsse, Pässe, xG) aus der StatsBomb-API
für mehrere Ligen und Saisons. Speichert in statsbomb_matches und statsbomb_events.
Bereits vorhandene Matches werden übersprungen (Duplikat-Schutz via _existing_match_ids).
"""
import sqlite3
import warnings
import pandas as pd
from statsbombpy import sb

warnings.filterwarnings("ignore", category=UserWarning)

# Ligen: (league_label, competition_name, competition_id, default_season_id, season_label)
COMPETITIONS = [
    ("1. Bundesliga", "1. Bundesliga", 9, 27, "2015/16"),
    ("1. Bundesliga", "1. Bundesliga", 9, 281, "2023/24"),
    ("Premier League", "Premier League", 2, 27, "2015/16"),
    ("La Liga", "La Liga", 11, 2, "2016/17"),
    ("Serie A", "Serie A", 12, 27, "2015/16"),
    ("Ligue 1", "Ligue 1", 7, 27, "2015/16"),
    ("Ligue 1", "Ligue 1", 7, 108, "2021/22"),
    ("Ligue 1", "Ligue 1", 7, 235, "2022/23"),
]

EVENT_COLS = [
    "id", "match_id", "index", "period", "minute", "second",
    "type", "possession", "possession_team", "play_pattern",
    "team", "player", "position",
    "location", "duration",
    "under_pressure", "counterpress",
    "shot_statsbomb_xg", "shot_outcome", "shot_technique", "shot_body_part",
    "pass_length", "pass_angle", "pass_outcome", "pass_recipient",
]


def _flatten_location(df: pd.DataFrame) -> pd.DataFrame:
    # StatsBomb speichert Koordinaten als [x, y]-Liste — SQLite braucht separate Spalten
    if "location" in df.columns:
        df["loc_x"] = df["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
        df["loc_y"] = df["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
        df.drop(columns=["location"], inplace=True)
    return df


def _table_exists(con: sqlite3.Connection, table_name: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _existing_match_ids(con: sqlite3.Connection, table_name: str, league_label: str, season_label: str) -> set[int]:
    if not _table_exists(con, table_name):
        return set()
    rows = con.execute(
        f"SELECT DISTINCT match_id FROM {table_name} WHERE league = ? AND season_label = ?",
        (league_label, season_label),
    ).fetchall()
    return {int(row[0]) for row in rows}


def _season_id_for_label(competition_name: str, label: str) -> int | None:
    """Sucht die season_id in den verfügbaren StatsBomb-Competitions."""
    try:
        comps = sb.competitions()
        start = label.split("/")[0]
        end = f"20{label.split('/')[1]}"
        statsbomb_label = f"{start}/{end}"
        match = comps[
            (comps["competition_name"] == competition_name) &
            (comps["season_name"] == statsbomb_label)
        ]
        if not match.empty:
            return int(match["season_id"].iloc[0])
    except Exception:
        pass
    return None


def fetch_matches_for_season(league_label: str, competition_name: str, competition_id: int, season_id: int, label: str) -> pd.DataFrame:
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    keep = [
        "match_id", "match_date", "kick_off", "competition", "season",
        "home_team", "away_team", "home_score", "away_score",
        "match_status", "referee", "stadium",
        "home_managers", "away_managers",
    ]
    cols = [c for c in keep if c in matches.columns]
    df = matches[cols].copy()
    for col in ["competition", "season", "referee", "stadium", "home_managers", "away_managers"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    df["league"] = league_label
    df["competition_name"] = competition_name
    df["season_label"] = label
    return df


def fetch_events_for_match(match_id: int) -> pd.DataFrame:
    evts = sb.events(match_id=match_id)
    evts["match_id"] = match_id
    cols = [c for c in EVENT_COLS if c in evts.columns]
    evts = evts[cols].copy()
    evts = _flatten_location(evts)
    for col in evts.select_dtypes(include="object").columns:
        evts[col] = evts[col].astype(str)
    return evts


def save_to_db(con: sqlite3.Connection) -> None:
    wrote_matches = False
    wrote_events = False
    total_matches = 0
    total_events = 0

    for league_label, competition_name, competition_id, season_id_default, label in COMPETITIONS:
        season_id = _season_id_for_label(competition_name, label) or season_id_default

        print(f"\n  Lade StatsBomb {league_label} {label} (season_id={season_id})...")
        try:
            matches = fetch_matches_for_season(league_label, competition_name, competition_id, season_id, label)
            print(f"    → {len(matches)} Matches gefunden")
        except Exception as e:
            print(f"    ⚠ Saison nicht verfügbar: {e}")
            continue

        existing_matches = _existing_match_ids(con, "statsbomb_matches", league_label, label)
        matches_to_write = matches[~matches["match_id"].isin(existing_matches)].copy()
        if not matches_to_write.empty:
            # "replace" nur beim allerersten Schreibvorgang, danach immer "append"
            # damit Daten aus verschiedenen Ligen nicht überschrieben werden.
            matches_to_write.to_sql("statsbomb_matches", con, if_exists="append" if wrote_matches or _table_exists(con, "statsbomb_matches") else "replace", index=False)
            wrote_matches = True
            total_matches += len(matches_to_write)
        elif _table_exists(con, "statsbomb_matches"):
            wrote_matches = True

        existing_event_matches = _existing_match_ids(con, "statsbomb_events", league_label, label)
        match_ids = [match_id for match_id in matches["match_id"].tolist() if match_id not in existing_event_matches]

        print(f"    Lade Events für {len(match_ids)} Matches...")
        for index, match_id in enumerate(match_ids, start=1):
            print(f"    Match {index}/{len(match_ids)} (id={match_id}) …", end=" ", flush=True)
            try:
                events = fetch_events_for_match(match_id)
                if not events.empty:
                    events["league"] = league_label
                    events["season_label"] = label
                    events.to_sql("statsbomb_events", con, if_exists="append" if wrote_events or _table_exists(con, "statsbomb_events") else "replace", index=False)
                    wrote_events = True
                    total_events += len(events)
                    con.commit()
                    print(f"{len(events)} Events")
                else:
                    con.commit()
                    print("0 Events")
            except Exception as e:
                con.commit()
                print(f"Fehler: {e}")

        if not match_ids:
            print("    → Alle Events für diese Saison sind bereits vorhanden")

    if wrote_matches:
        print(f"\n  ✓ statsbomb_matches: {total_matches} Zeilen gesamt")

    if wrote_events:
        print(f"  ✓ statsbomb_events: {total_events:,} Zeilen gesamt")
