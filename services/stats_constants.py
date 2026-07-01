"""Shared constants for stats-related services."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "soccer.db"
EXPORT_DIR = PROJECT_ROOT / "data"

FILTERABLE_LEAGUES = {"1. Bundesliga", "La Liga", "Premier League", "Serie A", "Ligue 1"}

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
