"""Business logic layer for statistics tab view models."""

import pandas as pd

from services.sentiment_service import get_team_sentiment
from services.stats_constants import PROJECT_ROOT
from services.stats_kpi_service import load_statsbomb_kpis_from_db
from services.stats_repository import load_top_kpis_from_db


def load_leistung_kpis_for_stats_tab(liga: str, saison: str, team_name: str) -> dict | None:
    """Lädt kombinierte Leistungs-KPIs und nutzt bei Bedarf StatsBomb-Saisonfallback."""
    table_kpis = load_top_kpis_from_db(liga, saison, team_name)
    if table_kpis is None:
        return None

    requested_season = table_kpis["season"]
    statsbomb_season_used = requested_season
    statsbomb_kpis = load_statsbomb_kpis_from_db(table_kpis["team"], requested_season, table_kpis["league"])

    if statsbomb_kpis is None and isinstance(requested_season, str) and "/" in requested_season:
        try:
            start_year = int(requested_season.split("/")[0])
            for candidate_start in range(start_year - 1, 2014, -1):
                candidate_season = f"{candidate_start}/{str(candidate_start + 1)[-2:]}"
                fallback = load_statsbomb_kpis_from_db(table_kpis["team"], candidate_season, table_kpis["league"])
                if fallback is not None:
                    statsbomb_kpis = fallback
                    statsbomb_season_used = candidate_season
                    break
        except ValueError:
            pass

    xg_per_game = None
    if statsbomb_kpis:
        xg_per_game = statsbomb_kpis.get("xG pro Spiel")
        if xg_per_game is None:
            xg_per_game = statsbomb_kpis.get("xG")

    return {
        "team": table_kpis["team"],
        "league": table_kpis["league"],
        "season": table_kpis["season"],
        "Tore": table_kpis["Tore"],
        "Gegentore": table_kpis["Gegentore"],
        "xG": xg_per_game,
        "Chancenverwertung": statsbomb_kpis.get("Chancenverwertung") if statsbomb_kpis else None,
        "Druckresistenz": statsbomb_kpis.get("Druckresistenz") if statsbomb_kpis else None,
        "statsbomb_season_used": statsbomb_season_used if statsbomb_kpis else None,
    }


def build_comparison_chart_data_for_stats_tab(liga: str, saison: str, team_name: str) -> tuple[pd.DataFrame, dict | None]:
    kpis = load_leistung_kpis_for_stats_tab(liga, saison, team_name)
    if kpis is None:
        return pd.DataFrame({"Metrik": ["Tore", "xG-Index pro Spiel", "Gegentore"], "Wert": [0, None, 0]}), None

    xg_index = round(kpis["xG"] * 10, 1) if kpis["xG"] is not None else None
    chart_data = pd.DataFrame({
        "Metrik": ["Tore", "xG-Index pro Spiel", "Gegentore"],
        "Wert": [
            kpis["Tore"],
            xg_index,
            kpis["Gegentore"],
        ],
    })
    return chart_data, kpis


def get_team_sentiment_for_stats_tab(team_name: str) -> dict | None:
    sentiment_path = PROJECT_ROOT / "data" / "wikipedia_articles.json"
    try:
        return get_team_sentiment(team_name, file_path=str(sentiment_path))
    except Exception:
        # Sentiment is optional for the UI; any NLP/runtime issue must not break the tab.
        return None
