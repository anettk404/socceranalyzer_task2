# -----------------------------------------------
# design.py
# -----------------------------------------------

# Noch zu tun: 
# - Tabs anbinden mit passenden Funktionen siehe unter Setup
# 

"""
Aufbau des Streamlit-Design für den GSA -nur Design, kein Inhalt

Starten aus dem Ordner Frontend mit "uv run streamlit run design.py"
"""

#-------------------------------------------------
# Setup
#-------------------------------------------------

import streamlit as st

#-------------------------------------------------
# Integration weiterer Funktionen aus anderen .py-Dateien
#-------------------------------------------------
from tab_statistics import render_statistics
from tab_clustering import render_clustering_tab
from tab_chat import render_chat_tab


#-------------------------------------------------
# Seitenkonfiguration
#-------------------------------------------------

st.set_page_config(
    page_title="GenSoccerAnalyzer",  # Titel im Browser-Tab
    page_icon="⚽",                   # Icon im Browser-Tab
    layout="wide",                     # "wide" nutzt die volle Bildschirmbreite,
                                       # "centered" wäre die Standard-Breite
    initial_sidebar_state="expanded" # Sidebar direkt sichtbar (ausgeklappt), nicht eingeklappt
)


# CSS für schönes Layout, Gestaltung von Farbe, Größe, Abstand, Form, Schriftart, nicht nur einfache, unformatierte Schrift
# .stab erzeugt CSS-Klassen

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 16px; }
    .source-tag {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 4px;
    }
    .tag-statsbomb { background: #d4edcf; color: #2d5a27; } 
    .tag-wikipedia { background: #e8e0f5; color: #5a3d8a; }
    .tag-openliga  { background: #d0e4f5; color: #2a6496; }
</style>
""", unsafe_allow_html=True)

    
#-------------------------------------------------
# Titel der App
#-------------------------------------------------

st.title("GenSoccerAnalyzer") # große Überschrift, wie h1 in html, erscheint direkt auf der Seite



#-------------------------------------------------
# Sidebar
#-------------------------------------------------



# ─────────────────────────────────────────────────────────────
# HAUPTBEREICH – Tabs
# ─────────────────────────────────────────────────────────────
tab_stats, tab_clustering, tab_chat = st.tabs([
    "📊 Statistiken",
    "🔵 Clustering",
    "💬 Chat-Analyse"
])

# -------------------------------------------------
# TAB 1 – Statistiken
# -------------------------------------------------

with tab_stats:

    with st.sidebar:

        st.subheader("Filter")

        liga = st.selectbox(
            "Liga",
            ["1. Bundesliga", "Champions League"],
            key="stats_liga"
        )

        saison = st.selectbox(
            "Saison",
            ["Alle Saisons", "2024/2025", "2023/2024", "2022/2023"],
            key="stats_saison"
        )

        team = st.selectbox(
            "Team",
            [
                "Alle Teams",
                "FC Bayern München",
                "Borussia Dortmund",
                "Bayer 04 Leverkusen"
            ],
            key="stats_team"
        )

        st.subheader("Datenquellen")

        st.checkbox("Wikipedia", value=True, key="stats_wiki")
        st.checkbox("StatsBomb", value=True, key="stats_statsbomb")
        st.checkbox("OpenLigaDB", value=True, key="stats_openliga")

    render_statistics(
        liga=liga,
        saison=saison,
        team=team
    )


# -------------------------------------------------
# TAB 2 – Clustering
# -------------------------------------------------

with tab_clustering:

    with st.sidebar:

        st.subheader("Filter")

        liga = st.selectbox(
            "Liga",
            ["1. Bundesliga", "Champions League"],
            key="cluster_liga"
        )

        st.selectbox(
            "Saison",
            ["Alle Saisons"],
            disabled=True,
            key="cluster_saison"
        )

        st.selectbox(
            "Team",
            ["Alle Teams"],
            disabled=True,
            key="cluster_team"
        )

        st.subheader("Datenquelle")

        st.checkbox(
            "Wikipedia",
            value=True,
            disabled=True,
            key="cluster_wiki"
        )

        st.checkbox(
            "StatsBomb",
            value=False,
            disabled=True,
            key="cluster_statsbomb"
        )

        st.checkbox(
            "OpenLigaDB",
            value=False,
            disabled=True,
            key="cluster_openliga"
        )

    render_clustering_tab()


# -------------------------------------------------
# TAB 3 – Chat
# -------------------------------------------------

with tab_chat:
    render_chat_tab()


   

