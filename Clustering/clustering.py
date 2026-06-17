"""
clustering.py
Klassisches NLP: TF-IDF Vektorisierung, KMeans Clustering und PCA-Reduktion
für die Visualisierung der Wikipedia-Vereinsartikel.
GenAI: LLM-basiertes Labeling der gefundenen Cluster.
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# === Daten laden ===

def load_articles(path: str | None = None) -> list[dict]:
    if path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(script_dir, "..", "data", "wikipedia_articles.json")
    with open(path) as f:
        return json.load(f)


# === Klassisches NLP: TF-IDF & Clustering ===

def run_clustering(
    data: list[dict],
    n_clusters: int = 5,
    ligen: list[str] | None = None
) -> tuple[pd.DataFrame, np.ndarray, TfidfVectorizer]:
    """
    Führt TF-IDF Vektorisierung, KMeans Clustering und PCA-Reduktion durch.

    Returns:
        df: DataFrame mit team, liga, cluster, x, y
        X: TF-IDF Matrix (sparse) - wird für get_top_terms_per_cluster benötigt
        vectorizer: gefitteter TfidfVectorizer - wird für Top-Terms benötigt
    """
    # Filter anwenden, falls Ligen ausgewählt wurden
    if ligen:
        data = [d for d in data if d["liga"] in ligen]

    texts = [d["text_en"] for d in data]
    teams = [d["team"] for d in data]
    ligen_col = [d["liga"] for d in data]

    # Absicherung: n_clusters darf nicht größer sein als Anzahl Dokumente
    n_clusters = min(n_clusters, len(data))

    vectorizer = TfidfVectorizer(
        max_features=500,
        stop_words="english",
        min_df=2,
        max_df=0.85
    )
    X = vectorizer.fit_transform(texts)

    labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X)
    coords = PCA(n_components=2).fit_transform(X.toarray())

    df = pd.DataFrame({
        "team": teams,
        "liga": ligen_col,
        "cluster": labels,
        "x": coords[:, 0],
        "y": coords[:, 1]
    })

    return df, X, vectorizer


def get_top_terms_per_cluster(
    X,
    labels: np.ndarray,
    vectorizer: TfidfVectorizer,
    n_terms: int = 10
) -> dict[int, list[str]]:
    """Extrahiert die wichtigsten TF-IDF-Begriffe pro Cluster."""
    feature_names = vectorizer.get_feature_names_out()
    top_terms = {}
    for cluster_id in sorted(set(labels)):
        idx = [i for i, l in enumerate(labels) if l == cluster_id]
        cluster_mean = np.asarray(X[idx].mean(axis=0)).flatten()
        top_idx = cluster_mean.argsort()[-n_terms:][::-1]
        top_terms[cluster_id] = [feature_names[i] for i in top_idx]
    return top_terms


# === GenAI: Cluster-Labeling via LLM ===

def label_clusters(top_terms: dict[int, list[str]]) -> dict[int, str]:
    """
    Lässt das LLM für alle Cluster gemeinsam unterscheidbare Labels generieren.
    Labels beschreiben das Textmuster der Artikel, nicht den aktuellen
    sportlichen Status (z.B. nicht "ist in der 2. Bundesliga").
    """
    clusters_text = "\n".join(
        f"Cluster {cid}: {', '.join(terms)}"
        for cid, terms in top_terms.items()
    )

    prompt = (
        f"Hier sind {len(top_terms)} Cluster von Fußballvereinen, jeweils "
        f"charakterisiert durch die häufigsten Begriffe in ihren Wikipedia-Artikeln:\n\n"
        f"{clusters_text}\n\n"
        f"Gib für jeden Cluster ein kurzes Label (max. 6 Wörter) auf Deutsch, das "
        f"das gemeinsame THEMA bzw. den TEXTSCHWERPUNKT dieser Artikel beschreibt "
        f"(z.B. 'Vereine mit Fokus auf Aufstiegsgeschichte').\n\n"
        f"WICHTIG:\n"
        f"- Beschreibe NIEMALS den aktuellen sportlichen Status oder die "
        f"aktuelle Liga eines Vereins als Fakt - die Begriffe spiegeln nur "
        f"wider, worüber die Artikel viel schreiben, nicht den heutigen Stand.\n"
        f"- Vermeide generische Begriffe wie 'Fußballverein', 'Bundesliga', "
        f"'Deutschland', die für alle Cluster zutreffen würden.\n"
        f"- Die Labels müssen sich klar voneinander unterscheiden.\n\n"
        f'Antworte NUR als JSON: {{"0": "Label", "1": "Label", ...}}'
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)
    return {int(k): v for k, v in result.items()}


# === Wrapper: alles in einem Aufruf ===

def get_clustered_data(
    n_clusters: int = 5,
    ligen: list[str] | None = None,
    with_llm_labels: bool = True,
    data: list[dict] | None = None
) -> pd.DataFrame:
    """
    Führt die komplette Clustering-Pipeline in einem Aufruf aus:
    Daten laden (falls nicht übergeben) -> TF-IDF -> KMeans -> PCA
    -> Top-Begriffe -> optional LLM-Labels.

    Wird von app.py aufgerufen, z.B.:
        df = get_clustered_data(n_clusters=5, ligen=["Bundesliga"])

    Args:
        n_clusters: gewünschte Anzahl Cluster
        ligen: Liste der Ligen zum Filtern, None = alle Ligen
        with_llm_labels: ob die GenAI-Labels generiert werden sollen
                          (False = schneller, kein API-Call, nur Cluster-Nummern)
        data: optional bereits geladene Artikel, sonst wird load_articles() genutzt

    Returns:
        DataFrame mit Spalten: team, liga, cluster, x, y
        und zusätzlich cluster_label, falls with_llm_labels=True
    """
    if data is None:
        data = load_articles()

    df, X, vectorizer = run_clustering(data, n_clusters=n_clusters, ligen=ligen)

    if with_llm_labels:
        top_terms = get_top_terms_per_cluster(X, df["cluster"].values, vectorizer)
        cluster_labels = label_clusters(top_terms)
        df["cluster_label"] = df["cluster"].map(cluster_labels)

    return df


if __name__ == "__main__":
    # Standalone-Test dieser Datei: python3 Clustering/clustering.py
    # Für die Streamlit-App reicht EIN Aufruf von get_clustered_data():
    #
    #   from clustering import get_clustered_data
    #   df = get_clustered_data(n_clusters=5, ligen=["Bundesliga"])
    #   -> df direkt an st.plotly_chart() / px.scatter() übergeben
    #      (Spalten: team, liga, cluster, cluster_label, x, y)

    df = get_clustered_data(n_clusters=5)

    print(df.head(10))
    print()
    print("Cluster-Größen:")
    print(df["cluster"].value_counts().sort_index())
    print()
    print(df[["cluster", "cluster_label"]].drop_duplicates().sort_values("cluster"))

    # Einfache Matplotlib-Visualisierung NUR für diesen Testlauf.
    # Die App selbst nutzt Plotly (siehe app.py), nicht diesen Block.
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 8))
    for label in df["cluster_label"].unique():
        subset = df[df["cluster_label"] == label]
        ax.scatter(subset["x"], subset["y"], label=label, s=60, alpha=0.7)

    for _, row in df.iterrows():
        ax.annotate(row["team"], (row["x"], row["y"]), fontsize=6, alpha=0.6)

    ax.set_title("Wikipedia-Clustering der Vereine (mit LLM-Labels)")
    ax.set_xlabel("PCA Komponente 1")
    ax.set_ylabel("PCA Komponente 2")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig("cluster_test.png", dpi=150)
    print()
    print("Plot gespeichert als cluster_test.png")