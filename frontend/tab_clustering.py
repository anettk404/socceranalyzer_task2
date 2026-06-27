# -----------------------------------------------
# tab_clustering.py – Clustering-Tab (Design & Test)
# -----------------------------------------------

import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Versuche den echten Service zu laden. Wenn er fehlt, nutzen wir Mock-Daten für den Design-Test.
try:
    from pipeline.analytics_service import load_and_calculate_clustering
    ECHTE_PIPELINE_VORHANDEN = True
except ModuleNotFoundError:
    ECHTE_PIPELINE_VORHANDEN = False


def generiere_mock_daten(k_wert):
    """Erzeugt realistische Testdaten für das Layout-Testing."""
    vereine = [
        "FC Bayern München", "Borussia Dortmund", "Bayer 04 Leverkusen",
        "RB Leipzig", "Eintracht Frankfurt", "VfB Stuttgart",
        "SC Freiburg", "1. FC Union Berlin", "Borussia Mönchengladbach",
        "Werder Bremen", "TSG 1899 Hoffenheim", "FC Augsburg"
    ]


# ------------------------------------------------------------------------
# Schaubild für t-SNE erzeugen
# ------------------------------------------------------------------------
    
    # Koordinatensystem: Zufällige, aber feste X/Y Koordinaten für das Diagramm erzeugen
    np.random.seed(42)
    x_koordinaten = np.random.randn(len(vereine)) * 5
    y_koordinaten = np.random.randn(len(vereine)) * 5
    # Vereine gleichmäßig auf Cluster aufteilen
    cluster_zuordnung = [i % k_wert for i in range(len(vereine))]
    
    df = pd.DataFrame({
        "Verein": vereine,
        "x": x_koordinaten,
        "y": y_koordinaten,
        "Zugeordnetes Cluster": cluster_zuordnung
    })
    
    # Beispielbegriffe für das Topic Modeling
    beispiel_begriffe = ["saison", "meister", "gewinnen", "bundesliga", "trainer", "stadion", "dfb-pokal", "tor"] # Echte Daten anbi
    
    insights = {}
    for i in range(k_wert):
        insights[i] = {
            "label": f"Tradition & Erfolgsgruppe {i+1}",
            "vereine": [vereine[j] for j in range(len(vereine)) if cluster_zuordnung[j] == i],
            "begriffe": [beispiel_begriffe[(i+j) % len(beispiel_begriffe)] for j in range(4)]
        }
        
    return df, insights


def render_clustering_tab():

    st.caption("Clustering der Wikipedia-Daten")

    # Werte aus dem Haupt-Session-State abrufen
    pipeline_aktiv = st.session_state.get("pipeline_aktiv", False)
    generate_answer_func = st.session_state.get("generate_answer_func", None)

    # Schieberegler für k-Wert (2 bis 5)
    k_wert = st.slider("Anzahl der Cluster (k)", min_value=2, max_value=5, value=3)

    # CSS-Styling für den Schieberegler (Schiene + Punkt grün, Zahlen dunkel) und die Begriffe
    st.markdown("""
    <style>
        /* 1. Der bewegliche Punkt (Slider Handle) */
        div[data-testid="stSlider"] div[role="slider"] {
            background-color: #2d5a27 !important;
            border-color: #2d5a27 !important;
            box-shadow: none !important;
        }
        
        /* 2. NUR die aktive Schiene (Linie links vom Punkt) grün färben */
        div[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div:first-child {
            background-color: #2d5a27 !important;
        }
        
        /* Sicherheits-Fallback für die rote Schiene, falls Streamlit Inline-Styles nutzt */
        div[data-testid="stSlider"] [style*="background-color: rgb(255)"],
        div[data-testid="stSlider"] [style*="background: rgb(255)"] {
            background-color: #2d5a27 !important;
        }

        /* 3. EXPLIZIT die Zahlen (über und unter der Linie) wieder dunkel und lesbar machen */
        div[data-testid="stSlider"] [data-testid="stWidgetLabel"],             /* Text über dem Slider */
        div[data-testid="stSlider"] [data-baseweb="slider"] + div,             /* Aktueller Wert über dem Punkt */
        div[data-testid="stSlider"] [data-baseweb="slider"] ~ div div {        /* Skala/Nummerierung unter der Linie */
            color: #1a1a18 !important;
            -webkit-text-fill-color: #1a1a18 !important; /* Verhindert, dass Browser Farben überschreiben */
        }

        /* 4. Begriffe (Code-Tags) verkleinern, damit sie in eine Zeile passen */
        div[data-testid="stMarkdownContainer"] code {
            font-size: 11px !important;       
            padding: 2px 6px !important;      
            letter-spacing: -0.2px !important; 
            white-space: nowrap !important;   
        }
    </style>
    """, unsafe_allow_html=True)

    with st.spinner("Lade Wikipedia-Daten und berechne K-Means & t-SNE live im RAM..."):
        try:
            # Wenn die echte Datei existiert, nimm diese, ansonsten die Design-Testdaten
            if ECHTE_PIPELINE_VORHANDEN:
                ergebnis_df, cluster_insights = load_and_calculate_clustering(
                    k_wert=k_wert, 
                    pipeline_aktiv=pipeline_aktiv, 
                    generate_answer_func=generate_answer_func
                )
            else:
                # Automatischer Fallback für die Design-Vorschau
                ergebnis_df, cluster_insights = generiere_mock_daten(k_wert)

            # ─────────────────────────────────────────────────────────────
            # NEUES LAYOUT: Zwei Spalten nebeneinander
            # ─────────────────────────────────────────────────────────────
            col_graph, col_details = st.columns([6, 4])
            
            # --- LINKS: Schaubild für die Cluster (t-SNE) ---
            with col_graph:
                st.subheader("Cluster-Schaubild")
                
                diagramm_hoehe = 3 + (k_wert * 1.2)

                fig, ax = plt.subplots(
                figsize=(6, diagramm_hoehe),
                facecolor="#f7f7f5"
                )

                ax.set_facecolor('#f7f7f5')
                colors = ["#ff4b4b", "#0068c9", "#83c83f", "#fca000", "#7d44b7"]
                
                for cluster_idx in sorted(ergebnis_df["Zugeordnetes Cluster"].unique()):
                    cluster_data = ergebnis_df[ergebnis_df["Zugeordnetes Cluster"] == cluster_idx]
                    label_text = cluster_insights.get(cluster_idx, {}).get("label", f"Cluster {cluster_idx}")
                    
                    ax.scatter(
                        cluster_data["x"], cluster_data["y"], 
                        label=label_text, color=colors[cluster_idx % len(colors)], 
                        s=150, edgecolors="#222222", zorder=3
                    )
                    
                for i, team_name in enumerate(ergebnis_df["Verein"]):
                    ax.annotate(
                        team_name, (ergebnis_df["x"].iloc[i], ergebnis_df["y"].iloc[i]), 
                        xytext=(5, 5), textcoords="offset points", fontsize=9
                    )
                    
                ax.set_xticks([])
                ax.set_yticks([])
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                plt.legend(loc="upper left", bbox_to_anchor=(0, -0.05), frameon=False, fontsize=9)
                st.pyplot(
                    fig,
                    use_container_width=True
                )


                
               # --- RECHTS: Cluster-Details (Aufgeteilt in 5 Felder) ---
            with col_details:
                st.subheader("Cluster-Analysen")
                
                # Farb-Emojis passend zur Reihenfolge im Matplotlib-Schaubild
                cluster_emojis = ["🔴", "🔵", "🟢", "🟡", "🟣"]

                # Feste Höhe für alle Boxen
                box_hoehe = 110
                
                # Die 5 Felder für die Cluster-Insights (wird dynamisch befüllt)
                for i in range(k_wert):
                    with st.container(border=True):
                        # Wenn das Cluster laut Slider aktuell existiert, zeige die echten Daten an
                        if i in cluster_insights:
                            insights = cluster_insights[i]
                            emoji = cluster_emojis[i % len(cluster_emojis)]
                            
                            # 1) Titel mit der passenden Farbkugel statt dem Ordnersymbol
                            st.markdown(f"**{emoji} Cluster {i}: {insights['label']}**")
                            
                            # 2) Die Vereine darunter wurden weggelassen (Platz gespart)
                            # Zeige nur noch die Top-Wörter/Themenbegriffe
                            st.markdown(f"`{' · '.join(insights['begriffe'])}`")
                        else:
                            # Platzhalter für inaktive Felder
                            st.markdown(f"**🔒 Feld {i+3}: Cluster inaktiv**")
                            st.caption("Erhöhe die Cluster-Anzahl am Slider, um dieses Feld zu aktivieren.")

        except Exception as e:
            st.error(f"Fehler bei der Berechnung oder Darstellung: {e}")

                        
          