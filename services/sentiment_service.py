"""
Titel: Wikipedia Sentiment-Analyse Service
Beschreibung: Dieses Modul lädt historische Wikipedia-Artikel von Fußballvereinen,
              zerlegt die Texte auf Satzebene und berechnet mithilfe des VADER-
              SentimentIntensityAnalyzers eine durchschnittliche Tonalität (Score) pro Verein.
              Die Ergebnisse werden farbcodiert in einem Pandas DataFrame ausgegeben.
Autorin: Annette Kufner
"""

import json
import pandas as pd
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import unicodedata
import re


_SENTIMENT_TEAM_ALIASES = {
    "fc bayern munchen": "fc bayern munich",
    "bayern munchen": "fc bayern munich",
    "bayern muenchen": "fc bayern munich",
    "1 fc heidenheim 1846": "1 fc heidenheim",
    "mainz 05": "1 fsv mainz 05",
    "fsv mainz 05": "1 fsv mainz 05",
    "real madrid": "real madrid cf",
    "paris saint germain": "paris saint germain fc",
    "psg": "paris saint germain fc",
}


def _normalize_team_name_for_sentiment(team_name: str) -> str:
    normalized = unicodedata.normalize("NFKD", team_name or "")
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    normalized = normalized.replace("&", " und ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\b(cf|fc|sc|sv|ac|as|ssc|vfl|tsg|rb|bv|e v)\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return _SENTIMENT_TEAM_ALIASES.get(normalized, normalized)


def sentiment_label_from_score(avg_score: float) -> str:
    if avg_score >= 0.45:
        return "🟢 Sehr Positiv"
    if avg_score >= 0.35:
        return "🟠 Positiv"
    return "🟡 Etwas durchwachsen"


def get_wikipedia_sentiment_dataframe(file_path="data/wikipedia_articles.json"):
    """
    Liest die Wikipedia-Artikel ein, analysiert die Stimmung (Sentiment) Satz für Satz
    und gibt ein nach Tonalität sortiertes Pandas DataFrame zurück.
    
    Parameter:
        file_path (str): Relativer Pfad zur JSON-Datei mit den Artikeln.
        
    Rückgabewert:
        pd.DataFrame: Bereinigte und sortierte Tabelle für das Streamlit-Frontend.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except FileNotFoundError:
        # Fallback für geänderte Ordnerstrukturen im Live-Betrieb
        return pd.DataFrame()
        
    try:
        sia = SentimentIntensityAnalyzer()
    except LookupError:
        # Streamlit Cloud images may miss NLTK resources on first boot.
        try:
            nltk.download("vader_lexicon", quiet=True)
            sia = SentimentIntensityAnalyzer()
        except Exception:
            return pd.DataFrame()

    data = []
    
    for article in articles:
        verein = article.get("wikipedia_title")
        text = article.get("text_en", "")
        
        if text:
            # Sätze trennen per nativem Python-Split (sicher vor NLTK-Download-Fehlern)
            saetze = text.split(". ")
            
            # Score für jeden einzelnen Satz berechnen
            satz_scores = [sia.polarity_scores(s)['compound'] for s in saetze if s.strip()]
            
            if satz_scores:
                # Mathematischen Durchschnitt berechnen
                avg_score = sum(satz_scores) / len(satz_scores)
                stimmung = sentiment_label_from_score(avg_score)
                    
                data.append({
                    "Verein": verein,
                    "Ø Sentiment-Score": round(avg_score, 4),
                    "Grundstimmung": stimmung
                })
            
    # DataFrame erstellen und nach den positivsten Scores absteigend sortieren
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by="Ø Sentiment-Score", ascending=False)
    return df


def get_team_sentiment(team_name: str, file_path="data/wikipedia_articles.json") -> dict | None:
    """Liefert den Sentiment-Wert und die textuelle Einstufung für ein Team."""
    if not team_name or team_name == "Alle Teams":
        return None

    df = get_wikipedia_sentiment_dataframe(file_path=file_path)
    if df.empty:
        return None

    normalized_target = _normalize_team_name_for_sentiment(team_name)
    matches = df[df["Verein"].astype(str).map(_normalize_team_name_for_sentiment) == normalized_target]
    if matches.empty:
        return None

    row = matches.iloc[0]
    score = float(row["Ø Sentiment-Score"])
    return {
        "team": str(row["Verein"]),
        "score": round(score, 4),
        "label": sentiment_label_from_score(score),
    }