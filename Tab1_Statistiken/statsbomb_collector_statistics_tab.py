"""
statsbomb_collector.py

Lädt Event-Daten von StatsBomb für die 1. Bundesliga, mappt die Teamnamen
auf die Schreibweise von OpenLigaDB und berechnet die KPIs 'Chancen-Verwertung'
sowie 'Druck-Resistenz'.

Ausführen zum Testen:
    uv run python statsbomb_collector_statistics_tab.py
"""

import json
import os
import pandas as pd
from statsbombpy import sb
from pathlib import Path



skript_ordner = Path(__file__).resolve().parent
haupt_verzeichnis = skript_ordner.parent

data_ordner = haupt_verzeichnis / "data" / "tab1_statistik"
data_ordner.mkdir(parents=True, exist_ok=True)



# Das Vereins-Mapping: "OpenLigaDB-Name": "StatsBomb-Name"
TEAM_NAME_MAPPING = {
    "FC Bayern München": "Bayern Munich",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "Borussia Dortmund": "Borussia Dortmund",
    "VfB Stuttgart": "VfB Stuttgart",
    "RB Leipzig": "RB Leipzig",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "TSG 1899 Hoffenheim": "TSG Hoffenheim",
    "1. FC Heidenheim": "Heidenheim",
    "SV Werder Bremen": "Werder Bremen",
    "SC Freiburg": "Freiburg",
    "FC Augsburg": "Augsburg",
    "VfL Wolfsburg": "Wolfsburg",
    "1. FSV Mainz 05": "Mainz",
    "Borussia Mönchengladbach": "Borussia Mönchengladbach",
    "1. FC Union Berlin": "Union Berlin",
    "VfL Bochum": "Bochum",
    "1. FC Köln": "FC Cologne",
    "SV Darmstadt 98": "Darmstadt"
}
# ---------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------

def hole_bundesliga_events(saison_label: str):
    """
    Prüft die Verfügbarkeit der Saison und lädt alle Spiele sowie Events.
    Passt das OpenLigaDB-Label (z.B. '2023/24') an StatsBomb ('2023/2024') an.
    """
    # 1. Label-Konvertierung: Aus "2023/24" wird "2023/2024"
    if "/" in saison_label and len(saison_label) == 7:
        jahr_teil = saison_label.split("/")[0]
        statsbomb_saison_name = f"{jahr_teil}/20{saison_label.split('/')[1]}"
    else:
        statsbomb_saison_name = saison_label

    print(f" Prüfe StatsBomb-Verfügbarkeit für: {statsbomb_saison_name}...")
    
    try:
        all_comps = sb.competitions()
    except Exception as e:
        print(f"❌ Fehler bei der Verbindung zu StatsBomb: {e}")
        return None

    # Filter nach 1. Bundesliga und Saison
    match_comp = all_comps[
        (all_comps['competition_name'] == '1. Bundesliga') & 
        (all_comps['season_name'] == statsbomb_saison_name)
    ]
    
    # Anforderung: Falls nicht verfügbar, Meldung ausgeben & abbrechen
    if match_comp.empty:
        print(f" Hinweis: Für die Saison '{saison_label}' stehen keine freien StatsBomb-Daten bereit.")
        return None
        
    comp_id = int(match_comp['competition_id'].iloc[0])
    season_id = int(match_comp['season_id'].iloc[0])
    
    print(f" Saison gefunden! Lade Spielplan...")
    matches = sb.matches(competition_id=comp_id, season_id=season_id)
    
    # Für eine anschauliche Vorstellung exemplarisches Laden der Events
    all_events_list = []
    print(f" Lade Events für {len(matches)} Spiele. Das kann einen Moment dauern...")
    
    for match_id in matches['match_id']:
        try:
            # Holen der Events als DataFrame und Umwandlung in Datensätze (Dictionaries)
            events_df = sb.events(match_id=match_id)
            all_events_list.extend(events_df.to_dict(orient="records"))
        except Exception:
            continue
            
    return all_events_list


def berechne_kpis_fuer_verein(all_events, openliga_team_name: str):
    """
    Berechnet KPI 1 (Chancen-Verwertung) und KPI 2 (Druck-Resistenz) für ein Team.
    """
    # Anforderung: Teamname mappen zu OpenLigaDB
    statsbomb_team_name = TEAM_NAME_MAPPING.get(openliga_team_name, openliga_team_name)
    
    tore_echt = 0
    gesamt_xg = 0.0
    druck_situationen = 0
    erfolgreich_entkommen = 0

    #  alle gesammelten Events der Saison durchlaufen
    for i, event in enumerate(all_events):
        if event.get("team") != statsbomb_team_name:
            continue
            
        event_type = event.get("type")

        # --- KPI 1: CHANCEN-VERWERTUNG ---
        if event_type == "Shot":
            xg = event.get("shot_statsbomb_xg", 0.0)
            if pd.isna(xg): 
                xg = 0.0
            gesamt_xg += xg
            
            if event.get("shot_outcome") == "Goal":
                tore_echt += 1

        # --- KPI 2: DRUCK-RESISTENZ ---
        elif event_type == "Pressure":
            druck_situationen += 1
            # Schauen, ob das direkt folgende Event den Ball behalten hat
            if i + 1 < len(all_events):
                naechstes_event = all_events[i + 1]
                if naechstes_event.get("play_pattern") != "From Lost Ball":
                    erfolgreich_entkommen += 1

    # Endberechnungen
    chancen_verwertung = tore_echt - gesamt_xg
    druck_resistenz_quote = (erfolgreich_entkommen / druck_situationen * 100) if druck_situationen > 0 else 0.0

    return {
        "Verein": openliga_team_name,  # Zurückgemappt für die UI!
        "Chancen_Qualitaet_xG": round(gesamt_xg, 1),
        "Tor_Effizienz_Delta": round(chancen_verwertung, 1),
        "Druck_Resistenz_Prozent": round(druck_resistenz_quote, 1)
    }


def generiere_und_speichere_statsbomb_kpis(saison_label: str, ausgabe_datei: str):
    """
    Zentralfunktion: Steuert den gesamten Ablauf und speichert das UI-Bereite JSON.
    """
    events = hole_bundesliga_events(saison_label)
    
    # Falls keine Daten da sind (z.B. 2022/23), Erzeugen einer leeren Struktur mit Status
    if events is None:
        platzhalter = {
            "status": "keine_daten",
            "saison": saison_label
        }

        ausgabe_pfad = Path(ausgabe_datei)

    # data-Ordner automatisch anlegen
        ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)

        with open(ausgabe_pfad, "w", encoding="utf-8") as f:
            json.dump(platzhalter, f, indent=4, ensure_ascii=False)

        print(f"⚠ Keine StatsBomb-Daten für {saison_label}")
        return
    
    saison_kpis = {}
    
    # Berechne Werte für jeden Verein aus bekanntem Mapping
    for deutscher_name in TEAM_NAME_MAPPING.keys():
        vereins_ergebnisse = berechne_kpis_fuer_verein(events, deutscher_name)
        saison_kpis[deutscher_name] = vereins_ergebnisse

    # Endergebnis abspeichern
    ausgabe_pfad = Path(ausgabe_datei)

    # Ordner automatisch anlegen
    ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)

    with open(ausgabe_pfad, "w", encoding="utf-8") as f:
        json.dump(saison_kpis, f, indent=4, ensure_ascii=False)

    print(f" Fertig! Daten erfolgreich exportiert nach: {ausgabe_pfad}\n")

if __name__ == "__main__":

    skript_ordner = Path(__file__).resolve().parent
    haupt_verzeichnis = skript_ordner.parent

    ausgabe_pfad = haupt_verzeichnis / "data" / "statsbomb_kpis_2023_24.json"

    generiere_und_speichere_statsbomb_kpis(
        "2022/23",
        str(data_ordner / "statsbomb_kpis_2022_23.json")
    )

    generiere_und_speichere_statsbomb_kpis(
        "2023/24",
    str(data_ordner / "statsbomb_kpis_2023_24.json")
    )

    generiere_und_speichere_statsbomb_kpis(
        "2024/25",
        str(data_ordner / "statsbomb_kpis_2024_25.json")
    )
