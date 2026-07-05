# -----------------------------------------------
# tab_clustering.py
# -----------------------------------------------

import sys
import os
import streamlit as st
import plotly.express as px
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from Clustering.clustering import load_articles, run_clustering, get_top_terms_per_cluster, label_clusters



CLUSTER_COLORS = ["#2ecc71", "#3b82f6", "#f39c12", "#9b59b6", "#e74c3c"]
CLUSTER_EMOJIS = ["🟢", "🔵", "🟠", "🟣", "🔴"]


@st.cache_data(show_spinner=False)
def lade_verfuegbare_ligen() -> list[str]:
    articles = load_articles()
    return sorted(set(a["liga"] for a in articles if a.get("liga")))


@st.cache_data(show_spinner=False)
def lade_clustering_daten(k_wert: int, liga: str | None = None) -> tuple[pd.DataFrame, dict]:
    articles = load_articles()
    ligen_filter = [liga] if liga else None
    df_raw, X, vectorizer = run_clustering(articles, n_clusters=k_wert, ligen=ligen_filter)
    top_terms = get_top_terms_per_cluster(X, df_raw["cluster"].values, vectorizer)

    try:
        cluster_labels = label_clusters(top_terms)
    except Exception:
        cluster_labels = {cid: f"Cluster {cid}" for cid in top_terms}

    df_raw["cluster_label"] = df_raw["cluster"].map(cluster_labels)

    insights = {
        cid: {
            "label": cluster_labels.get(cid, f"Cluster {cid}"),
            "vereine": df_raw[df_raw["cluster"] == cid]["team"].tolist(),
            "begriffe": top_terms.get(cid, [])[:6],
        }
        for cid in sorted(top_terms.keys())
    }

    return df_raw, insights


def render_clustering_tab():
    st.markdown("""
    <style>
        .cluster-badge {
            display: inline-block; padding: 2px 10px; border-radius: 12px;
            font-size: 0.78rem; font-weight: 600; margin: 2px 3px 0 0;
        }
        .cluster-header {
            display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem;
        }
        .cluster-title { font-weight: 700; font-size: 1rem; }
        .cluster-subtitle {
            background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0;
            padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600;
        }
        .cluster-card {
            background: white; border: 1px solid #e5e7eb; border-radius: 10px;
            padding: 0.9rem 1rem; margin-bottom: 0.6rem;
        }
        .cluster-card-label { font-weight: 700; font-size: 0.9rem; color: #6b7280; margin-bottom: 0.3rem; }
        .cluster-card-teams { font-size: 0.78rem; color: #6b7280; margin-bottom: 0.4rem; }
        .term-pill {
            display: inline-block; background: #f3f4f6; color: #374151;
            border-radius: 8px; padding: 1px 8px; font-size: 0.72rem;
            margin: 2px 2px 0 0; border: 1px solid #e5e7eb;
        }
        .filter-label {
            font-size: 0.72rem; font-weight: 600; color: #6b7280;
            letter-spacing: 0.05em; margin-bottom: 4px; margin-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

    col_sidebar, col_main = st.columns([1, 2.8])

    with col_sidebar:
        ligen = lade_verfuegbare_ligen()
        st.markdown('<div class="filter-label">LIGA</div>', unsafe_allow_html=True)
        liga_auswahl = st.selectbox(
            "Liga",
            options=["Alle"] + ligen,
            index=0,
            label_visibility="collapsed",
            key="cluster_liga",
        )
        gewaehlte_liga = None if liga_auswahl == "Alle" else liga_auswahl

        st.markdown('<div class="filter-label">CLUSTER-ANZAHL</div>', unsafe_allow_html=True)
        k_wert = st.slider("Cluster-Anzahl (k)", min_value=2, max_value=5, value=3,
                           label_visibility="collapsed", key="cluster_k")

    with col_main:
        st.markdown("""
        <div class="cluster-header">
            <span class="cluster-title">Vereins-Clustering</span>
            <span class="cluster-subtitle">TF-IDF + KMeans + LLM-Labels</span>
            <span class="cluster-subtitle">Wikipedia</span>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Berechne Clustering..."):
            try:
                df, insights = lade_clustering_daten(k_wert, gewaehlte_liga)
            except Exception as e:
                st.error(f"Fehler beim Laden der Daten: {e}")
                return

        df["Farbe"] = df["cluster"].map(lambda c: CLUSTER_COLORS[c % len(CLUSTER_COLORS)])
        df["Label"] = df["cluster"].map(lambda c: insights.get(c, {}).get("label", f"Cluster {c}"))
        color_map = {
            row["Label"]: CLUSTER_COLORS[row["cluster"] % len(CLUSTER_COLORS)]
            for _, row in df.drop_duplicates("cluster").iterrows()
        }
        label_order = [
            df[df["cluster"] == cid]["Label"].iloc[0]
            for cid in sorted(insights.keys())
            if len(df[df["cluster"] == cid]) > 0
        ]
        col_plot, col_cards = st.columns([1.6, 1])

        with col_plot:
            fig = px.scatter(
                df,
                x="x", y="y",
                color="Label",
                hover_name="team",
                hover_data={"liga": True, "x": False, "y": False, "Label": False},
                color_discrete_map=color_map,
                category_orders={"Label": label_order},
                height=480,
            )
            fig.update_traces(
                marker=dict(size=11, line=dict(width=1.5, color="#ffffff")),
                selector=dict(mode="markers"),
            )
            fig.update_layout(
                plot_bgcolor="#f9fafb",
                paper_bgcolor="#f9fafb",
                xaxis=dict(showticklabels=False, showgrid=False, zeroline=False, title=""),
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, title=""),
                legend=dict(
                    title=dict(text="    Cluster", font=dict(color="#6b7280", size=11)),
                    orientation="v",
                    yanchor="top", y=-0.05,
                    xanchor="left", x=0,
                    font=dict(size=11, color="#374151"),
                    bgcolor="rgba(255,255,255,0.95)",
                    bordercolor="#d1d5db",
                    borderwidth=1,
                ),
                margin=dict(l=10, r=10, t=10, b=130),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_cards:
            for cid in sorted(insights.keys()):
                info = insights[cid]
                color = CLUSTER_COLORS[cid % len(CLUSTER_COLORS)]
                emoji = CLUSTER_EMOJIS[cid % len(CLUSTER_EMOJIS)]
                teams_str = ", ".join(info["vereine"][:4])
                if len(info["vereine"]) > 4:
                    teams_str += f" +{len(info['vereine']) - 4}"
                begriffe_html = "".join(
                    f'<span class="term-pill">{b}</span>' for b in info["begriffe"]
                )
                st.markdown(f"""
                <div class="cluster-card" style="border-left: 4px solid {color};">
                    <div class="cluster-card-label">{emoji} {info['label']}</div>
                    <div class="cluster-card-teams">{teams_str}</div>
                    <div>{begriffe_html}</div>
                </div>
                """, unsafe_allow_html=True)
