"""
tab_statistics.py – Statistiken-Tab

------------------------------------------------------------------------------------------------
Design der KPI-Karten (Platz, Punkte, Siege, Tore, Gegentore, xG)
Word Cloud pro Verein (Wikipedia)
Sentiment-Analyse-Feld (Wikipedia)
Balkendiagramme (Vergleich zweier Teams)
etc.
------------------------------------------------------------------------------------------------
"""
# Authorin: Annette Kufner

# Hinweis: Dieses Skript wurde mithilfe von Codex, Gemini und Claude entwickelt.


# =====================================================
# 1) Grundsetup: Imports und Pfadkonfiguration
# =====================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from helpers import load_wordcloud_frequencies, zeige_wortwolke
except ImportError:  # pragma: no cover - fallback for different execution contexts
    from frontend.helpers import load_wordcloud_frequencies, zeige_wortwolke

from services.stats_repository import (  # noqa: E402
    get_available_leagues as repo_get_available_leagues,
    get_available_seasons as repo_get_available_seasons,
    get_available_teams as repo_get_available_teams,
    load_top_kpis_from_db as repo_load_top_kpis_from_db,
)
from services.stats_tab_service import (  # noqa: E402
    build_comparison_chart_data_for_stats_tab,
    get_team_sentiment_for_stats_tab,
    load_leistung_kpis_for_stats_tab,
)


# =====================================================
# 2) Datenzugriff: verfügbare Filterwerte aus der DB
# =====================================================

@st.cache_data(show_spinner=False)
def get_available_leagues() -> list[str]:
    """UI-Wrapper für verfügbare Ligen aus dem Repository-Layer."""
    return repo_get_available_leagues()


@st.cache_data(show_spinner=False)
def get_available_seasons(liga: str) -> list[str]:
    """UI-Wrapper für verfügbare Saisons aus dem Repository-Layer."""
    return repo_get_available_seasons(liga)


@st.cache_data(show_spinner=False)
def get_available_teams(liga: str, saison: str) -> list[str]:
    """UI-Wrapper für verfügbare Teams aus dem Repository-Layer."""
    return repo_get_available_teams(liga, saison)


@st.cache_data(show_spinner=False)
def has_wordcloud_data(team_name: str) -> bool:
    """Prüft, ob für ein Team Wikipedia-Wortwolkenfrequenzen verfügbar sind."""
    if not team_name or team_name == "Alle Teams":
        return False
    return bool(load_wordcloud_frequencies(team_name))


def format_team_option_label(team_name: str) -> str:
    """Kennzeichnet Teams ohne Wikipedia-Daten direkt im Select-Label."""
    if team_name == "Alle Teams":
        return team_name
    return team_name if has_wordcloud_data(team_name) else f"{team_name} (ohne Wikipedia)"


def format_liga_option_label(liga_name: str) -> str:
    """Formatiert Liga-Bezeichnungen für die UI-Anzeige."""
    if liga_name == "1. Bundesliga":
        return "Bundesliga"
    return liga_name


# =====================================================
# 3) KPI-Loader: OpenLigaDB + StatsBomb Kombination
# =====================================================

@st.cache_data(show_spinner=False)
def load_top_kpis_from_db(liga: str, saison: str, team_name: str) -> dict | None:
    """UI-Wrapper für Top-KPIs aus dem Repository-Layer."""
    return repo_load_top_kpis_from_db(liga, saison, team_name)


@st.cache_data(show_spinner=False)
def load_leistung_kpis_from_db(liga: str, saison: str, team_name: str) -> dict | None:
    """UI-Wrapper für Leistungs-KPIs aus dem Business-Layer."""
    return load_leistung_kpis_for_stats_tab(liga, saison, team_name)


# =====================================================
# 4) UI-Bausteine: KPI-Card + Sentiment-Card + Wortwolke
# =====================================================

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
            min-height: 86px;
            padding: 0.55rem 0.68rem 0.5rem 0.68rem;
            border-radius: 15px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-left: 1px solid rgba(148, 163, 184, 0.28);
            background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.96) 100%);
            box-shadow: 0 12px 26px rgba(15, 23, 42, 0.10);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 0.18rem;
            overflow: hidden;
        ">
            <div style="font-size: 0.63rem; font-weight: 800; color: #334155; line-height: 1.0; text-transform: uppercase; letter-spacing: 0.03em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{label}</div>
            <div style="font-size: 1.02rem; font-weight: 850; color: #0f172a; line-height: 1.0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{display_value}</div>
            <div style="font-size: 0.63rem; font-weight: 700; color: rgba(15, 23, 42, 0.72); line-height: 1.0; min-height: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_team_sentiment(team_name: str) -> dict | None:
    """Lädt teambezogene Sentiment-Werte aus der Wikipedia-JSON über den Service."""
    try:
        return get_team_sentiment_for_stats_tab(team_name)
    except Exception:
        return None


def _sentiment_color(sentiment_label: str) -> str:
    """Mappt die Textstimmung auf die visuelle Punktfarbe."""
    if "Sehr Positiv" in sentiment_label:
        return "#16a34a"
    if "Positiv" in sentiment_label:
        return "#f97316"
    return "#eab308"


def render_sentiment_section(team_name: str, source_enabled: bool = True):
    """Rendert die Sentiment-Sektion unterhalb der KPI-Übersicht."""
    st.markdown('<div class="stats-section-title">Sentiment Analyse</div>', unsafe_allow_html=True)

    if not source_enabled:
        st.info("Datenquelle Wikipedia ist deaktiviert.")
        return

    if not team_name or team_name == "Alle Teams":
        st.info("Bitte ein konkretes Team auswählen, um den Sentiment-Wert anzuzeigen.")
        return

    try:
        team_sentiment = load_team_sentiment(team_name)
    except Exception:
        st.info("Sentiment-Daten sind aktuell nicht verfügbar.")
        return

    if team_sentiment is None:
        st.info("Für dieses Team sind aktuell keine Sentiment-Daten verfügbar.")
        return

    # Der Emoji-Punkt im Text wird entfernt, da die Farbkugel die Bewertung bereits visualisiert.
    mood = team_sentiment["label"]
    point_color = _sentiment_color(mood)
    mood_text = mood.replace("🟢 ", "").replace("🟠 ", "").replace("🟡 ", "")
    st.markdown(
        f"""
        <div style="
            margin-top: 0.15rem;
            padding: 0.9rem 1rem;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.25);
            background: linear-gradient(135deg, rgba(241, 245, 249, 0.95) 0%, rgba(255, 255, 255, 0.96) 100%);
            box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
        ">
            <div style="font-size: 0.72rem; font-weight: 800; color: #334155; text-transform: uppercase; letter-spacing: 0.05em;">Wikipedia Sentiment</div>
            <div style="margin-top: 0.35rem; font-size: 1.35rem; font-weight: 850; color: #0f172a; line-height: 1;">{team_sentiment['score']:.4f}</div>
            <div style="margin-top: 0.45rem; font-size: 0.95rem; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 0.45rem;">
                <span style="display: inline-block; width: 0.72rem; height: 0.72rem; border-radius: 999px; background: {point_color};"></span>
                <span>{mood_text}</span>
            </div>
            <div style="margin-top: 0.28rem; font-size: 0.75rem; color: #475569;">Verein: {team_sentiment['team']}</div>
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
    """Baut die drei Vergleichsmetriken (Tore, xG-Index, Gegentore) für ein Team."""
    return build_comparison_chart_data_for_stats_tab(liga, saison, team_name)


def _build_comparison_figure(
    chart_data: pd.DataFrame,
    chart_title: str,
    color_map: dict,
    shared_y_max: float,
):
    """Erstellt das Plotly-Balkendiagramm für ein Team."""
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
    
    # Grid: oben Team-Filter, unten die beiden Vergleichs-Charts.
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

    # Linkes Team wird bei Wechsel des Fokus-Teams automatisch synchronisiert.
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

    # Obere Filterleiste links/rechts.
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

    # Datengrundlage für beide Charts laden und gemeinsame Y-Achse bestimmen.
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
    """Entry-Point des Statistik-Tabs: Filter oben, Inhalte darunter."""
    st.markdown("""
    <style>
        .stats-focus-team {
            color: #2d5a27;
            font-family: var(--gsa-heading-font, "Segoe UI", sans-serif);
            font-weight: 700;
            font-size: 1.18rem;
            line-height: 1.08;
            letter-spacing: -0.01em;
            margin-top: 0.45rem;
            margin-bottom: 0.12rem;
        }
        .stats-section-title {
            color: #1f2937;
            font-family: var(--gsa-heading-font, "Segoe UI", sans-serif);
            font-weight: 700;
            font-size: 1.02rem;
            line-height: 1.08;
            letter-spacing: -0.01em;
            margin-top: 0.3rem;
            margin-bottom: 0.05rem;
        }
        div[data-testid="column"] .stMarkdown {
            width: 100%;
        }
    </style>
    """, unsafe_allow_html=True)

    # Filterkopf mit Liga/Saison/Team für den gesamten Tab.
    liga_options = get_available_leagues()

    with st.container():
        col_liga, col_saison, col_team = st.columns([1, 1, 1.2], gap="small")

        with col_liga:
            liga = st.selectbox(
                "Liga",
                liga_options,
                key="stats_liga",
                format_func=format_liga_option_label,
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

    # Fokuszeile zeigt, welches Team aktuell die KPI- und Sentimentkarten steuert.
    team_heading = team if team != "Alle Teams" else "Alle Teams"
    st.markdown(
        f'<div class="stats-focus-team">Verein im Fokus: {team_heading}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Aktiver Filter: {format_liga_option_label(liga)} · {saison}")
    render_statistics(liga=liga, saison=saison, team=team)


# =====================================================
# 5) Seitenlogik: KPI-Bereich, Sentiment, Wortwolke, Vergleich
# =====================================================

def render_statistics(liga: str, saison: str, team: str, sources_enabled: dict = None):
    
    # Wenn keine Quellenauswahl übergeben wurde, sind alle Datenquellen aktiv.
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
    
    # Bereich 1: KPI-Karten links, Wortwolke rechts.

    kpi_data = load_top_kpis_from_db(liga, saison, team)
    if kpi_data is None:
        st.warning("Für die aktuelle Filterwahl sind in soccer.db keine OpenLigaDB-KPIs verfügbar.")
    leistung_kpis = load_leistung_kpis_from_db(liga, saison, team)
    
    # Quellen-Mapping steuert, welche UI-Elemente bei deaktivierten Quellen ausgegraut werden.
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

    # Reihenfolge und Gruppierung der KPI-Karten im 3x3-Raster.
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

    kpi_col, wordcloud_col = st.columns([1.05, 1.35], gap="large")

    with kpi_col:
        st.markdown('<div class="stats-section-title">Übersicht</div>', unsafe_allow_html=True)
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

        st.markdown("<div style='height: 0.35rem;'></div>", unsafe_allow_html=True)
        # Sentiment wird direkt unter den KPI-Reihen angezeigt.
        render_sentiment_section(
            team_name=team,
            source_enabled=elements_sources["WordCloud"] in sources_selected,
        )

    with wordcloud_col:
        is_disabled = elements_sources["WordCloud"] not in sources_selected
        render_wordcloud_placeholder(
            source=elements_sources["WordCloud"],
            disabled=is_disabled,
            team_name=team
        )

    # Zusatzhinweis, wenn kein konkretes Team ausgewählt ist.
    if kpi_data and team == "Alle Teams":
        st.caption(f"KPI-Werte zeigen aktuell: {kpi_data['team']} · {kpi_data['league']} · {kpi_data['season']}")
    if kpi_data:
        # Kurzer Datenstand-Hinweis unter dem oberen Bereich.
        st.caption(
            f"Datenstand OpenLigaDB: {kpi_data['Spiele']} Spiele"
        )

    st.markdown(
        """
        <div style='height: 1rem;'></div>
        <div style='height: 10px; border-radius: 999px; background: linear-gradient(90deg, rgba(148,163,184,0.12) 0%, rgba(148,163,184,0.32) 50%, rgba(148,163,184,0.12) 100%);'></div>
        <div style='height: 0.8rem;'></div>
        """,
        unsafe_allow_html=True,
    )
    
    # Bereich 2: direkter Teamvergleich mit zwei synchronen Diagrammen.
    st.markdown(
        f'<div class="stats-focus-team">Teamvergleich: {format_liga_option_label(liga)} · {saison}</div>',
        unsafe_allow_html=True,
    )
    render_comparison_chart(team, liga, saison, ["Bayern", "Dortmund", "Leverkusen", "Mainz", "Leipzig"])
