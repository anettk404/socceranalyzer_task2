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
import random
import re
import unicodedata

import matplotlib.pyplot as plt
import streamlit as st

_WORDCLOUD_IMPORT_ERROR: str | None = None

try:
    from wordcloud import WordCloud
except Exception as exc:  # pragma: no cover - optional dependency
    WordCloud = None
    _WORDCLOUD_IMPORT_ERROR = str(exc)

ROOT_DIR = Path(__file__).resolve().parent.parent

_WORDCLOUD_TEAM_ALIASES = {
    "fc bayern munchen": "fc bayern munich",
    "bayern munchen": "fc bayern munich",
    "bayern muenchen": "fc bayern munich",
    "1 fc heidenheim 1846": "1 fc heidenheim",
    "1 fc heidenheim": "1 fc heidenheim",
    "mainz 05": "1 fsv mainz 05",
    "fsv mainz 05": "1 fsv mainz 05",
    "real madrid": "real madrid cf",
    "paris saint germain": "paris saint germain fc",
    "psg": "paris saint germain fc",
}


def _normalize_wordcloud_team_name(team_name: str) -> str:
    normalized = unicodedata.normalize("NFKD", team_name or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    normalized = normalized.replace("&", " und ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\b(cf|fc|sc|sv|ac|as|ssc|vfl|tsg|rb|bv|e v)\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return _WORDCLOUD_TEAM_ALIASES.get(normalized, normalized)


def load_wordcloud_frequencies(team_name: str = "", data_path: str | Path | None = None) -> dict:
    """Lädt die Wortwolken-Häufigkeiten für ein Team aus der JSON-Datei."""
    resolved_path = Path(data_path) if data_path else ROOT_DIR / "data" / "haeufigkeiten_wortwolken.json"

    if not resolved_path.exists():
        return {}

    with resolved_path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    if not team_name:
        return {}

    normalized_team = _normalize_wordcloud_team_name(team_name)
    for key, frequencies in data.items():
        if _normalize_wordcloud_team_name(key) == normalized_team:
            return frequencies

    for key, frequencies in data.items():
        normalized_key = _normalize_wordcloud_team_name(key)
        if normalized_team and (normalized_team in normalized_key or normalized_key in normalized_team):
            return frequencies

    return {}


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

    hint = "Hinweis: Paket 'wordcloud' nicht verfügbar, zeige vereinfachte Visualisierung."
    if _WORDCLOUD_IMPORT_ERROR:
        hint += f" (Grund: {_WORDCLOUD_IMPORT_ERROR})"
    st.caption(hint)

    max_weight = max(weight for _, weight in words)
    fig, ax = plt.subplots(figsize=(11.5, 6.2), dpi=140)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_position([0, 0, 1, 1])
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    rng = random.Random(42)
    cmap = plt.cm.get_cmap("viridis")
    cols = 8
    for index, (word, weight) in enumerate(words):
        row, col = divmod(index, cols)
        size = 10 + (weight / max_weight) * 30
        x_base = 0.06 + (col / cols) * 0.88
        y_base = 0.90 - (row * 0.11)
        x = min(0.96, max(0.04, x_base + rng.uniform(-0.025, 0.025)))
        y = min(0.95, max(0.05, y_base + rng.uniform(-0.02, 0.02)))
        color = cmap(min(1.0, 0.25 + (weight / max_weight) * 0.7))
        ax.text(x, y, word, fontsize=size, ha="center", va="center", color=color, alpha=0.95)

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

