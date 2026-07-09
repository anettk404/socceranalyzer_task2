"""
GenSoccerAnalyzer – Schritt 1: Wikipedia-Daten sammeln & strukturieren

Autorin: Susanne Schmid
=======================================================================
Sammelt Wikipedia-Artikel für alle Teams der 5 europäischen Top-Ligen
sowie die Liga-Artikel selbst (Bundesliga, Premier League, etc.).

Pro Verein werden drei Datenquellen extrahiert:
  - Fließtext (text_en): vollständiger Artikeltext auf Englisch
  - Infobox: strukturierte Faktendaten (Gründung, Stadion, Trainer, etc.)
  - Tabellen: Kader ("Current squad") und Erfolge ("Honours")

Sprachstrategie: Artikel werden auf Englisch gespeichert (keine Übersetzung).
text-embedding-3-small matched deutsche Fragen zuverlässig auf englische
Chunks (Cross-Lingual Retrieval)

Infobox-Felder werden mit deutschen Synonymen angereichert
(z.B. "Head coach / Trainer / Cheftrainer") um das Cross-Lingual
Retrieval für häufige Faktenfragen zu verbessern.

Ergebnis:
  data/wikipedia_articles.json  ← Vereinsartikel (96 Teams, 5 Ligen)
  data/wikipedia_leagues.json   ← Liga-Artikel (5 Ligen)

Voraussetzungen:
    pip install requests tqdm beautifulsoup4
"""

import json
import time
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ─────────────────────────────────────────────
# 1. TEAM-LISTE PRO LIGA
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

# Liga-Artikel selbst (für allgemeine Infos: Modus, Auf-/Abstieg, Rekorde)
# Wikipedia-Seitentitel auf Englisch
LEAGUES = {
    "Bundesliga":     "Bundesliga",
    "Premier League": "Premier League",
    "La Liga":        "La Liga",
    "Serie A":        "Serie A",
    "Ligue 1":        "Ligue 1",
}

WIKIPEDIA_API  = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_REST = "https://en.wikipedia.org/api/rest_v1/page/html"
HEADERS = {"User-Agent": "GenSoccerAnalyzer (Educational Project, Hochschule der Medien)"}

# Sektionsnamen nach denen wir im HTML suchen (Groß-/Kleinschreibung egal)
SECTION_CURRENT_SQUAD = ["current squad", "first team", "first-team squad"]
SECTION_HONOURS       = ["honours", "honor", "achievements"]


# ─────────────────────────────────────────────
# 2. FLIESSTEXT HOLEN (wie bisher)
# ─────────────────────────────────────────────
def fetch_plaintext(title: str, retries: int = 5) -> dict | None:
    """Holt den Wikipedia-Artikel als Plain Text (ohne Tabellen/Infobox)."""
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
    }
    for attempt in range(retries):
        try:
            r = requests.get(WIKIPEDIA_API, params=params, headers=HEADERS, timeout=10)
            if r.status_code == 429:
                wait = 15 * (attempt + 1)  # 15s → 30s → 45s → 60s → 75s
                print(f"Rate limit Fließtext – warte {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data  = r.json()
            pages = data["query"]["pages"]
            page  = next(iter(pages.values()))
            if "missing" in page:
                print(f"Seite nicht gefunden: '{title}'")
                return None
            text = page.get("extract", "").strip()
            if not text:
                print(f"Kein Text für: '{title}'")
                return None
            return {"wikipedia_title": page["title"], "text_en": text}
        except Exception as e:
            print(f"Fehler Fließtext '{title}' (Versuch {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return None


# ─────────────────────────────────────────────
# 3. HTML HOLEN (für Infobox + Tabellen)
# ─────────────────────────────────────────────
def fetch_html(title: str, retries: int = 5) -> BeautifulSoup | None:
    """Holt den Wikipedia-Artikel als HTML und gibt ein BeautifulSoup-Objekt zurück."""
    url = f"{WIKIPEDIA_REST}/{requests.utils.quote(title)}"
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 429:
                wait = 15 * (attempt + 1)  # 15s → 30s → 45s → 60s → 75s
                print(f"Rate limit HTML – warte {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"Fehler HTML '{title}' (Versuch {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(8)
    return None


# ─────────────────────────────────────────────
# 4. INFOBOX EXTRAHIEREN
# ─────────────────────────────────────────────
def extract_infobox(soup: BeautifulSoup, team: str) -> dict:
    """
    Extrahiert Key-Value Paare aus der Wikipedia-Infobox.
    Gibt leeres dict zurück wenn keine Infobox gefunden.
    """
    infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
    if not infobox:
        return {}

    data = {}
    for row in infobox.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            key   = cells[0].get_text(separator=" ", strip=True)
            value = cells[1].get_text(separator=" ", strip=True)
            # Leere Keys / reine Zahlen / zu lange Keys überspringen
            if key and value and len(key) < 50 and not key.isdigit():
                # Referenz-Nummern entfernen (z.B. "[1]")
                value = re.sub(r"\[\d+\]", "", value).strip()
                data[key] = value

    return data


# Deutsche Synonyme für häufige Infobox-Felder, damit deutsche Fragen
# ("Wer ist der Trainer?") besser gegen englische Infobox-Werte matchen.
# Nur Felder die laut Häufigkeitsanalyse oft genug vorkommen, um sich zu lohnen.
INFOBOX_FIELD_SYNONYMS = {
    "Founded":                                "Founded / Gegründet",
    "Full name":                               "Full name / Vollständiger Name",
    "Capacity":                                "Capacity / Kapazität (Stadion)",
    "League":                                  "League / Liga",
    "Head coach":                              "Head coach / Trainer / Cheftrainer",
    "Manager":                                 "Manager / Trainer / Cheftrainer",
    "Nicknames":                               "Nicknames / Spitzname",
    "Nickname":                                "Nickname / Spitzname",
    "President":                               "President / Präsident",
    "Owner":                                   "Owner / Besitzer / Eigentümer",
    "Owners":                                  "Owners / Besitzer / Eigentümer",
    "Owner(s)":                                "Owner(s) / Besitzer / Eigentümer",
    "Ground":                                  "Ground / Stadion",
    "Stadium":                                 "Stadium / Stadion",
    "Short name":                              "Short name / Kurzname",
    "Chairman":                                "Chairman / Vorsitzender",
    "CEO":                                     "CEO / Geschäftsführer",
    "Home colours":                            "Home colours / Heimfarben",
}


def infobox_to_text(infobox: dict, team: str) -> str | None:
    """
    Serialisiert die Infobox als lesbaren RAG-Text.
    Häufige Feldnamen werden um deutsche Synonyme ergänzt, damit
    deutsche Fragen ("Wer ist der Trainer?") besser auf die englischen
    Infobox-Werte matchen (Cross-Lingual Retrieval, kein Übersetzungsschritt).
    """
    if not infobox:
        return None
    lines = [f"{team} – Steckbrief:"]
    for key, value in infobox.items():
        display_key = INFOBOX_FIELD_SYNONYMS.get(key, key)
        lines.append(f"  {display_key}: {value}")
    return "\n".join(lines)

def parse_html_table(table) -> list[dict]:
    """
    Parst eine HTML-Tabelle in eine Liste von Zeilen-Dicts.
    Erste Zeile wird als Header verwendet.
    """
    rows = table.find_all("tr")
    if not rows:
        return []

    # Header-Zeile finden (th-Tags)
    headers = []
    for row in rows:
        ths = row.find_all("th")
        if ths:
            headers = [th.get_text(separator=" ", strip=True) for th in ths]
            # Referenznummern entfernen
            headers = [re.sub(r"\[\d+\]", "", h).strip() for h in headers]
            break

    if not headers:
        return []

    # Datenzeilen parsen
    result = []
    for row in rows:
        tds = row.find_all("td")
        if not tds:
            continue
        values = [td.get_text(separator=" ", strip=True) for td in tds]
        values = [re.sub(r"\[\d+\]", "", v).strip() for v in values]

        # Zeile als Dict mit Header-Keys
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(values) and header:
                row_dict[header] = values[i]

        if row_dict:
            result.append(row_dict)

    return result


# ─────────────────────────────────────────────
# 5b. INHALT AUS SEKTION EXTRAHIEREN
#     Tabelle bevorzugt, Liste als Fallback
# ─────────────────────────────────────────────
def find_section_content(soup: BeautifulSoup, section_names: list[str]) -> list:
    """
    Findet den Inhalt einer Sektion – zuerst als Tabelle, dann als Listen-Fallback.
    Unterstützt:
    - <h2>/<h3> Überschriften (klassisches Wikipedia-HTML)
    - <div class="mw-heading"> Überschriften (neueres Wikipedia-HTML)
    - Verschachtelte <ul>/<li> Listen (z.B. Honours bei kleineren Vereinen)
    - <table> Tabellen (z.B. Honours bei großen Vereinen, Kader)
    """
    # Alle möglichen Überschriften-Elemente sammeln
    # Wikipedia nutzt sowohl <h2>/<h3> als auch <div class="mw-heading">
    all_headings = soup.find_all(
        lambda tag: tag.name in ["h2", "h3"] or
        (tag.name == "div" and tag.get("class") and
         any("mw-heading" in c for c in tag.get("class", [])))
    )

    for heading in all_headings:
        heading_text = heading.get_text(strip=True).lower()
        heading_text = re.sub(r"\[.*?\]", "", heading_text).strip()

        if any(name in heading_text for name in section_names):
            first_list = None  # als Fallback merken

            for sibling in heading.find_next_siblings():
                # Stopp bei nächster Überschrift (h2/h3 oder mw-heading div)
                if sibling.name in ["h2", "h3"]:
                    break
                if sibling.name == "div" and any(
                    "mw-heading" in c for c in sibling.get("class", [])
                ):
                    break

                # Priorität 1: Tabelle direkt
                if sibling.name == "table":
                    return parse_html_table(sibling)

                # Priorität 2: Tabelle innerhalb eines div
                table = sibling.find("table")
                if table:
                    return parse_html_table(table)

                # Fallback merken: erste <ul> in der Sektion
                if sibling.name == "ul" and first_list is None:
                    first_list = sibling
                # <ul> auch innerhalb eines div suchen
                elif first_list is None:
                    ul = sibling.find("ul")
                    if ul:
                        first_list = ul

            # Keine Tabelle gefunden – Liste rekursiv flach extrahieren
            if first_list:
                items = []
                for li in first_list.find_all("li"):
                    # get_text holt den kompletten Text inkl. verschachtelter Unterpunkte
                    text = li.get_text(separator=" ", strip=True)
                    text = re.sub(r"\[\d+\]", "", text).strip()
                    # Nur Top-Level <li> nehmen (nicht die verschachtelten Kinder)
                    # Erkennbar daran: direkte Kinder der first_list, nicht tiefer
                    if li.parent == first_list and text:
                        items.append(text)
                return items

    return []


# ─────────────────────────────────────────────
# 6. TABELLEN → RAG-TEXT SERIALISIEREN
# ─────────────────────────────────────────────
def squad_to_text(squad: list[dict], team: str) -> str | None:
    """Serialisiert die Kader-Tabelle als lesbaren RAG-Text."""
    if not squad:
        return None

    lines = [f"{team} – Aktueller Kader:"]
    for player in squad:
        # Flexibel: verschiedene mögliche Spaltennamen abfangen
        name     = player.get("Name") or player.get("Player") or player.get("Spieler", "")
        position = player.get("Pos.") or player.get("Position") or player.get("Pos", "")
        number   = player.get("No.") or player.get("#") or player.get("Nr.", "")
        nation   = player.get("Nat.") or player.get("Nation") or player.get("Nationality", "")

        if name:
            parts = []
            if number:  parts.append(f"#{number}")
            if name:    parts.append(name)
            if position: parts.append(f"({position})")
            if nation:  parts.append(f"[{nation}]")
            lines.append("  " + " ".join(parts))

    return "\n".join(lines) if len(lines) > 1 else None


def honours_to_text(honours: list, team: str) -> str | None:
    """
    Serialisiert Erfolge als lesbaren RAG-Text.
    Verarbeitet sowohl Tabellen (Liste von Dicts) als auch Listen (Liste von Strings).
    """
    if not honours:
        return None

    lines = [f"{team} – Erfolge und Titel:"]
    for row in honours:
        if isinstance(row, dict):
            # Aus Tabelle: Spaltenwerte zusammenfügen
            values = [v for v in row.values() if v]
            if values:
                lines.append("  " + " | ".join(values))
        elif isinstance(row, str) and row:
            # Aus Liste: direkt übernehmen
            lines.append(f"  {row}")

    return "\n".join(lines) if len(lines) > 1 else None



# ─────────────────────────────────────────────
# 8. HAUPTPROGRAMM
# ─────────────────────────────────────────────
def collect_all_articles(
    output_path: str = "data/wikipedia_articles.json",
) -> list[dict]:
    """
    Iteriert über alle Ligen & Teams und sammelt:
      - Fließtext (wie bisher)
      - Infobox-Daten
      - Kader-Tabelle
      - Erfolge-Tabelle
    Speichert alles in einer neuen JSON-Datei (Backup bleibt erhalten).
    """
    Path("data").mkdir(exist_ok=True)

    # Fortsetzen falls bereits Datei existiert
    if Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
        already_done = {a["wikipedia_title"] for a in articles}
        print(f"Bereits {len(articles)} Artikel vorhanden – wird fortgesetzt.\n")
    else:
        articles     = []
        already_done = set()

    total_teams = sum(len(teams) for teams in TEAMS.values())

    with tqdm(total=total_teams, desc="Teams gesamt") as pbar:
        for liga, teams in TEAMS.items():
            print(f"\nLiga: {liga}")
            for team in teams:
                pbar.set_postfix({"team": team[:30]})

                if any(a["team"] == team for a in articles):
                    print(f"Bereits vorhanden: {team}")
                    pbar.update(1)
                    continue

                # ── Fließtext ──────────────────────────
                print(f"Hole Fließtext: {team}")
                article = fetch_plaintext(team)
                if article is None:
                    pbar.update(1)
                    continue

                time.sleep(2)

                # ── HTML für Infobox + Tabellen ────────
                print(f"Hole HTML: {team}")
                soup = fetch_html(team)

                if soup is None:
                    print(f"HTML nach allen Versuchen fehlgeschlagen – Team wird beim nächsten Start erneut versucht.")
                    pbar.update(1)
                    continue  # nicht speichern!

                infobox_data = extract_infobox(soup, team)
                print(f"Infobox: {len(infobox_data)} Felder")

                squad_data = find_section_content(soup, SECTION_CURRENT_SQUAD)
                print(f"Kader: {len(squad_data)} Einträge")

                honours_data = find_section_content(soup, SECTION_HONOURS)
                print(f"Erfolge: {len(honours_data)} Einträge")

                time.sleep(2)

                # ── RAG-Chunks vorbereiten ─────────────
                rag_chunks = {}

                infobox_text = infobox_to_text(infobox_data, team)
                if infobox_text:
                    rag_chunks["infobox_text"] = infobox_text

                squad_text = squad_to_text(squad_data, team)
                if squad_text:
                    rag_chunks["kader_text"] = squad_text

                honours_text = honours_to_text(honours_data, team)
                if honours_text:
                    rag_chunks["erfolge_text"] = honours_text

                # ── Alles zusammenbauen ────────────────
                article.update({
                    "liga":     liga,
                    "team":     team,
                    "source":   "wikipedia",
                    "language": "en",
                    "infobox":  infobox_data,
                    "tabellen": {
                        "kader":   squad_data,
                        "erfolge": honours_data,
                    },
                    "rag_chunks": rag_chunks,
                })

                articles.append(article)
                already_done.add(article["wikipedia_title"])

                # Zwischenspeichern nach jedem Team
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(articles, f, ensure_ascii=False, indent=2)

                time.sleep(6)   # höfliche Pause zwischen Teams
                pbar.update(1)

    print(f"\nFertig! {len(articles)} Artikel in '{output_path}' gespeichert.")
    return articles


# ─────────────────────────────────────────────
# 8b. LIGA-ARTIKEL SAMMELN
#     Eigene, einfachere Pipeline: kein Kader, dafür Infobox + Honours/Rekorde
# ─────────────────────────────────────────────
def collect_league_articles(
    output_path: str = "data/wikipedia_leagues.json",
) -> list[dict]:
    """
    Holt die allgemeinen Liga-Artikel (Bundesliga, Premier League, etc.).
    Liefert: Fließtext, Infobox (Gründung, Anzahl Teams, aktueller Meister),
    sowie eine Erfolge/Rekorde-Sektion falls vorhanden.
    Speichert in einer eigenen Datei – getrennt von den Vereinsartikeln.
    """
    Path("data").mkdir(exist_ok=True)

    if Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            league_articles = json.load(f)
        already_done = {a["liga"] for a in league_articles}
        print(f"Bereits {len(league_articles)} Liga-Artikel vorhanden – wird fortgesetzt.\n")
    else:
        league_articles = []
        already_done = set()

    with tqdm(total=len(LEAGUES), desc="Ligen gesamt") as pbar:
        for liga, wiki_title in LEAGUES.items():
            pbar.set_postfix({"liga": liga})

            if liga in already_done:
                print(f"Bereits vorhanden: {liga}")
                pbar.update(1)
                continue

            # ── Fließtext ──────────────────────────
            print(f"\nHole Fließtext: {liga} ({wiki_title})")
            article = fetch_plaintext(wiki_title)
            if article is None:
                pbar.update(1)
                continue

            time.sleep(2)

            # ── HTML für Infobox + Erfolge/Rekorde ─
            print(f"Hole HTML: {liga}")
            soup = fetch_html(wiki_title)

            if soup is None:
                print(f"HTML fehlgeschlagen – Liga wird beim nächsten Start erneut versucht.")
                pbar.update(1)
                continue

            infobox_data = extract_infobox(soup, liga)
            print(f"Infobox: {len(infobox_data)} Felder")

            # Bei Liga-Artikeln heißen Rekorde/Titel-Sektionen oft anders als bei Vereinen
            records_data = find_section_content(
                soup, ["most titles", "champions", "records", "winners"]
            )
            print(f"Rekorde/Titel: {len(records_data)} Einträge")

            time.sleep(2)

            # ── RAG-Chunks vorbereiten ─────────────
            rag_chunks = {}

            infobox_text = infobox_to_text(infobox_data, liga)
            if infobox_text:
                rag_chunks["infobox_text"] = infobox_text

            records_text = honours_to_text(records_data, liga)  # gleiche Serialisierung wie Honours
            if records_text:
                rag_chunks["rekorde_text"] = records_text

            # ── Alles zusammenbauen ────────────────
            article.update({
                "liga":       liga,
                "source":     "wikipedia_league",
                "language":   "en",
                "infobox":    infobox_data,
                "tabellen":   {"rekorde": records_data},
                "rag_chunks": rag_chunks,
            })

            league_articles.append(article)
            already_done.add(liga)

            # Zwischenspeichern nach jeder Liga
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(league_articles, f, ensure_ascii=False, indent=2)

            time.sleep(6)
            pbar.update(1)

    print(f"\nFertig! {len(league_articles)} Liga-Artikel in '{output_path}' gespeichert.")
    return league_articles


# ─────────────────────────────────────────────
# 9. START
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # ── Schritt 1: Vereinsartikel ──────────────
    articles = collect_all_articles(
        output_path="data/wikipedia_articles.json",
    )

    # Kurze Übersicht
    print("\nÜbersicht Vereine:")
    from collections import Counter
    liga_count = Counter(a["liga"] for a in articles)
    for liga, count in liga_count.items():
        print(f"  {liga}: {count} Teams")

    # Vollständigkeit der neuen Felder
    print("\nVollständigkeit der neuen Felder (Vereine):")
    has_infobox  = sum(1 for a in articles if a.get("infobox"))
    has_kader    = sum(1 for a in articles if a.get("tabellen", {}).get("kader"))
    has_erfolge  = sum(1 for a in articles if a.get("tabellen", {}).get("erfolge"))
    total        = len(articles)
    print(f"  Infobox vorhanden:  {has_infobox}/{total}")
    print(f"  Kader vorhanden:    {has_kader}/{total}")
    print(f"  Erfolge vorhanden:  {has_erfolge}/{total}")

    # ── Schritt 2: Liga-Artikel ────────────────
    print("\n" + "=" * 60)
    print("  Liga-Artikel sammeln")
    print("=" * 60)
    league_articles = collect_league_articles(
        output_path="data/wikipedia_leagues.json",
    )

    print("\nVollständigkeit der neuen Felder (Ligen):")
    has_infobox_l = sum(1 for a in league_articles if a.get("infobox"))
    has_rekorde   = sum(1 for a in league_articles if a.get("tabellen", {}).get("rekorde"))
    total_l       = len(league_articles)
    print(f"  Infobox vorhanden:  {has_infobox_l}/{total_l}")
    print(f"  Rekorde vorhanden:  {has_rekorde}/{total_l}")