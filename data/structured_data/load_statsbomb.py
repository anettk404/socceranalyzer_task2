"""StatsBomb loader — 1. Bundesliga, mehrere Saisons mit allen Events."""
import sqlite3
import warnings
import pandas as pd
from statsbombpy import sb

warnings.filterwarnings("ignore", category=UserWarning)

# Saisons: (competition_id, season_id, label)
SEASONS = [
    (9, 270, "2022/23"),   # 1. Bundesliga 2022/23
    (9, 281, "2023/24"),   # 1. Bundesliga 2023/24
    (9, 282, "2024/25"),   # 1. Bundesliga 2024/25
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
    if "location" in df.columns:
        df["loc_x"] = df["location"].apply(lambda v: v[0] if isinstance(v, list) else None)
        df["loc_y"] = df["location"].apply(lambda v: v[1] if isinstance(v, list) else None)
        df.drop(columns=["location"], inplace=True)
    return df


def _season_id_for_label(label: str) -> int | None:
    """Sucht die season_id in den verfügbaren StatsBomb-Competitions."""
    try:
        comps = sb.competitions()
        # StatsBomb-Format: "2023/2024" statt "2023/24"
        start = label.split("/")[0]
        end = f"20{label.split('/')[1]}"
        statsbomb_label = f"{start}/{end}"
        match = comps[
            (comps["competition_name"] == "1. Bundesliga") &
            (comps["season_name"] == statsbomb_label)
        ]
        if not match.empty:
            return int(match["season_id"].iloc[0])
    except Exception:
        pass
    return None


def fetch_matches_for_season(competition_id: int, season_id: int, label: str) -> pd.DataFrame:
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
    df["season_label"] = label
    return df


def fetch_events(match_ids: list[int]) -> pd.DataFrame:
    frames = []
    for i, mid in enumerate(match_ids, start=1):
        print(f"    Match {i}/{len(match_ids)} (id={mid}) …", end=" ", flush=True)
        try:
            evts = sb.events(match_id=mid)
            evts["match_id"] = mid
            cols = [c for c in EVENT_COLS if c in evts.columns]
            evts = evts[cols].copy()
            evts = _flatten_location(evts)
            for col in evts.select_dtypes(include="object").columns:
                evts[col] = evts[col].astype(str)
            frames.append(evts)
            print(f"{len(evts)} Events")
        except Exception as e:
            print(f"Fehler: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def save_to_db(con: sqlite3.Connection) -> None:
    all_matches = []
    all_events = []

    for competition_id, season_id_default, label in SEASONS:
        # season_id dynamisch aus StatsBomb holen (Fallback auf default)
        season_id = _season_id_for_label(label) or season_id_default

        print(f"\n  Lade StatsBomb {label} (season_id={season_id})...")
        try:
            matches = fetch_matches_for_season(competition_id, season_id, label)
            print(f"    → {len(matches)} Matches gefunden")
        except Exception as e:
            print(f"    ⚠ Saison nicht verfügbar: {e}")
            continue

        all_matches.append(matches)
        match_ids = matches["match_id"].tolist()

        print(f"    Lade Events für {len(match_ids)} Matches...")
        events = fetch_events(match_ids)
        if not events.empty:
            events["season_label"] = label
            all_events.append(events)
            print(f"    → {len(events):,} Events geladen")

    if all_matches:
        df_matches = pd.concat(all_matches, ignore_index=True)
        df_matches.to_sql("statsbomb_matches", con, if_exists="replace", index=False)
        print(f"\n  ✓ statsbomb_matches: {len(df_matches)} Zeilen gesamt")

    if all_events:
        df_events = pd.concat(all_events, ignore_index=True)
        df_events.to_sql("statsbomb_events", con, if_exists="replace", index=False)
        print(f"  ✓ statsbomb_events: {len(df_events):,} Zeilen gesamt")
