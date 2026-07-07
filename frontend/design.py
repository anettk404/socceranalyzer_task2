# -----------------------------------------------
# design.py
# -----------------------------------------------
# Authorin: Annette Kufner

# 
"""
Aufbau des Streamlit-Design für den GSA -nur Design, kein Inhalt

Starten aus dem Ordner Frontend mit "uv run streamlit run design.py"
"""

#-------------------------------------------------
# Setup
#-------------------------------------------------

import importlib.util
import sqlite3
import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "soccer.db"
REQUIRED_DB_TABLES = {
    "openliga_matches",
    "openliga_table",
    "statsbomb_matches",
    "statsbomb_events",
}

#-------------------------------------------------
# Integration weiterer Funktionen aus anderen .py-Dateien
#-------------------------------------------------
def _load_local_module(module_name: str, file_name: str):
    module_path = Path(__file__).resolve().parent / file_name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _db_is_ready() -> bool:
    if not DB_PATH.exists():
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            existing_tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not REQUIRED_DB_TABLES.issubset(existing_tables):
                return False
    except sqlite3.Error:
        return False

    return True


@st.cache_resource(show_spinner=False)
def _bootstrap_database_if_needed() -> tuple[bool, str]:
    if _db_is_ready():
        return True, "ready"

    ingest_path = PROJECT_ROOT / "data" / "structured_data" / "ingest.py"
    if not ingest_path.exists():
        return False, f"Ingestion-Skript nicht gefunden: {ingest_path}"

    try:
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        ingest_module = _load_module_from_path("structured_data_ingest", ingest_path)
        ingest_module.main()
    except Exception as exc:
        return False, str(exc)

    if not _db_is_ready():
        return False, "Datenbank wurde erstellt, enthält aber nicht alle erwarteten Tabellen."

    return True, "bootstrapped"


try:
    from . import tab_statistics
    from .tab_clustering import render_clustering_tab
    from .tab_chat import render_chat_tab
except ImportError:  # Fallback, wenn die Datei direkt aus dem Ordner gestartet wird
    tab_statistics = _load_local_module("tab_statistics_local", "tab_statistics.py")
    render_clustering_tab = _load_local_module("tab_clustering_local", "tab_clustering.py").render_clustering_tab
    render_chat_tab = _load_local_module("tab_chat_local", "tab_chat.py").render_chat_tab


#-------------------------------------------------
# Seitenkonfiguration
#-------------------------------------------------

st.set_page_config(
    page_title="GenSoccerAnalyzer",  # Titel im Browser-Tab
    page_icon="⚽",                   # Icon im Browser-Tab
    layout="wide",                     # "wide" nutzt die volle Bildschirmbreite,
                                       # "centered" wäre die Standard-Breite
    initial_sidebar_state="collapsed"
)


# CSS für schönes Layout, Gestaltung von Farbe, Größe, Abstand, Form, Schriftart, nicht nur einfache, unformatierte Schrift
# .stab erzeugt CSS-Klassen

st.markdown("""
<style>
    [data-testid="stSidebar"], [data-testid="stSidebarNav"], [data-testid="collapsedControl"] {
        display: none !important;
    }
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

with st.spinner("Initialisiere Datenbank..."):
    db_ok, db_status = _bootstrap_database_if_needed()

if not db_ok:
    st.error(
        "Datenbank-Bootstrap fehlgeschlagen. Einige Statistiken sind ggf. nicht verfügbar."
    )
    st.caption(f"Grund: {db_status}")
elif db_status == "bootstrapped" and not st.session_state.get("db_bootstrap_shown"):
    st.success("Lokale Datenbank wurde beim Start automatisch erstellt.")
    st.session_state["db_bootstrap_shown"] = True



#-------------------------------------------------
# Sidebar - entfernt
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
    tab_statistics.render_statistics_tab()


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


   

