"""
tab_statistics.py – Statistiken-Tab

------------------------------------------------------------------------------------------------
Design der KPI-Karten (Platz, Punkte, Siege, Tore, Chancenverwertung, Gegentore, Druckresistenz)
Word Cloud pro Verein (Wikipedia)
Balkendiagramme (Vergleich zweier Teams)
------------------------------------------------------------------------------------------------
"""
# Authorin: Annette Kufner


#-----------------------------------------------------
# Setup
#-----------------------------------------------------

import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from pathlib import Path
import sys

try:
    from helpers import load_wordcloud_frequencies, zeige_wortwolke
except ImportError:  # pragma: no cover - fallback for different execution contexts
    from frontend.helpers import load_wordcloud_frequencies, zeige_wortwolke

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.stats_kpi_service import (  # noqa: E402
    load_statsbomb_kpis_from_db,
    normalize_openliga_season_label,
    normalize_openliga_team_name,
)

#-----------------------------------------------------
# Import weiterer Funktionen aus anderen .py-Dateien
#-----------------------------------------------------

DB_PATH = PROJECT_ROOT / "data" / "soccer.db"
DEFAULT_LIGA_OPTIONS = ["Alle Ligen", "1. Bundesliga", "La Liga", "Premier League", "Serie A", "Ligue 1"]
FALLBACK_TEAM_OPTIONS_BY_LIGA = {
    "Alle Ligen": ["Alle Teams"],
    "1. Bundesliga": [
        "Alle Teams", "FC Bayern München", "Borussia Dortmund", "Bayer 04 Leverkusen", "RB Leipzig",
        "VfB Stuttgart", "Eintracht Frankfurt", "SC Freiburg", "TSG Hoffenheim", "VfL Wolfsburg",
        "Borussia Mönchengladbach", "FC Augsburg", "Mainz 05", "Werder Bremen", "1. FC Heidenheim",
        "1. FC Union Berlin", "VfL Bochum", "SV Darmstadt 98",
    ],
    "La Liga": ["Alle Teams", "Real Madrid", "FC Barcelona", "Atlético Madrid", "Sevilla FC", "Villarreal CF", "Real Sociedad", "Athletic Club", "Valencia CF", "Celta Vigo"],
    "Premier League": ["Alle Teams", "Manchester City", "Liverpool FC", "Arsenal FC", "Chelsea FC", "Manchester United", "Tottenham Hotspur", "Newcastle United", "Aston Villa", "Leicester City"],
    "Serie A": ["Alle Teams", "Inter Mailand", "Juventus Turin", "AC Mailand", "AS Rom", "SSC Neapel", "Atalanta Bergamo", "Lazio Rom", "Fiorentina", "Bologna FC"],
    "Ligue 1": ["Alle Teams", "Paris Saint-Germain", "Olympique Marseille", "Olympique Lyon", "AS Monaco", "LOSC Lille", "Stade Rennais", "AJ Auxerre", "RC Lens", "FC Nantes"],
}

FALLBACK_ALL_TEAMS = ["Alle Teams", *sorted({
    team
    for liga, teams in FALLBACK_TEAM_OPTIONS_BY_LIGA.items()
    if liga != "Alle Ligen"
    for team in teams
    if team != "Alle Teams"
})]


#-----------------------------------------------------
# Hilfsfunktionen für UI-Komponenten
#-----------------------------------------------------

@st.cache_data(show_spinner=False)
def _table_columns(table_name: str) -> set[str]:
    if not DB_PATH.exists():
        return set()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


@st.cache_data(show_spinner=False)
def get_available_leagues() -> list[str]:
    if not DB_PATH.exists():
        return DEFAULT_LIGA_OPTIONS

    columns = _table_columns("openliga_table")
    if "league" not in columns:
        return DEFAULT_LIGA_OPTIONS

    with sqlite3.connect(DB_PATH) as conn:
        leagues = [row[0] for row in conn.execute("SELECT DISTINCT league FROM openliga_table ORDER BY league").fetchall()]

    return ["Alle Ligen", *leagues] if leagues else DEFAULT_LIGA_OPTIONS


@st.cache_data(show_spinner=False)
def get_available_seasons(liga: str) -> list[str]:
    if not DB_PATH.exists():
        return ["Alle Saisons", "2024/25", "2023/24", "2022/23"]

    columns = _table_columns("openliga_table")
    if "season" not in columns:
        return ["Alle Saisons", "2024/25", "2023/24", "2022/23"]

    where_sql = ""
    params: tuple = ()
    if liga not in (None, "", "Alle Ligen") and "league" in columns:
        where_sql = " WHERE league = ?"
        params = (liga,)

    with sqlite3.connect(DB_PATH) as conn:
        seasons = [
            row[0]
            for row in conn.execute(
                f"SELECT DISTINCT season FROM openliga_table{where_sql} ORDER BY season DESC",
                params,
            ).fetchall()
        ]

    return ["Alle Saisons", *seasons] if seasons else ["Alle Saisons"]


@st.cache_data(show_spinner=False)
def get_available_teams(liga: str, saison: str) -> list[str]:
    if not DB_PATH.exists():
        if liga == "Alle Ligen":
            return FALLBACK_ALL_TEAMS
        return FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])

    columns = _table_columns("openliga_table")
    if "team" not in columns:
        if liga == "Alle Ligen":
            return FALLBACK_ALL_TEAMS
        return FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])

    where_clauses = []
    params: list[str] = []
    if liga not in (None, "", "Alle Ligen") and "league" in columns:
        where_clauses.append("league = ?")
        params.append(liga)
    normalized_season = normalize_openliga_season_label(saison)
    if normalized_season and "season" in columns:
        where_clauses.append("season = ?")
        params.append(normalized_season)

    query = "SELECT DISTINCT team FROM openliga_table"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY team"

    with sqlite3.connect(DB_PATH) as conn:
        teams = [row[0] for row in conn.execute(query, tuple(params)).fetchall()]

    if teams:
        return ["Alle Teams", *teams]

    if liga == "Alle Ligen":
        return FALLBACK_ALL_TEAMS
    return FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])


@st.cache_data(show_spinner=False)
def has_wordcloud_data(team_name: str) -> bool:
    if not team_name or team_name == "Alle Teams":
        return False
    return bool(load_wordcloud_frequencies(team_name))


def format_team_option_label(team_name: str) -> str:
    if team_name == "Alle Teams":
        return team_name
    return team_name if has_wordcloud_data(team_name) else f"{team_name} (ohne Wikipedia)"


@st.cache_data(show_spinner=False)
def load_top_kpis_from_db(liga: str, saison: str, team_name: str) -> dict | None:
    """Liest Platz, Punkte, Siege, Niederlagen, Tore und Gegentore aus soccer.db."""
    if not DB_PATH.exists():
        return None

    columns = _table_columns("openliga_table")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        where_clauses = []
        params: list[str] = []

        if liga not in (None, "", "Alle Ligen") and "league" in columns:
            where_clauses.append("league = ?")
            params.append(liga)

        normalized_season = normalize_openliga_season_label(saison)
        if normalized_season and "season" in columns:
            where_clauses.append("season = ?")
            params.append(normalized_season)

        selected_team = normalize_openliga_team_name(team_name)
        if selected_team:
            where_clauses.append("team = ?")
            params.append(selected_team)

        select_fields = [
            "league" if "league" in columns else "'' AS league",
            "season" if "season" in columns else "'' AS season",
            "team",
            "position",
            "points",
            "matches" if "matches" in columns else "0 AS matches",
            "won",
            "lost",
            "goals_for",
            "goals_against",
        ]
        query = f"SELECT {', '.join(select_fields)} FROM openliga_table"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        order_by = ["position ASC"]
        if "season_start_year" in columns:
            order_by.insert(0, "season_start_year DESC")
        elif "season" in columns:
            order_by.insert(0, "season DESC")
        query += " ORDER BY " + ", ".join(order_by) + " LIMIT 1"

        row = conn.execute(query, tuple(params)).fetchone()

    if row is None:
        return None

    return {
        "league": row["league"] if "league" in row.keys() else liga,
        "season": row["season"] if "season" in row.keys() else saison,
        "team": row["team"],
        "Platz": int(row["position"]),
        "Punkte": int(row["points"]),
        "Spiele": int(row["matches"]),
        "Siege": int(row["won"]),
        "Unentschieden": max(int(row["matches"]) - int(row["won"]) - int(row["lost"]), 0),
        "Niederlagen": int(row["lost"]),
        "Tore": int(row["goals_for"]),
        "Gegentore": int(row["goals_against"]),
    }


@st.cache_data(show_spinner=False)
def load_leistung_kpis_from_db(liga: str, saison: str, team_name: str) -> dict | None:
    table_kpis = load_top_kpis_from_db(liga, saison, team_name)
    if table_kpis is None:
        return None

    requested_season = table_kpis["season"]
    statsbomb_season_used = requested_season
    statsbomb_kpis = load_statsbomb_kpis_from_db(table_kpis["team"], requested_season, table_kpis["league"])

    # Falls die gewaehlte Saison keine StatsBomb-Daten hat (z. B. 2024/25),
    # nutze die zuletzt verfuegbare historische Saison fuer das Team.
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

def render_kpi_card(
    label: str,
    value: str | int,
    unit: str = "",
    source: str = "",
    disabled: bool = False,
    accent_color: str = "#2d5a27",
    detail: str = "",
):
    """Rendert eine KPI-Karte mit farbigem Rand im Statistik-UI."""
    display_value = f"{value} {unit}".strip()
    opacity = "0.48" if disabled else "1"
    st.markdown(
        f"""
        <div style="
            opacity: {opacity};
            min-height: 76px;
            padding: 0.45rem 0.6rem 0.42rem 0.6rem;
            border-radius: 15px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-left: 1px solid rgba(148, 163, 184, 0.28);
            background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.96) 100%);
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.10);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        ">
            <div style="font-size: 0.7rem; font-weight: 800; color: #334155; line-height: 1.1; text-transform: uppercase; letter-spacing: 0.04em;">{label}</div>
            <div style="font-size: 1.18rem; font-weight: 850; color: #0f172a; line-height: 1.05; margin-top: 0.1rem; word-break: break-word;">{display_value}</div>
            <div style="font-size: 0.68rem; font-weight: 700; color: rgba(15, 23, 42, 0.72); line-height: 1.1; min-height: 0.85rem;">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_wordcloud_placeholder(source: str = "", disabled: bool = False, team_name: str = ""):
    """Zeigt eine echte Wortwolke für das ausgewählte Team an."""
    selected_team = team_name if team_name and team_name != "Alle Teams" else ""

    with st.container(border=True):
        if disabled:
            st.info("Datenquelle nicht aktiviert")
        elif not selected_team:
            st.info("Bitte waehle ein konkretes Team aus, um die passende Wortwolke zu sehen.")
        else:
            frequencies = load_wordcloud_frequencies(selected_team)
            if frequencies:
                zeige_wortwolke(frequencies, titel=selected_team)
            else:
                st.info(f"Für {selected_team} sind keine Wortwolken-Daten verfügbar.")


def _build_comparison_chart_data(liga: str, saison: str, team_name: str) -> tuple[pd.DataFrame, dict | None]:
    kpis = load_leistung_kpis_from_db(liga, saison, team_name)
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


def _build_comparison_figure(
    chart_data: pd.DataFrame,
    chart_title: str,
    color_map: dict,
    shared_y_max: float,
):
    plot_data = chart_data.copy()
    # Render exact KPI values; zero must stay zero to avoid misleading bar heights.
    plot_data["Anzeigewert"] = plot_data["Wert"]
    plot_data["Wert_Label"] = plot_data["Wert"].apply(
        lambda value: "n/a" if pd.isna(value) else (f"{value:.1f}" if isinstance(value, float) else str(value))
    )

    fig = px.bar(
        plot_data,
        x="Metrik",
        y="Anzeigewert",
        color="Metrik",
        color_discrete_map=color_map,
        text="Wert_Label",
    )
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{x}: %{text}<extra></extra>",
    )
    fig.update_layout(
        title=chart_title,
        height=350,
        xaxis_title="",
        yaxis_title="Wert",
        yaxis_range=[0, shared_y_max],
        showlegend=False,
        bargap=0.35,
        margin=dict(t=60, r=20, b=20, l=20),
    )
    fig.update_yaxes(tickformat=".0f")
    return fig


def render_comparison_chart(team_name: str, liga: str, saison: str, all_teams: list = None):
    """Rendert zwei vergleichbare Barcharts in 2x2 Grid - oben Filter, unten Charts"""
    if all_teams is None:
        all_teams = ["Bayern", "Dortmund", "Leverkusen", "Mainz", "Leipzig"]
    
    top_left, top_right = st.columns(2, gap="medium")
    bottom_left, bottom_right = st.columns(2, gap="medium")
    
    # Farben für die drei Metriken
    color_map = {
        "Tore": "#7ec97e",        # Helles Grün
        "xG-Index pro Spiel": "#4a7c59", # Mittleres Grün
        "Gegentore": "#2d5a27"    # Dunkles Grün
    }

    selected_liga = liga
    selected_saison = saison
    compare_team_options = [
        candidate
        for candidate in get_available_teams(selected_liga, selected_saison)
        if candidate != "Alle Teams"
    ]
    if not compare_team_options:
        compare_team_options = list(dict.fromkeys([team_name, *all_teams])) or [team_name]

    left_team_key = "compare_team_left"
    left_team_source_key = "compare_team_left_source"
    right_team_key = "compare_team_right"

    if st.session_state.get(left_team_source_key) != team_name or left_team_key not in st.session_state:
        st.session_state[left_team_key] = team_name
        st.session_state[left_team_source_key] = team_name

    left_current_team = st.session_state.get(left_team_key, team_name)
    if left_current_team not in compare_team_options:
        left_current_team = team_name if team_name in compare_team_options else compare_team_options[0]

    right_current_team = st.session_state.get(right_team_key)
    if right_current_team not in compare_team_options or right_current_team == left_current_team:
        right_current_team = next((candidate for candidate in compare_team_options if candidate != left_current_team), left_current_team)

    right_team_options = [candidate for candidate in compare_team_options if candidate != left_current_team]
    if not right_team_options:
        right_team_options = compare_team_options[:]

    left_team_options = [candidate for candidate in compare_team_options if candidate != right_current_team]
    if not left_team_options:
        left_team_options = compare_team_options[:]

    if left_current_team not in left_team_options:
        left_current_team = team_name if team_name in left_team_options else left_team_options[0]

    if right_current_team not in right_team_options:
        right_current_team = next((candidate for candidate in right_team_options if candidate != left_current_team), right_team_options[0])

    st.session_state[left_team_key] = left_current_team
    st.session_state[right_team_key] = right_current_team

    with top_left:
        with st.container(border=True):
            filter_label_col, filter_input_col = st.columns([1, 2], gap="small")

            with filter_label_col:
                st.markdown("<div style='padding-top: 0.45rem; font-weight: 600;'>Team</div>", unsafe_allow_html=True)
            with filter_input_col:
                left_team = st.selectbox(
                    "Team",
                    left_team_options,
                    index=left_team_options.index(left_current_team),
                    key=left_team_key,
                    format_func=format_team_option_label,
                    label_visibility="collapsed",
                )

            st.caption(f"Vergleich in gleicher Liga/Saison: {selected_liga} · {selected_saison}")
    
    with top_right:
        with st.container(border=True):
            filter_label_col, filter_input_col = st.columns([1, 2], gap="small")

            with filter_label_col:
                st.markdown("<div style='padding-top: 0.45rem; font-weight: 600;'>Team</div>", unsafe_allow_html=True)
            with filter_input_col:
                right_team = st.selectbox(
                    "Team",
                    right_team_options,
                    index=right_team_options.index(right_current_team),
                    key=right_team_key,
                    format_func=format_team_option_label,
                    label_visibility="collapsed",
                )

            st.caption(f"Vergleich in gleicher Liga/Saison: {selected_liga} · {selected_saison}")

    left_chart_data, left_kpis = _build_comparison_chart_data(selected_liga, selected_saison, left_team)
    right_chart_data, right_kpis = _build_comparison_chart_data(selected_liga, selected_saison, right_team)
    left_label = left_kpis["team"] if left_kpis else left_team
    right_label = right_kpis["team"] if right_kpis else right_team
    left_max = left_chart_data["Wert"].fillna(0).max()
    right_max = right_chart_data["Wert"].fillna(0).max()
    shared_y_max = max(left_max, right_max, 1)
    shared_y_max = max(10, shared_y_max * 1.15)

    st.caption("Hinweis: Der xG-Index pro Spiel ist zur besseren Vergleichbarkeit mit Tore und Gegentore mit Faktor 10 skaliert.")

    with bottom_left:
        fig = _build_comparison_figure(
            left_chart_data,
            left_label,
            color_map,
            shared_y_max,
        )
        st.plotly_chart(fig, width="stretch")
        if left_kpis and left_kpis["xG"] is None:
            st.caption("Für dieses Team liegen in StatsBomb aktuell keine xG-Vergleichsdaten vor.")
        elif left_kpis and left_kpis.get("statsbomb_season_used") and left_kpis["statsbomb_season_used"] != selected_saison:
            st.caption(f"xG basiert auf verfügbarer StatsBomb-Saison {left_kpis['statsbomb_season_used']}.")

    with bottom_right:
        fig = _build_comparison_figure(
            right_chart_data,
            right_label,
            color_map,
            shared_y_max,
        )
        st.plotly_chart(fig, width="stretch")
        if right_kpis and right_kpis["xG"] is None:
            st.caption("Für dieses Vergleichsteam liegen in StatsBomb aktuell keine xG-Vergleichsdaten vor.")
        elif right_kpis and right_kpis.get("statsbomb_season_used") and right_kpis["statsbomb_season_used"] != selected_saison:
            st.caption(f"xG basiert auf verfügbarer StatsBomb-Saison {right_kpis['statsbomb_season_used']}.")


def render_statistics_tab() -> None:
    st.markdown("""
    <style>
        .stats-focus-team {
            color: #2d5a27;
            font-weight: 700;
            font-size: 1.35rem;
            margin-top: 0.45rem;
            margin-bottom: 0.1rem;
        }
        div[data-testid="column"] .stMarkdown {
            width: 100%;
        }
    </style>
    """, unsafe_allow_html=True)

    liga_options = get_available_leagues()

    with st.container():
        col_liga, col_saison, col_team = st.columns([1, 1, 1.2], gap="small")

        with col_liga:
            liga = st.selectbox(
                "Liga",
                liga_options,
                key="stats_liga",
            )

        saison_options = get_available_seasons(liga)
        default_saison_index = 1 if len(saison_options) > 1 else 0
        with col_saison:
            saison = st.selectbox(
                "Saison",
                saison_options,
                index=default_saison_index,
                key="stats_saison",
            )

        team_options = get_available_teams(liga, saison)
        with col_team:
            team = st.selectbox(
                "Team",
                team_options,
                key="stats_team",
                format_func=format_team_option_label,
            )

        st.caption("Teams mit dem Zusatz '(ohne Wikipedia)' haben aktuell keine verfügbare Wortwolke.")

    team_heading = team if team != "Alle Teams" else "Alle Teams"
    st.markdown(
        f'<div class="stats-focus-team">Verein im Fokus: {team_heading}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Aktiver Filter: {liga} · {saison}")
    render_statistics(liga=liga, saison=saison, team=team)


#-----------------------------------------------------
# Seiteneinteilung 
#-----------------------------------------------------

def render_statistics(liga: str, saison: str, team: str, sources_enabled: dict = None):
    
    # Wenn sources_enabled nicht übergeben wird, alle aktivieren
    if sources_enabled is None:
        sources_enabled = {
            "OpenligaDB": True,
            "Statsbomb": True,
            "Wikipedia": True
        }
    
    # Liste der aktivierten Quellen erstellen
    sources_selected = [source for source, enabled in sources_enabled.items() if enabled]

    if saison in (None, "", "Alle Saisons"):
        st.info("Bitte waehle eine konkrete Saison aus. Mit 'Alle Saisons' sind KPI-Werte nicht eindeutig interpretierbar.")
        return
    
    # ===== BEREICH 1: KPIs & Wortwolke =====

    kpi_data = load_top_kpis_from_db(liga, saison, team)
    if kpi_data is None:
        st.warning("Für die aktuelle Filterwahl sind in soccer.db keine OpenLigaDB-KPIs verfügbar.")
    leistung_kpis = load_leistung_kpis_from_db(liga, saison, team)
    
    # Definiere Quellen für jedes Element
    elements_sources = {
        "Platz": "OpenligaDB",
        "Punkte": "OpenligaDB",
        "Siege": "OpenligaDB",
        "Unentschieden": "OpenligaDB",
        "Niederlagen": "OpenligaDB",
        "Tore": "OpenligaDB",
        "Gegentore": "OpenligaDB",
        "StatsBomb-Kennzahl": "Statsbomb",
        "WordCloud": "Wikipedia"
    }

    kpi_colors = {
        "Platz": "#6d28d9",
        "Punkte": "#1d4ed8",
        "StatsBomb-Feld": "#8b5cf6",
        "Siege": "#15803d",
        "Unentschieden": "#d97706",
        "Niederlagen": "#be123c",
        "Tore": "#a16207",
        "Gegentore": "#7c3aed",
        "StatsBomb-Kennzahl": "#4f46e5",
    }

    kpi_rows = [
        [
            {"label": "Platz", "value": kpi_data["Platz"] if kpi_data else "-", "unit": ".", "detail": "", "source": elements_sources["Platz"]},
            {"label": "Punkte", "value": kpi_data["Punkte"] if kpi_data else "-", "unit": "", "detail": "", "source": elements_sources["Punkte"]},
            {"label": "StatsBomb-Feld", "value": "", "unit": "", "detail": "später per SQL befüllen", "source": "Statsbomb"},
        ],
        [
            {"label": "Siege", "value": kpi_data["Siege"] if kpi_data else "-", "unit": "", "detail": "", "source": elements_sources["Siege"]},
            {"label": "Unentschieden", "value": kpi_data["Unentschieden"] if kpi_data else "-", "unit": "", "detail": "", "source": elements_sources["Unentschieden"]},
            {"label": "Niederlagen", "value": kpi_data["Niederlagen"] if kpi_data else "-", "unit": "", "detail": "", "source": elements_sources["Niederlagen"]},
        ],
        [
            {"label": "Tore", "value": leistung_kpis["Tore"] if leistung_kpis else "-", "unit": "", "detail": "", "source": elements_sources["Tore"]},
            {"label": "Gegentore", "value": leistung_kpis["Gegentore"] if leistung_kpis else "-", "unit": "", "detail": "", "source": elements_sources["Gegentore"]},
            {"label": "StatsBomb-Kennzahl", "value": "", "unit": "", "detail": "später per SQL befüllen", "source": elements_sources["StatsBomb-Kennzahl"]},
        ],
    ]

    kpi_col, wordcloud_col = st.columns([0.88, 1.52], gap="large")

    with kpi_col:
        for row_items in kpi_rows:
            row_cols = st.columns(3, gap="small")
            for index, card in enumerate(row_items):
                with row_cols[index]:
                    is_disabled = card["source"] not in sources_selected
                    render_kpi_card(
                        card["label"],
                        card["value"],
                        card["unit"],
                        source=card["source"],
                        disabled=is_disabled,
                        accent_color=kpi_colors.get(card["label"], "#8b5cf6"),
                        detail=card["detail"],
                    )

    with wordcloud_col:
        is_disabled = elements_sources["WordCloud"] not in sources_selected
        render_wordcloud_placeholder(
            source=elements_sources["WordCloud"],
            disabled=is_disabled,
            team_name=team
        )

    if kpi_data and team == "Alle Teams":
        st.caption(f"KPI-Werte zeigen aktuell: {kpi_data['team']} · {kpi_data['league']} · {kpi_data['season']}")
    if kpi_data:
        st.caption(
            f"Datenstand OpenLigaDB: {kpi_data['Spiele']} Spiele · "
            f"{kpi_data['Siege']}S/{kpi_data['Unentschieden']}U/{kpi_data['Niederlagen']}N · "
            f"Quellen: OpenLigaDB (Felder 1-7), StatsBomb (Felder 8-9)"
        )

    st.markdown("<hr style='border: none; height: 2px; background-color: #d3d3d3; margin-top: 1rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)
    
    # ===== BEREICH 2: Team-Vergleich =====
    st.markdown(f"### Team-Vergleich · {liga} · {saison}")
    render_comparison_chart(team, liga, saison, ["Bayern", "Dortmund", "Leverkusen", "Mainz", "Leipzig"])
