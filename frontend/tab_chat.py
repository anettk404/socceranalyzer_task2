# -----------------------------------------------
# tab_chat.py
# -----------------------------------------------

import streamlit as st


def render_chat_tab():

    st.caption("Chat-Analyse mit GenSoccerAnalyzer")

    st.markdown("### Frage den GenSoccerAnalyzer")

    frage = st.text_area(
        "Deine Frage",
        placeholder="Warum war Bayer Leverkusen 2023/24 so erfolgreich?"
    )

    if st.button("Analyse starten", use_container_width=True):

        if not frage.strip():
            st.warning("Bitte eine Frage eingeben.")
            return

        # Platzhalter für spätere LLM-Antwort
        with st.spinner("Analysiere Datenquellen..."):

            antwort = """
            Dies ist aktuell ein Platzhalter.

            Später werden hier Antworten aus:
            - OpenLigaDB
            - Wikipedia
            - StatsBomb

            generiert.
            """

            st.success("Analyse abgeschlossen")
            st.markdown(antwort)

    st.markdown("---")

    st.subheader("Beispiel-Fragen")

    st.markdown("""
    - Warum hat Leverkusen die Saison dominiert?
    - Welche Teams spielen ähnlich wie Bayern?
    - Welche Cluster zeigen ähnliche Vereinsidentitäten?
    - Wie effizient war Dortmund im Torabschluss?
    - Welche Begriffe prägen Union Berlin?
    """)