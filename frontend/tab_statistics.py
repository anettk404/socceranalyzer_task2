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

#-----------------------------------------------------
# Import weiterer Funktionen aus anderen .py-Dateien
#-----------------------------------------------------


#-----------------------------------------------------
# Hilfsfunktionen für UI-Komponenten
#-----------------------------------------------------

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


def render_wordcloud_placeholder(source: str = "", disabled: bool = False):
    """Placeholder für Wortwolke. Kann ausgegraut werden."""
    opacity = "0.4" if disabled else "1"
    with st.container(border=True):
        st.markdown(f"<div style='opacity: {opacity}'>", unsafe_allow_html=True)
        if source:
            st.caption(f"📊 {source}")
        st.subheader("Word Cloud")
        if not disabled:
            st.info("Wortwolke wird hier eingefügt")
        else:
            st.info("Datenquelle nicht aktiviert")
        st.markdown("</div>", unsafe_allow_html=True)


def render_comparison_chart(team_name: str, all_teams: list = None):
    """Rendert zwei vergleichbare Barcharts in 2x2 Grid - oben Filter, unten Charts"""
    if all_teams is None:
        all_teams = ["Bayern", "Dortmund", "Leverkusen", "Mainz", "Leipzig"]
    
    # Filter aus anderen Teams
    other_teams = [t for t in all_teams if t != team_name]
    
    # Oben: Filter
    col_top_left, col_top_right = st.columns(2)
    
    with col_top_left:
        st.write(f"**Team: {team_name}**")
    
    with col_top_right:
        selected_team = st.selectbox("Team vergleichen mit:", other_teams, key="compare_team")
    
    st.markdown("")
    
    # Unten: Charts mit drei verschiedenen Grüntönen
    col_chart1, col_chart2 = st.columns(2)
    
    # Farben für die drei Metriken
    color_map = {
        "Tore": "#7ec97e",        # Helles Grün
        "Chancen": "#4a7c59",     # Mittleres Grün
        "Gegentore": "#2d5a27"    # Dunkles Grün
    }
    
    with col_chart1:
        chart_data = pd.DataFrame({
            "Metrik": ["Tore", "Chancen", "Gegentore"],
            "Wert": [45, 62, 28]
        })
        fig = px.bar(
            chart_data,
            x="Metrik",
            y="Wert",
            color="Metrik",
            color_discrete_map=color_map
        )
        fig.update_layout(height=350, xaxis_title="", yaxis_title="", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        chart_data = pd.DataFrame({
            "Metrik": ["Tore", "Chancen", "Gegentore"],
            "Wert": [38, 55, 32]
        })
        fig = px.bar(
            chart_data,
            x="Metrik",
            y="Wert",
            color="Metrik",
            color_discrete_map=color_map
        )
        fig.update_layout(height=350, xaxis_title="", yaxis_title="", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


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
    
    col_left, col_right = st.columns([1, 2], gap="medium")
    
    # Definiere Quellen für jedes Element
    elements_sources = {
        "Platz": "OpenligaDB",
        "Punkte": "OpenligaDB",
        "Siege": "OpenligaDB",
        "WordCloud": "Wikipedia"
    }
    
    with col_left:
        for label, value, unit in [("Platz", 1, "."), ("Punkte", 75, "Pkt"), ("Siege", 24, "")]:
            source = elements_sources[label]
            is_disabled = source not in sources_selected
            render_kpi_card(label, value, unit, source=source, disabled=is_disabled)
    
    with col_right:
        is_disabled = elements_sources["WordCloud"] not in sources_selected
        render_wordcloud_placeholder(source=elements_sources["WordCloud"], disabled=is_disabled)
    
    st.markdown("<hr style='border: none; height: 2px; background-color: #d3d3d3;'>", unsafe_allow_html=True)
    
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
            render_kpi_card("Tore", 62, "", source=leistung_sources["Tore"], disabled=is_disabled)
        with col_c:
            is_disabled = leistung_sources["Chancenverwertung"] not in sources_selected
            render_kpi_card("Chancenverwertung", "42%", "", source=leistung_sources["Chancenverwertung"], disabled=is_disabled)
    
    with col_defensive:
        st.write("**Defensive**")
        col_g, col_d = st.columns(2)
        with col_g:
            is_disabled = leistung_sources["Gegentore"] not in sources_selected
            render_kpi_card("Gegentore", 28, "", source=leistung_sources["Gegentore"], disabled=is_disabled)
        with col_d:
            is_disabled = leistung_sources["Druckresistenz"] not in sources_selected
            render_kpi_card("Druckresistenz", "71%", "", source=leistung_sources["Druckresistenz"], disabled=is_disabled)
    
    st.markdown("<hr style='border: none; height: 2px; background-color: #d3d3d3;'>", unsafe_allow_html=True)
    
    # ===== BEREICH 3: Team-Vergleich =====
    st.markdown(f"### Team-Vergleich - {team} · {liga} · {saison}")
    render_comparison_chart(team, ["Bayern", "Dortmund", "Leverkusen", "Mainz", "Leipzig"])
