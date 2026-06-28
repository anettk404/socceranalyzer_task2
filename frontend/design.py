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
try:
    from .tab_statistics import render_statistics
    from .tab_clustering import render_clustering_tab
    from .tab_chat import render_chat_tab
except ImportError:  # Fallback, wenn die Datei direkt aus dem Ordner gestartet wird
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

LIGA_OPTIONS = ["Alle Ligen", "1. Bundesliga", "La Liga", "Premier League", "Serie A", "Ligue 1"]
BUNDESLIGA_TEAMS = [
    "Alle Teams",
    "FC Bayern München",
    "Borussia Dortmund",
    "Bayer 04 Leverkusen",
    "RB Leipzig",
    "VfB Stuttgart",
    "Eintracht Frankfurt",
    "SC Freiburg",
    "TSG Hoffenheim",
    "VfL Wolfsburg",
    "Borussia Mönchengladbach",
    "FC Augsburg",
    "Mainz 05",
    "Werder Bremen",
    "1. FC Heidenheim",
    "1. FC Union Berlin",
    "VfL Bochum",
    "SV Darmstadt 98",
]
LA_LIGA_TEAMS = [
    "Alle Teams",
    "Real Madrid",
    "FC Barcelona",
    "Atlético Madrid",
    "Sevilla FC",
    "Villarreal CF",
    "Real Sociedad",
    "Athletic Club",
    "Valencia CF",
    "Celta Vigo",
]
PREMIER_LEAGUE_TEAMS = [
    "Alle Teams",
    "Manchester City",
    "Liverpool FC",
    "Arsenal FC",
    "Chelsea FC",
    "Manchester United",
    "Tottenham Hotspur",
    "Newcastle United",
    "Aston Villa",
    "Leicester City",
]
SERIE_A_TEAMS = [
    "Alle Teams",
    "Inter Mailand",
    "Juventus Turin",
    "AC Mailand",
    "AS Rom",
    "SSC Neapel",
    "Atalanta Bergamo",
    "Lazio Rom",
    "Fiorentina",
    "Bologna FC",
]
LIGUE_1_TEAMS = [
    "Alle Teams",
    "Paris Saint-Germain",
    "Olympique Marseille",
    "Olympique Lyon",
    "AS Monaco",
    "LOSC Lille",
    "Stade Rennais",
    "AJ Auxerre",
    "RC Lens",
    "FC Nantes",
]
TEAM_OPTIONS_BY_LIGA = {
    "Alle Ligen": ["Alle Teams"],
    "1. Bundesliga": BUNDESLIGA_TEAMS,
    "La Liga": LA_LIGA_TEAMS,
    "Premier League": PREMIER_LEAGUE_TEAMS,
    "Serie A": SERIE_A_TEAMS,
    "Ligue 1": LIGUE_1_TEAMS,
}


def get_team_options_for_liga(liga: str) -> list[str]:
    """Gibt die Team-Optionen für die ausgewählte Liga zurück."""
    return TEAM_OPTIONS_BY_LIGA.get(liga, ["Alle Teams"])


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
            LIGA_OPTIONS,
            key="stats_liga"
        )

        saison = st.selectbox(
            "Saison",
            ["Alle Saisons", "2024/2025", "2023/2024", "2022/2023"],
            key="stats_saison"
        )

        team_options = get_team_options_for_liga(liga)
        team = st.selectbox(
            "Team",
            team_options,
            key="stats_team"
        )

    render_statistics(
        liga=liga,
        saison=saison,
        team=team
    )


# -------------------------------------------------
# TAB 2 – Clustering
# -------------------------------------------------

with tab_clustering:
    render_clustering_tab()


# -------------------------------------------------
# TAB 3 – Chat
# -------------------------------------------------

with tab_chat:
    render_chat_tab()


   

