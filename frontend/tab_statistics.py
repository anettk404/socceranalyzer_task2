"""
tab_statistics.py – Statistiken-Tab

------------------------------------------------------------------------------------------------
Design der KPI-Karten (Platz, Punkte, Siege, Tore, Chancenverwertung, Gegentore, Druckresistenz)
Word Cloud pro Verein (Wikipedia)
Balkendiagramme (Vergleich zweier Teams)
------------------------------------------------------------------------------------------------
"""

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

from Tab1_Statistiken.statsbomb_collector_statistics_tab import (  # noqa: E402
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

    query = "SELECT DISTINCT season FROM openliga_table"
    params: tuple = ()
    if liga not in (None, "", "Alle Ligen") and "league" in columns:
        query += " WHERE league = ?"
        params = (liga,)
    query += " ORDER BY season DESC"

    with sqlite3.connect(DB_PATH) as conn:
        seasons = [row[0] for row in conn.execute(query, params).fetchall()]

    return ["Alle Saisons", *seasons] if seasons else ["Alle Saisons"]


@st.cache_data(show_spinner=False)
def get_available_teams(liga: str, saison: str) -> list[str]:
    if not DB_PATH.exists():
        return FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])

    columns = _table_columns("openliga_table")
    if "team" not in columns:
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

    return ["Alle Teams", *teams] if teams else FALLBACK_TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])


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
        "Siege": int(row["won"]),
        "Niederlagen": int(row["lost"]),
        "Tore": int(row["goals_for"]),
        "Gegentore": int(row["goals_against"]),
    }


@st.cache_data(show_spinner=False)
def load_leistung_kpis_from_db(liga: str, saison: str, team_name: str) -> dict | None:
    table_kpis = load_top_kpis_from_db(liga, saison, team_name)
    if table_kpis is None:
        return None

    statsbomb_kpis = load_statsbomb_kpis_from_db(table_kpis["team"], table_kpis["season"], table_kpis["league"])
    return {
        "team": table_kpis["team"],
        "league": table_kpis["league"],
        "season": table_kpis["season"],
        "Tore": table_kpis["Tore"],
        "Gegentore": table_kpis["Gegentore"],
        "Chancenverwertung": statsbomb_kpis["Chancenverwertung"] if statsbomb_kpis else None,
        "Druckresistenz": statsbomb_kpis["Druckresistenz"] if statsbomb_kpis else None,
    }

def render_kpi_card(label: str, value: str | int, unit: str = "", source: str = "", disabled: bool = False):
    """Rendert eine KPI-Karte mit Label und Wert. Kann ausgegraut werden."""
    opacity = "0.4" if disabled else "1"
    with st.container(border=True):
        if disabled:
            st.markdown(f"<div style='opacity: {opacity}'><strong>{label}</strong><br>({value} {unit})</div>", unsafe_allow_html=True)
        else:
            st.metric(label=label, value=f"{value} {unit}".strip())
        if source:
            st.caption(f"📊 {source}")


def render_wordcloud_placeholder(source: str = "", disabled: bool = False, team_name: str = ""):
    """Zeigt eine echte Wortwolke für das ausgewählte Team an."""
    selected_team = team_name if team_name and team_name != "Alle Teams" else ""

    st.markdown("### Word Cloud aus Wikipedia")
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
        return pd.DataFrame({"Metrik": ["Tore", "Chancenverwertung", "Gegentore"], "Wert": [0, 0, 0]}), None

    chart_data = pd.DataFrame({
        "Metrik": ["Tore", "Chancenverwertung", "Gegentore"],
        "Wert": [
            kpis["Tore"],
            kpis["Chancenverwertung"] if kpis["Chancenverwertung"] is not None else 0,
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
    min_visible_bar = max(shared_y_max * 0.04, 0.6)
    plot_data["Anzeigewert"] = plot_data["Wert"].apply(lambda value: min_visible_bar if value == 0 else value)
    plot_data["Wert_Label"] = plot_data["Wert"].apply(lambda value: f"{value:.1f}" if isinstance(value, float) else str(value))

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
        "Chancenverwertung": "#4a7c59",     # Mittleres Grün
        "Gegentore": "#2d5a27"    # Dunkles Grün
    }

    left_chart_data, left_kpis = _build_comparison_chart_data(liga, saison, team_name)
    
    with top_left:
        with st.container(border=True):
            left_label = left_kpis["team"] if left_kpis else team_name
            st.markdown(f"**Team:** {left_label}")

    with top_right:
        with st.container(border=True):
            compare_liga_options = [entry for entry in get_available_leagues() if entry != "Alle Ligen"]
            compare_liga_index = compare_liga_options.index(liga) if liga in compare_liga_options else 0

            filter_label_col, filter_input_col = st.columns([1, 2], gap="small")

            with filter_label_col:
                st.markdown("<div style='padding-top: 0.45rem; font-weight: 600;'>Liga</div>", unsafe_allow_html=True)
            with filter_input_col:
                selected_liga = st.selectbox(
                    "Liga",
                    compare_liga_options,
                    key="compare_liga",
                    index=compare_liga_index,
                    label_visibility="collapsed",
                )

            filter_label_col, filter_input_col = st.columns([1, 2], gap="small")

            with filter_label_col:
                st.markdown("<div style='padding-top: 0.45rem; font-weight: 600;'>Saison</div>", unsafe_allow_html=True)
            with filter_input_col:
                selected_saison = st.selectbox(
                    "Saison",
                    get_available_seasons(selected_liga)[1:] or ["2022/23", "2023/24", "2024/25"],
                    key="compare_saison",
                    label_visibility="collapsed",
                )

            compare_team_options = [
                candidate
                for candidate in get_available_teams(selected_liga, selected_saison)
                if candidate != "Alle Teams" and candidate != team_name
            ]
            if not compare_team_options:
                compare_team_options = [candidate for candidate in all_teams if candidate != team_name] or [team_name]

            filter_label_col, filter_input_col = st.columns([1, 2], gap="small")

            with filter_label_col:
                st.markdown("<div style='padding-top: 0.45rem; font-weight: 600;'>Team</div>", unsafe_allow_html=True)
            with filter_input_col:
                selected_team = st.selectbox(
                    "Team",
                    compare_team_options,
                    key="compare_team",
                    format_func=format_team_option_label,
                    label_visibility="collapsed",
                )

    right_chart_data, right_kpis = _build_comparison_chart_data(selected_liga, selected_saison, selected_team)
    left_label = left_kpis["team"] if left_kpis else team_name
    right_label = right_kpis["team"] if right_kpis else selected_team
    shared_y_max = max(left_chart_data["Wert"].max(), right_chart_data["Wert"].max(), 1)
    shared_y_max = max(10, shared_y_max * 1.15)

    with bottom_left:
        fig = _build_comparison_figure(
            left_chart_data,
            left_label,
            color_map,
            shared_y_max,
        )
        st.plotly_chart(fig, use_container_width=True)
        if (left_chart_data["Wert"] == 0).any():
            st.caption("Nullwerte werden als schmale Vergleichsbalken dargestellt.")
        if left_kpis and left_kpis["Chancenverwertung"] is None:
            st.caption("Für dieses Team liegen in StatsBomb aktuell keine Vergleichsdaten vor.")

    with bottom_right:
        fig = _build_comparison_figure(
            right_chart_data,
            right_label,
            color_map,
            shared_y_max,
        )
        st.plotly_chart(fig, use_container_width=True)
        if (right_chart_data["Wert"] == 0).any():
            st.caption("Nullwerte werden als schmale Vergleichsbalken dargestellt.")
        if right_kpis and right_kpis["Chancenverwertung"] is None:
            st.caption("Für dieses Vergleichsteam liegen in StatsBomb aktuell keine Vergleichsdaten vor.")


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
    
    # ===== BEREICH 1: KPIs & Wortwolke =====
    st.markdown("### Übersicht")

    kpi_data = load_top_kpis_from_db(liga, saison, team)
    if kpi_data is None:
        st.warning("Für die aktuelle Filterwahl sind in soccer.db keine OpenLigaDB-KPIs verfügbar.")
    leistung_kpis = load_leistung_kpis_from_db(liga, saison, team)
    
    # Definiere Quellen für jedes Element
    elements_sources = {
        "Platz": "OpenligaDB",
        "Punkte": "OpenligaDB",
        "Siege": "OpenligaDB",
        "Niederlagen": "OpenligaDB",
        "WordCloud": "Wikipedia"
    }

    kpi_labels = [
        ("Platz", kpi_data["Platz"] if kpi_data else "-", "."),
        ("Punkte", kpi_data["Punkte"] if kpi_data else "-", "Pkt"),
        ("Siege", kpi_data["Siege"] if kpi_data else "-", ""),
        ("Niederlagen", kpi_data["Niederlagen"] if kpi_data else "-", ""),
    ]
    kpi_cols = st.columns(4, gap="small")
    for index, (label, value, unit) in enumerate(kpi_labels):
        with kpi_cols[index]:
            source = elements_sources[label]
            is_disabled = source not in sources_selected
            render_kpi_card(label, value, unit, source=source, disabled=is_disabled)

    if kpi_data and team == "Alle Teams":
        st.caption(f"KPI-Werte zeigen aktuell: {kpi_data['team']} · {kpi_data['league']} · {kpi_data['season']}")

    st.markdown("<hr style='border: none; height: 2px; background-color: #d3d3d3; margin-top: 1rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)

    is_disabled = elements_sources["WordCloud"] not in sources_selected
    render_wordcloud_placeholder(
        source=elements_sources["WordCloud"],
        disabled=is_disabled,
        team_name=team
    )
    st.markdown("<hr style='border: none; height: 2px; background-color: #d3d3d3; margin-top: 1rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)
    
    # ===== BEREICH 2: Thematische KPI-Paare =====
    st.markdown(f"### Leistung - {team} · {liga} · {saison}")
    
    # Definiere Quellen für Leistungs-KPIs
    leistung_sources = {
        "Tore": "OpenligaDB",
        "Chancenverwertung": "Statsbomb",
        "Gegentore": "OpenligaDB",
        "Druckresistenz": "Statsbomb"
    }
    
    # KPI-Paare
    col_offensive, col_defensive = st.columns(2, gap="medium")
    
    with col_offensive:
        st.write("**Offensive**")
        col_t, col_c = st.columns(2)
        with col_t:
            is_disabled = leistung_sources["Tore"] not in sources_selected
            render_kpi_card("Tore", leistung_kpis["Tore"] if leistung_kpis else "-", "", source=leistung_sources["Tore"], disabled=is_disabled)
        with col_c:
            is_disabled = leistung_sources["Chancenverwertung"] not in sources_selected
            chance_value = leistung_kpis["Chancenverwertung"] if leistung_kpis and leistung_kpis["Chancenverwertung"] is not None else "-"
            render_kpi_card("Chancenverwertung", chance_value, "", source=leistung_sources["Chancenverwertung"], disabled=is_disabled)
    
    with col_defensive:
        st.write("**Defensive**")
        col_g, col_d = st.columns(2)
        with col_g:
            is_disabled = leistung_sources["Gegentore"] not in sources_selected
            render_kpi_card("Gegentore", leistung_kpis["Gegentore"] if leistung_kpis else "-", "", source=leistung_sources["Gegentore"], disabled=is_disabled)
        with col_d:
            is_disabled = leistung_sources["Druckresistenz"] not in sources_selected
            druck_value = f"{leistung_kpis['Druckresistenz']}%" if leistung_kpis and leistung_kpis["Druckresistenz"] is not None else "-"
            render_kpi_card("Druckresistenz", druck_value, "", source=leistung_sources["Druckresistenz"], disabled=is_disabled)

    if leistung_kpis and (leistung_kpis["Chancenverwertung"] is None or leistung_kpis["Druckresistenz"] is None):
        st.caption("StatsBomb-Daten sind für diese Liga/Saison aktuell nicht in soccer.db verfügbar.")
    
    st.markdown("<hr style='border: none; height: 2px; background-color: #d3d3d3;'>", unsafe_allow_html=True)
    
    # ===== BEREICH 3: Team-Vergleich =====
    st.markdown(f"### Team-Vergleich - {team} · {liga} · {saison}")
    render_comparison_chart(team, liga, saison, ["Bayern", "Dortmund", "Leverkusen", "Mainz", "Leipzig"])
