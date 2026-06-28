# -----------------------------------------------------
# helpers.py
# -----------------------------------------------------

"""
Hilfsfunktionen für die Streamlit-App

Enthält alle Funktionen zur Datenverarbeitung und Visualisierung.
Die Funktionen werden in app.py importiert und aufgerufen.

Funktionen:
    - zeige_wortwolke(): Erzeugt und zeigt eine Wortwolke
    - render_source_tags(): Zeigt farbige Quellen-Tags
    - render_confidence(): Zeigt Confidence-Balken
    - init_session_state(): Initialisiert Session-State
    - inject_css(): Globales CSS
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

try:
    from wordcloud import WordCloud
except ImportError:  # pragma: no cover - optional dependency
    WordCloud = None

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_wordcloud_frequencies(team_name: str = "", data_path: str | Path | None = None) -> dict:
    """Lädt die Wortwolken-Häufigkeiten für ein Team aus der JSON-Datei."""
    resolved_path = Path(data_path) if data_path else ROOT_DIR / "data" / "tab1_statistik" / "haeufigkeiten_wortwolken.json"

    if not resolved_path.exists():
        return {}

    with resolved_path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    if not team_name:
        return next(iter(data.values()), {})

    normalized_team = team_name.strip().lower()
    for key, frequencies in data.items():
        if key.strip().lower() == normalized_team:
            return frequencies

    for key, frequencies in data.items():
        if normalized_team in key.strip().lower() or key.strip().lower() in normalized_team:
            return frequencies

    return next(iter(data.values()), {})


def zeige_wortwolke(haeufigkeiten: dict, titel: str = "") -> None:
    """
    Erzeugt eine Wortwolke aus einem Worthäufigkeits-Dictionary.

    Falls das Paket wordcloud nicht verfügbar ist, wird ein einfacher
    visueller Fallback mit Matplotlib dargestellt.
    """
    if not haeufigkeiten:
        st.info("Keine Wortwolken-Daten verfügbar.")
        return

    if WordCloud is not None:
        wc = WordCloud(
            width=1100,
            height=700,
            background_color="#f8fafc",
            max_words=90,
            colormap="viridis",
            random_state=42,
            prefer_horizontal=0.9,
        ).generate_from_frequencies(haeufigkeiten)

        fig, ax = plt.subplots(figsize=(11.5, 6.2), dpi=140)
        fig.patch.set_facecolor("#f8fafc")
        ax.set_facecolor("#f8fafc")
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        ax.set_position([0, 0, 1, 1])
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=140, bbox_inches="tight", pad_inches=0, facecolor="#f8fafc")
        plt.close(fig)
        buffer.seek(0)
        st.image(buffer.getvalue(), caption=titel or None, use_container_width=True, output_format="PNG")
        return

    words = sorted(haeufigkeiten.items(), key=lambda item: item[1], reverse=True)[:60]
    if not words:
        st.info("Keine Wortwolken-Daten verfügbar.")
        return

    max_weight = max(weight for _, weight in words)
    fig, ax = plt.subplots(figsize=(11.5, 6.2), dpi=140)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_position([0, 0, 1, 1])
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    cols = 6
    for index, (word, weight) in enumerate(words):
        row, col = divmod(index, cols)
        size = 10 + (weight / max_weight) * 34
        x = 0.04 + (col / cols) * 0.9
        y = 0.92 - (row * 0.13)
        ax.text(x, y, word, fontsize=size, ha="center", va="center")

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=140, bbox_inches="tight", pad_inches=0, facecolor="#f8fafc")
    plt.close(fig)
    buffer.seek(0)
    st.image(buffer.getvalue(), caption=titel or None, use_container_width=True, output_format="PNG")


def render_source_tags(quellen: list):
    """Zeigt farbige Quellen-Tags unter einer Antwort"""
    st.markdown(
        " ".join([
            f'<span class="source-tag tag-{q.lower()}">{q}</span>'
            for q in quellen
        ]),
        unsafe_allow_html=True
    )

def render_confidence(wert: float):
    """Zeigt Confidence-Balken"""
    st.progress(wert, text=f"Confidence: {int(wert*100)}%")

def init_session_state():
    """Initialisiert alle Session-State Variablen"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "beispiel_frage" not in st.session_state:
        st.session_state.beispiel_frage = None

def inject_css():
    """Globales CSS für Source-Tags und Styling"""
    st.markdown("""
    <style>
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

