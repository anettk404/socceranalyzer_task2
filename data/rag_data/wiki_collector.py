"""
GenSoccerAnalyzer – Schritt 1: Wikipedia-Daten sammeln & ins Deutsche übersetzen
=================================================================================
Dieses Skript holt Wikipedia-Artikel für alle Teams der 5 europäischen Top-Ligen
auf Englisch und übersetzt sie ins Deutsche (via deep-translator / DeepL-Free).
Ergebnis: data/wikipedia_articles.json  – bereit für Chunking & Pinecone-Upload.

Voraussetzungen (einmalig installieren):
    pip install requests deep-translator tqdm
"""

import json
import time
import os
from pathlib import Path
import requests
from tqdm import tqdm
from deep_translator import GoogleTranslator   # kostenlos, kein API-Key nötig
                                               # Alternative: DeepLTranslator (500k Zeichen/Monat gratis)

# ─────────────────────────────────────────────
# 1. TEAM-LISTE PRO LIGA
#    Wikipedia-Seitentitel auf Englisch verwenden!
# ─────────────────────────────────────────────
TEAMS = {
    "Bundesliga": [
        "FC Bayern Munich", "Borussia Dortmund", "Bayer 04 Leverkusen",
        "RB Leipzig", "Borussia Mönchengladbach", "Eintracht Frankfurt",
        "VfB Stuttgart", "SC Freiburg", "1. FC Union Berlin",
        "TSG 1899 Hoffenheim", "SV Werder Bremen", "VfL Wolfsburg",
        "FC Augsburg", "1. FSV Mainz 05", "VfL Bochum",
        "1. FC Heidenheim", "FC St. Pauli", "Holstein Kiel",
    ],
    "Premier League": [
        "Arsenal F.C.", "Aston Villa F.C.", "Brentford F.C.",
        "Brighton & Hove Albion F.C.", "Chelsea F.C.", "Crystal Palace F.C.",
        "Everton F.C.", "Fulham F.C.", "Ipswich Town F.C.", "Leicester City F.C.",
        "Liverpool F.C.", "Luton Town F.C.", "Manchester City F.C.",
        "Manchester United F.C.", "Newcastle United F.C.", "Nottingham Forest F.C.",
        "Sheffield United F.C.", "Tottenham Hotspur F.C.", "West Ham United F.C.",
        "Wolverhampton Wanderers F.C.",
    ],
    "La Liga": [
        "FC Barcelona", "Real Madrid CF", "Atlético Madrid", "Sevilla FC",
        "Real Betis", "Real Sociedad", "Villarreal CF", "Athletic Bilbao",
        "Valencia CF", "RC Celta de Vigo", "Getafe CF", "Rayo Vallecano",
        "CA Osasuna", "Girona FC", "Almería", "Cádiz CF",
        "Deportivo Alavés", "Granada CF", "Las Palmas", "Mallorca",
    ],
    "Serie A": [
        "AC Milan", "Inter Milan", "Juventus FC", "AS Roma",
        "SS Lazio", "Atalanta BC", "ACF Fiorentina", "SSC Napoli",
        "Torino FC", "Bologna FC 1909", "Hellas Verona FC", "US Sassuolo Calcio",
        "Udinese Calcio", "US Salernitana 1919", "Genoa CFC", "Empoli FC",
        "Frosinone Calcio", "Cagliari Calcio", "US Lecce", "Monza",
    ],
    "Ligue 1": [
        "Paris Saint-Germain FC", "AS Monaco FC", "Olympique de Marseille",
        "Olympique Lyonnais", "Stade Rennais FC", "RC Lens",
        "Lille OSC", "OGC Nice", "Montpellier HSC", "Stade de Reims",
        "FC Nantes", "Toulouse FC", "RC Strasbourg Alsace", "Stade Brestois 29",
        "Le Havre AC", "FC Metz", "Clermont Foot 63", "FC Lorient",
    ],
}


# ─────────────────────────────────────────────
# 2. WIKIPEDIA-ARTIKEL HOLEN
# ─────────────────────────────────────────────
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "GenSoccerAnalyzer (Educational Project, Hochschule der Medien)"}


def fetch_wikipedia_article(title: str, retries: int = 3) -> dict | None:
    """
    Holt den vollständigen Text eines Wikipedia-Artikels.
    Gibt dict mit 'wikipedia_title' und 'text_en' zurück, oder None bei Fehler.
    Retry-Logik mit exponentiellem Backoff bei 429 Too Many Requests.
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        #"redirects": True,   # automatische Weiterleitungen folgen
    }

    for attempt in range(retries):
        try:
            response = requests.get(WIKIPEDIA_API, params=params, headers=HEADERS, timeout=10)

            # if response.status_code == 429:
            #     wait = 5 * (attempt + 1)  # 5s → 10s → 15s
            #     print(f"  ⏳ Rate limit – warte {wait}s (Versuch {attempt + 1}/{retries})...")
            #     time.sleep(wait)
            #     continue

            response.raise_for_status()
            data = response.json()

            pages = data["query"]["pages"]
            page = next(iter(pages.values()))

            if "missing" in page:
                print(f"  ⚠️  Seite nicht gefunden: '{title}'")
                return None

            text = page.get("extract", "").strip()
            if not text:
                print(f"  ⚠️  Kein Text für: '{title}'")
                return None

            return {"wikipedia_title": page["title"], "text_en": text}

        except Exception as e:
            print(f"  ❌ Fehler bei '{title}' (Versuch {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(5)

    return None


# ─────────────────────────────────────────────
# 3. TEXT INS DEUTSCHE ÜBERSETZEN
# ─────────────────────────────────────────────
def translate_to_german(text: str, chunk_size: int = 4500) -> str:
    """
    GoogleTranslator hat ein Limit von ~5000 Zeichen pro Aufruf.
    Wir teilen lange Texte in Blöcke auf und fügen sie wieder zusammen.
    """
    translator = GoogleTranslator(source="en", target="de")

    # Text in Absätze aufteilen und Blöcke zusammenbauen
    paragraphs = text.split("\n")
    blocks = []
    current_block = ""

    for para in paragraphs:
        if len(current_block) + len(para) + 1 < chunk_size:
            current_block += para + "\n"
        else:
            if current_block.strip():
                blocks.append(current_block.strip())
            current_block = para + "\n"

    if current_block.strip():
        blocks.append(current_block.strip())

    # Jeden Block übersetzen
    translated_blocks = []
    for block in blocks:
        try:
            translated = translator.translate(block)
            translated_blocks.append(translated)
            time.sleep(0.3)   # kurze Pause, um Rate Limits zu vermeiden
        except Exception as e:
            print(f"    ⚠️  Übersetzungsfehler (Block übersprungen): {e}")
            translated_blocks.append(block)  # Fallback: Original behalten

    return "\n".join(translated_blocks)


# ─────────────────────────────────────────────
# 4. HAUPTPROGRAMM
# ─────────────────────────────────────────────
def collect_all_articles(output_path: str = "data/wikipedia_articles.json",
                          translate: bool = True) -> list[dict]:
    """
    Iteriert über alle Ligen & Teams, holt Wikipedia-Artikel,
    übersetzt sie optional ins Deutsche und speichert alles als JSON.
    """
    Path("data").mkdir(exist_ok=True)

    # Falls bereits eine Datei existiert: weitermachen statt neu anfangen
    if Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
        already_done = {a["wikipedia_title"] for a in articles}
        print(f"📂 Bereits {len(articles)} Artikel vorhanden – wird fortgesetzt.\n")
    else:
        articles = []
        already_done = set()

    total_teams = sum(len(teams) for teams in TEAMS.values())

    with tqdm(total=total_teams, desc="Teams gesamt") as pbar:
        for liga, teams in TEAMS.items():
            print(f"\n🏟️  Liga: {liga}")
            for team in teams:
                pbar.set_postfix({"team": team[:30]})

                # VORHER prüfen, nicht nachher
                if team in already_done or any(a["team"] == team for a in articles):
                    print(f"  ⏭️  Bereits vorhanden: {team}")
                    pbar.update(1)
                    continue

                # Wikipedia-Artikel holen
                article = fetch_wikipedia_article(team)

                if article is None:
                    pbar.update(1)
                    continue

                # Ins Deutsche übersetzen
                if translate:
                    print(f"  🔄 Übersetze: {team} ({len(article['text_en'])} Zeichen)...")
                    article["text_de"] = translate_to_german(article["text_en"])
                else:
                    article["text_de"] = article["text_en"]   # für Tests ohne Übersetzung

                # Metadaten hinzufügen
                article["liga"] = liga
                article["team"] = team
                article["source"] = "wikipedia"
                article["language"] = "de"

                articles.append(article)
                already_done.add(article["wikipedia_title"])

                # Nach jedem Team zwischenspeichern (Absicherung gegen Abbrüche)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(articles, f, ensure_ascii=False, indent=2)

                time.sleep(1)   # höfliche Pause zwischen Wikipedia-Anfragen
                pbar.update(1)

    print(f"\n✅ Fertig! {len(articles)} Artikel in '{output_path}' gespeichert.")
    return articles


# ─────────────────────────────────────────────
# 5. START
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Für einen schnellen Test: translate=False setzen
    # Für die finale Version: translate=True (dauert ~30-60 Min für alle Teams)
    articles = collect_all_articles(
        output_path="data/wikipedia_articles.json",
        translate=True
    )

    # Kurze Übersicht
    print("\n📊 Übersicht:")
    from collections import Counter
    liga_count = Counter(a["liga"] for a in articles)
    for liga, count in liga_count.items():
        print(f"  {liga}: {count} Teams")