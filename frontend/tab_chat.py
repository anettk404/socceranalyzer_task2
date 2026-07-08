# -----------------------------------------------
# tab_chat.py
# Autor: Selma Elezovic
# Streamlit Chat-Interface: nimmt Nutzerfragen entgegen, streamt den
# Agenten-Durchlauf mit Live-Fortschrittsanzeige und zeigt Antwort,
# Confidence-Badge und SQL-Rohdaten an.
# -----------------------------------------------

import sys
import os
import time
import streamlit as st

# Pfad zum Projekt-Root hinzufügen, damit agents/ importiert werden kann
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.orchestrator import app as graph

# Leerer Startzustand für jeden neuen Graphen-Aufruf.
# Alle Felder müssen vorhanden sein, da der LangGraph-Graph typisiert ist.
EMPTY_STATE = {
    "question": "",
    "chat_history": "",
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

# Anzeigenamen für die einzelnen Agenten (werden als Badge-Labels genutzt)
AGENT_LABELS = {
    "openligadb": "OpenLigaDB",
    "statsbomb": "StatsBomb",
    "combined": "OpenLigaDB + StatsBomb",
    "rag": "Wikipedia",
    "validator": "Validator",
}

# Hintergrundfarben der Agent-Badges — farblich nach Datenquelle getrennt
AGENT_COLORS = {
    "openligadb": "#e8f4e8",
    "statsbomb": "#e8f0fb",
    "combined": "#fff3e0",
    "rag": "#f3e8fb",
    "validator": "#f1f5f9",
}

# Rahmenfarben der Agent-Badges (passend zu den Hintergrundfarben)
AGENT_BORDER = {
    "openligadb": "#2ecc71",
    "statsbomb": "#3b82f6",
    "combined": "#f39c12",
    "rag": "#9b59b6",
    "validator": "#64748b",
}

# Vorgefertigte Fragen die als Schnellauswahl in der Sidebar angezeigt werden
BEISPIEL_FRAGEN = [
    "Bayern letzte 5 Spiele ↗",
    "xG Überperformer ↗",
    "Leverkusen 23/24 ↗",
    "Wer steht auf Platz 1? ↗",
    "Welche Titel hat Juventus? ↗",
]

# Reihenfolge und Beschriftung der Fortschrittsanzeige während der Verarbeitung.
# Der Supervisor kann mehrfach erscheinen (iterativer Loop), wird aber nur einmal angezeigt.
AGENT_STEPS = [
    ("supervisor",  "Supervisor analysiert Frage"),
    ("openligadb",  "OpenLigaDB-Agent lädt Tabellendaten"),
    ("statsbomb",   "StatsBomb-Agent lädt Event-Daten"),
    ("combined",    "Combined-Agent verbindet Datenquellen"),
    ("rag",         "Wikipedia-Agent sucht Hintergrundwissen"),
    ("aggregator",  "Aggregator fasst Teilergebnisse zusammen"),
    ("validator",   "Validator prüft Antwort"),
]


def _build_history_string(messages: list) -> str:
    """Baut einen kompakten Gesprächsverlauf für den Graphen-Input.

    Nur letzte 3 Runden um das Token-Limit von gpt-4o-mini nicht zu überschreiten.
    Paare werden als 'User: … / Assistent: …' formatiert und mit Trennlinien verbunden.
    """
    pairs = []
    i = 0
    while i < len(messages) - 1:
        # Nur vollständige User+Assistent-Paare aufnehmen
        if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
            pairs.append(
                f"User: {messages[i]['content']}\nAssistent: {messages[i + 1]['content']}"
            )
            i += 2
        else:
            i += 1
    # Nur die letzten 3 Paare übergeben, ältere werden verworfen
    return "\n\n---\n\n".join(pairs[-3:])



def render_chat_tab():
    """Rendert den gesamten Chat-Tab mit Beispielfragen, Gesprächsverlauf und Eingabefeld."""

    # Inline-CSS für Badges, Confidence-Ampel und Q&A-Runden-Darstellung
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

        /* Ältere Runden leicht zurücktreten lassen */
        .qa-round-old {
            opacity: 0.55;
            margin-bottom: 1.2rem;
            padding: 0.75rem 1rem;
            border-radius: 10px;
            border-left: 3px solid #e5e7eb;
        }
        .qa-round-old .qa-question {
            font-size: 0.82rem; color: #6b7280; margin-bottom: 0.3rem;
        }
        .qa-round-old .qa-answer {
            font-size: 0.88rem; color: #374151;
        }

        /* Aktuelle Runde hervorheben */
        .qa-round-current {
            margin-bottom: 1rem;
            padding: 1rem 1.2rem;
            border-radius: 12px;
            background: #f8faff;
            border: 1px solid #dbeafe;
            box-shadow: 0 2px 8px rgba(59,130,246,0.07);
        }
        .qa-round-current .qa-question {
            font-size: 0.85rem; font-weight: 600; color: #1d4ed8; margin-bottom: 0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)

    # Layout: schmale linke Spalte für Beispielfragen, breite rechte Spalte für Chat
    col_examples, col_chat = st.columns([1, 2.8])

    with col_examples:
        st.markdown('<div class="filter-label" style="margin-top:0">BEISPIEL-FRAGEN</div>', unsafe_allow_html=True)
        # Jeder Button schreibt die bereinigte Frage in den Session State,
        # damit sie beim nächsten Rerender als Eingabe vorausgefüllt wird
        for bfrage in BEISPIEL_FRAGEN:
            if st.button(bfrage, key=f"btn_{bfrage}"):
                st.session_state["beispiel_frage"] = bfrage.replace(" ↗", "")

    with col_chat:
        # Titelzeile mit App-Name und Status-Badge
        st.markdown("""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
            <div style="display:flex;align-items:center;gap:0.6rem">
                <span class="app-focus-title" style="color:#0f172a;">GSA Chat-Analyse</span>
                <span style="background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;
                             padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600">
                    Multi-Agent aktiv
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Gesprächsverlauf im Session State initialisieren falls noch nicht vorhanden
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Steuerleiste: Gespräch zurücksetzen + Info zur Verlässlichkeit
        col_reset, col_info = st.columns([1, 1])
        with col_reset:
            if st.button("Gespräch zurücksetzen", key="reset"):
                st.session_state.messages = []
                st.rerun()
        with col_info:
            with st.expander("Was bedeutet die Verlässlichkeit?"):
                st.markdown("""
**Verlässlichkeit** zeigt, wie gut die Antwort durch echte Daten belegt ist.

| Score | Bedeutung |
|-------|-----------|
| **Hoch** ≥ 80 % | Antwort stimmt mit Datenbank- oder Wikipedia-Daten überein |
| **Mittel** 60–79 % | Teilweise belegt, aber nicht vollständig prüfbar |
| **Niedrig** < 60 % | Keine Quelldaten verfügbar oder Abweichungen gefunden — mit Vorsicht lesen |

*Niedrige Verlässlichkeit heißt nicht automatisch falsch — nur dass keine Daten zur Verifikation vorhanden waren.*
                """)


        def render_meta(steps: list, confidence: float, sql: str, sql_result: str) -> None:
            """Zeigt Agent-Badges, Confidence-Ampel und optionalen SQL-Expander an.

            - steps: Liste der durchlaufenen Agenten-Keys (z.B. ['openligadb', 'validator'])
            - confidence: Float 0.0–1.0, bestimmt Farbe der Ampel
            - sql: generiertes SQL-Statement (leer = nicht anzeigen)
            - sql_result: JSON-String der Datenbankrohdaten (leer oder '[]' = nicht anzeigen)
            """
            # Agent-Badges als HTML zusammenbauen
            badges = ""
            for step in steps:
                label = AGENT_LABELS.get(step, step)
                bg = AGENT_COLORS.get(step, "#f3f4f6")
                border = AGENT_BORDER.get(step, "#9ca3af")
                badges += f'<span class="agent-badge" style="background:{bg};border:1px solid {border};color:#374151">{label}</span>'

            # Confidence-Ampel: grün ≥ 80%, gelb 60–79%, rot < 60%
            if confidence >= 0.8:
                conf_html = f'<span class="conf-high">● Hohe Verlässlichkeit {confidence:.0%}</span>'
            elif confidence >= 0.6:
                conf_html = f'<span class="conf-mid">● Mittlere Verlässlichkeit {confidence:.0%}</span>'
            else:
                conf_html = f'<span class="conf-low">● Niedrige Verlässlichkeit {confidence:.0%}</span>'
            st.markdown(f"{badges}&nbsp;&nbsp;{conf_html}", unsafe_allow_html=True)

            # SQL und Rohdaten nur anzeigen wenn vorhanden und nicht leer
            if sql or sql_result:
                with st.expander("Quellen & SQL anzeigen"):
                    if sql:
                        st.markdown("**Generiertes SQL:**")
                        st.code(sql, language="sql")
                    if sql_result and sql_result != "[]":
                        st.markdown("**Rohdaten aus der Datenbank:**")
                        # Rohdaten auf 2000 Zeichen begrenzen um die UI nicht zu überfluten
                        st.code(sql_result[:2000], language="json")

        # ── Gesprächsverlauf als Q&A-Runden rendern ──────────────────────────
        # Nachrichten werden paarweise (User + Assistent) zu Runden zusammengefasst
        messages = st.session_state.messages
        rounds = []
        i = 0
        while i < len(messages):
            if messages[i]["role"] == "user":
                user_msg = messages[i]
                # Assistent-Nachricht nur aufnehmen wenn sie direkt folgt
                assistant_msg = messages[i + 1] if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant" else None
                rounds.append((user_msg, assistant_msg))
                i += 2 if assistant_msg else 1
            else:
                i += 1

        for idx, (user_msg, assistant_msg) in enumerate(rounds):
            is_last = idx == len(rounds) - 1
            # Letzte Runde wird hervorgehoben, ältere Runden werden gedimmt
            css_class = "qa-round-current" if is_last else "qa-round-old"

            # Frage als HTML-Block rendern (Pfeil-Symbol ▶ als visueller Marker)
            st.markdown(f'<div class="{css_class}"><div class="qa-question">&#9656; {user_msg["content"]}</div></div>', unsafe_allow_html=True)

            if assistant_msg:
                if is_last:
                    # Aktuelle Antwort vollständig mit Metadaten anzeigen
                    st.markdown(assistant_msg["content"])
                    meta = assistant_msg.get("meta", {})
                    render_meta(meta.get("steps", []), meta.get("confidence", 0.0), meta.get("sql", ""), meta.get("sql_result", ""))
                else:
                    # Ältere Antworten auf 300 Zeichen kürzen um Platz zu sparen
                    st.markdown(f'<div class="qa-round-old"><div class="qa-answer">{assistant_msg["content"][:300]}{"…" if len(assistant_msg["content"]) > 300 else ""}</div></div>', unsafe_allow_html=True)

        # ── Neue Eingabe verarbeiten ──────────────────────────────────────────
        # Beispielfrage aus Session State holen (wurde durch Button-Klick gesetzt)
        prefill = st.session_state.pop("beispiel_frage", None)
        frage = st.chat_input("Frage auf Deutsch stellen, z.B. Wie steht die Bundesliga?")
        # Button-Klick hat Vorrang nur wenn kein Text direkt im Eingabefeld steht
        if prefill and not frage:
            frage = prefill

        if frage:
            # Nutzerfrage sofort in den Verlauf schreiben
            st.session_state.messages.append({"role": "user", "content": frage})

            with st.spinner(""):
                # Platzhalter für die Live-Fortschrittsanzeige
                progress_placeholder = st.empty()

                def show_progress(completed_steps: list, active: str) -> None:
                    """Aktualisiert die Step-Liste: erledigte Steps grün, aktiver Step blau."""
                    html = ""
                    for key, label in AGENT_STEPS:
                        if key in completed_steps:
                            html += f'<div class="progress-step done">&#10003; {label}</div>'
                        elif key == active:
                            html += f'<div class="progress-step active">&#9679; {label}...</div>'
                    progress_placeholder.markdown(html, unsafe_allow_html=True)

                # Fortschrittsanzeige mit Supervisor als erstem aktivem Schritt starten
                show_progress([], "supervisor")
                result = None
                completed = []

                # Kontext aus bisherigem Verlauf aufbauen (ohne die gerade gestellte Frage)
                history = _build_history_string(st.session_state.messages[:-1])

                # Graph streamen: jedes Chunk enthält den Node-Namen und den aktuellen State
                for chunk in graph.stream({**EMPTY_STATE, "question": frage, "chat_history": history}):
                    node = list(chunk.keys())[0]
                    state = chunk[node]

                    # Jeden Node nur einmal in die erledigten Steps aufnehmen
                    if node not in completed:
                        completed.append(node)

                    # Nächsten anzuzeigenden Step anhand der fixen Reihenfolge ermitteln.
                    # Supervisor kann mehrfach aufgerufen werden (iterativer Loop),
                    # next_idx zeigt immer den nächsten Step in der fixen Anzeigereihenfolge.
                    node_order = [k for k, _ in AGENT_STEPS]
                    next_idx = node_order.index(node) + 1 if node in node_order else -1
                    next_node = node_order[next_idx] if next_idx < len(node_order) else ""
                    show_progress(completed, next_node)

                    # Letzten bekannten State merken — enthält am Ende die finale Antwort
                    result = state

                # Fortschrittsanzeige nach Abschluss entfernen
                progress_placeholder.empty()

            # Antwort Wort für Wort mit Tipp-Effekt einblenden
            answer = result.get("answer", "Keine Antwort erhalten.")
            answer_placeholder = st.empty()
            displayed = ""
            for word in answer.split(" "):
                displayed += word + " "
                # Cursor-Symbol ▌ am Ende simuliert aktives Tippen
                answer_placeholder.markdown(displayed + "▌")
                time.sleep(0.03)
            # Finalen Text ohne Cursor rendern
            answer_placeholder.markdown(answer)

            # Badges und Confidence direkt unterhalb der Antwort anzeigen
            render_meta(
                result.get("steps", []),
                result.get("confidence", 0.0),
                result.get("sql", ""),
                result.get("sql_result", ""),
            )

            # Assistent-Nachricht mit Metadaten im Session State speichern,
            # damit render_meta beim nächsten Rerender die Daten wieder hat
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

            # Seite neu laden damit der Gesprächsverlauf korrekt neu gerendert wird
            st.rerun()
