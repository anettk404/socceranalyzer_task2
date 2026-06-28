# -----------------------------------------------
# tab_chat.py
# -----------------------------------------------

import sys
import os
import time
import streamlit as st

# Pfad zum Projekt-Root hinzufügen, damit agents/ importiert werden kann
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.orchestrator import app as graph

EMPTY_STATE = {
    "question": "",
    "route": "",
    "route_reason": "",
    "sql": "",
    "sql_result": "",
    "sub_answers": [],
    "steps": [],
    "active_agent": "",
    "answer": "",
    "confidence": 0.0,
}

AGENT_LABELS = {
    "openligadb": "OpenLigaDB",
    "statsbomb": "StatsBomb",
    "combined": "OpenLigaDB + StatsBomb",
    "rag": "Wikipedia",
    "validator": "Validator",
}

AGENT_COLORS = {
    "openligadb": "#e8f4e8",
    "statsbomb": "#e8f0fb",
    "combined": "#fff3e0",
    "rag": "#f3e8fb",
    "validator": "#f1f5f9",
}

AGENT_BORDER = {
    "openligadb": "#2ecc71",
    "statsbomb": "#3b82f6",
    "combined": "#f39c12",
    "rag": "#9b59b6",
    "validator": "#64748b",
}

BEISPIEL_FRAGEN = [
    "Bayern letzte 5 Spiele ↗",
    "xG Überperformer ↗",
    "Leverkusen 23/24 ↗",
    "Wer steht auf Platz 1? ↗",
    "Welche Titel hat Juventus? ↗",
]

AGENT_STEPS = [
    ("supervisor",  "Supervisor analysiert Frage"),
    ("openligadb",  "OpenLigaDB-Agent lädt Tabellendaten"),
    ("statsbomb",   "StatsBomb-Agent lädt Event-Daten"),
    ("combined",    "Combined-Agent verbindet Datenquellen"),
    ("rag",         "Wikipedia-Agent sucht Hintergrundwissen"),
    ("aggregator",  "Aggregator fasst Teilergebnisse zusammen"),
    ("validator",   "Validator prüft Antwort"),
]


def render_chat_tab():
    st.markdown("""
    <style>
        .agent-badge {
            display: inline-block; padding: 2px 10px; border-radius: 12px;
            font-size: 0.78rem; font-weight: 500; margin: 2px 3px 0 0;
        }
        .conf-high { background:#dcfce7; color:#15803d; padding:3px 10px; border-radius:10px; font-size:0.8rem; }
        .conf-mid  { background:#fef9c3; color:#a16207; padding:3px 10px; border-radius:10px; font-size:0.8rem; }
        .conf-low  { background:#fee2e2; color:#b91c1c; padding:3px 10px; border-radius:10px; font-size:0.8rem; }
        .filter-label { font-size:0.72rem; font-weight:600; color:#6b7280; letter-spacing:0.05em; margin-bottom:4px; }
        .progress-step { font-size:0.82rem; color:#6b7280; padding: 2px 0; }
        .progress-step.done { color:#16a34a; }
        .progress-step.active { color:#1d4ed8; font-weight:600; }
        div[data-testid="stButton"] button {
            width:100%; text-align:left; background:white;
            border:1px solid #e5e7eb; border-radius:8px;
            padding:6px 12px; font-size:0.85rem; color:#374151; margin-bottom:4px;
        }
        div[data-testid="stButton"] button:hover { background:#f9fafb; border-color:#d1d5db; }
        [data-testid="stChatMessage"] { padding: 0.5rem 0; }
    </style>
    """, unsafe_allow_html=True)

    col_sidebar, col_chat = st.columns([1, 2.8])

    with col_sidebar:
        st.markdown('<div class="filter-label">FILTER</div>', unsafe_allow_html=True)
        st.selectbox("", ["Alle Ligen", "Bundesliga", "Champions League"],
                     label_visibility="collapsed", key="liga_filter")
        st.selectbox("", ["Alle Saisons", "2024/25", "2023/24", "2022/23"],
                     label_visibility="collapsed", key="saison_filter")
        st.selectbox("", ["Alle Teams", "Bayern München", "Borussia Dortmund", "Bayer Leverkusen"],
                     label_visibility="collapsed", key="team_filter")

        st.markdown('<div class="filter-label" style="margin-top:1.2rem">DATENQUELLEN</div>', unsafe_allow_html=True)
        st.checkbox("StatsBomb (xG, Pässe, Schüsse)", value=True, key="chat_statsbomb")
        st.checkbox("OpenLigaDB (Tabelle, Ergebnisse)", value=True, key="chat_openliga")
        st.checkbox("Wikipedia (Klubgeschichte)", value=True, key="chat_wiki")

        st.markdown('<div class="filter-label" style="margin-top:1.2rem">BEISPIEL-FRAGEN</div>', unsafe_allow_html=True)
        for bfrage in BEISPIEL_FRAGEN:
            if st.button(bfrage, key=f"btn_{bfrage}"):
                st.session_state["beispiel_frage"] = bfrage.replace(" ↗", "")

    with col_chat:
        st.markdown("""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
            <div style="display:flex;align-items:center;gap:0.6rem">
                <strong>GSA Chat-Analyse</strong>
                <span style="background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;
                             padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600">
                    Multi-Agent aktiv
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if "messages" not in st.session_state:
            st.session_state.messages = []

        if st.button("Gespräch zurücksetzen", key="reset"):
            st.session_state.messages = []
            st.rerun()

        def render_meta(steps: list, confidence: float, sql: str, sql_result: str) -> None:
            badges = ""
            for step in steps:
                label = AGENT_LABELS.get(step, step)
                bg = AGENT_COLORS.get(step, "#f3f4f6")
                border = AGENT_BORDER.get(step, "#9ca3af")
                badges += f'<span class="agent-badge" style="background:{bg};border:1px solid {border};color:#374151">{label}</span>'
            if confidence >= 0.8:
                conf_html = f'<span class="conf-high">● Hohe Verlässlichkeit {confidence:.0%}</span>'
            elif confidence >= 0.6:
                conf_html = f'<span class="conf-mid">● Mittlere Verlässlichkeit {confidence:.0%}</span>'
            else:
                conf_html = f'<span class="conf-low">● Niedrige Verlässlichkeit {confidence:.0%}</span>'
            st.markdown(f"{badges}&nbsp;&nbsp;{conf_html}", unsafe_allow_html=True)

            if sql or sql_result:
                with st.expander("Quellen & SQL anzeigen"):
                    if sql:
                        st.markdown("**Generiertes SQL:**")
                        st.code(sql, language="sql")
                    if sql_result and sql_result != "[]":
                        st.markdown("**Rohdaten aus der Datenbank:**")
                        st.code(sql_result[:2000], language="json")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and "meta" in msg:
                    meta = msg["meta"]
                    render_meta(meta["steps"], meta["confidence"], meta.get("sql", ""), meta.get("sql_result", ""))

        prefill = st.session_state.pop("beispiel_frage", None)
        frage = st.chat_input("Frage auf Deutsch stellen, z.B. Wie steht die Bundesliga?")
        if prefill and not frage:
            frage = prefill

        if frage:
            st.session_state.messages.append({"role": "user", "content": frage})
            with st.chat_message("user"):
                st.markdown(frage)

            with st.chat_message("assistant"):
                progress_placeholder = st.empty()

                def show_progress(completed_steps: list, active: str) -> None:
                    html = ""
                    for key, label in AGENT_STEPS:
                        if key in completed_steps:
                            html += f'<div class="progress-step done">&#10003; {label}</div>'
                        elif key == active:
                            html += f'<div class="progress-step active">&#9679; {label}...</div>'
                    progress_placeholder.markdown(html, unsafe_allow_html=True)

                show_progress([], "supervisor")
                result = None
                completed = []

                for chunk in graph.stream({**EMPTY_STATE, "question": frage}):
                    node = list(chunk.keys())[0]
                    state = chunk[node]

                    if node not in completed:
                        completed.append(node)

                    node_order = [k for k, _ in AGENT_STEPS]
                    next_idx = node_order.index(node) + 1 if node in node_order else -1
                    next_node = node_order[next_idx] if next_idx < len(node_order) else ""
                    show_progress(completed, next_node)

                    result = state

                progress_placeholder.empty()

                answer = result.get("answer", "Keine Antwort erhalten.")
                answer_placeholder = st.empty()
                displayed = ""
                for word in answer.split(" "):
                    displayed += word + " "
                    answer_placeholder.markdown(displayed + "▌")
                    time.sleep(0.03)
                answer_placeholder.markdown(answer)

                render_meta(
                    result.get("steps", []),
                    result.get("confidence", 0.0),
                    result.get("sql", ""),
                    result.get("sql_result", ""),
                )

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "meta": {
                    "steps":      result.get("steps", []),
                    "confidence": result.get("confidence", 0.0),
                    "sql":        result.get("sql", ""),
                    "sql_result": result.get("sql_result", ""),
                },
            })
