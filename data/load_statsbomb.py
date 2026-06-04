"""StatsBomb loader — 1. Bundesliga 2023/24, erste 15 Matches mit Events."""
import sqlite3
import warnings
import pandas as pd
from statsbombpy import sb

# suppress open-data auth warning
warnings.filterwarnings("ignore", category=UserWarning)

COMPETITION_ID = 9    # 1. Bundesliga
SEASON_ID = 281       # 2023/24
MAX_MATCHES = 15

# event columns to keep — keeps the table lean but queryable
EVENT_COLS = [
    "id", "match_id", "index", "period", "minute", "second",
    "type", "possession", "possession_team", "play_pattern",
    "team", "player", "position",
    "location", "duration",
    "under_pressure", "counterpress",
    # shot-specific
    "shot_statsbomb_xg", "shot_outcome", "shot_technique", "shot_body_part",
    # pass-specific
    "pass_length", "pass_angle", "pass_outcome", "pass_recipient",
]


def _flatten_location(df: pd.DataFrame) -> pd.DataFrame:
    """Explode list-type location column into x/y floats."""
    if "location" in df.columns:
        df["loc_x"] = df["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
        df["loc_y"] = df["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
        df.drop(columns=["location"], inplace=True)
    return df


def fetch_matches() -> pd.DataFrame:
    matches = sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID)
    keep = [
        "match_id", "match_date", "kick_off", "competition", "season",
        "home_team", "away_team", "home_score", "away_score",
        "match_status", "referee", "stadium",
        "home_managers", "away_managers",
    ]
    cols = [c for c in keep if c in matches.columns]
    df = matches[cols].copy()
    # flatten nested dicts to strings for SQLite
    for col in ["competition", "season", "referee", "stadium", "home_managers", "away_managers"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


def fetch_events(match_ids: list[int]) -> pd.DataFrame:
    frames = []
    for i, mid in enumerate(match_ids, start=1):
        print(f"    Match {i}/{len(match_ids)} (id={mid}) …", end=" ", flush=True)
        evts = sb.events(match_id=mid)
        evts["match_id"] = mid
        # keep only existing columns
        cols = [c for c in EVENT_COLS if c in evts.columns]
        evts = evts[cols].copy()
        evts = _flatten_location(evts)
        # stringify remaining object columns that may contain dicts/lists
        for col in evts.select_dtypes(include="object").columns:
            evts[col] = evts[col].astype(str)
        frames.append(evts)
        print(f"{len(evts)} Events")
    return pd.concat(frames, ignore_index=True)


def save_to_db(con: sqlite3.Connection) -> None:
    print("  Lade StatsBomb Matches...")
    matches = fetch_matches()
    match_ids = matches["match_id"].tolist()[:MAX_MATCHES]
    matches_subset = matches[matches["match_id"].isin(match_ids)]
    matches_subset.to_sql("statsbomb_matches", con, if_exists="replace", index=False)
    print(f"    → {len(matches_subset)} Matches gespeichert")

    print(f"  Lade StatsBomb Events für {len(match_ids)} Matches...")
    events = fetch_events(match_ids)
    events.to_sql("statsbomb_events", con, if_exists="replace", index=False)
    print(f"    → {len(events):,} Events gespeichert")
