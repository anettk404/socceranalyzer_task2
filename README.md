# GenSoccerAnalyzer

GenSoccerAnalyzer ist eine KI-gestützte Fußball-Analyse-App, die natürlichsprachliche Fragen über Fußballdaten beantwortet. Ein Multi-Agenten-System auf Basis von LangGraph routet jede Anfrage automatisch an die passende Datenquelle und validiert die Antwort auf Halluzinationen.

**Autorin:** Annette Kufner, Susanne Schmid, Selma Elezovic

---

## Datenquellen

| Quelle | Inhalt | Agent |
|---|---|---|
| **OpenLigaDB** | Bundesliga-Tabellen, Spielpläne, Ergebnisse (Saison 2023/24) | `openligadb_agent` |
| **StatsBomb Open Data** | Ereignisdaten: xG, Schüsse, Pässe, Pressing, Spielphasen | `statsbomb_agent` |
| **Wikipedia (Pinecone)** | Vereinsgeschichte, Trainer-Biografien, Stadien, Titel | `rag_agent` |
| **Kombiniert** | Fragen die beide strukturierten Quellen gleichzeitig benötigen | `combined_agent` |

---

## Architektur

```
Frage
  └─► Question Rewriter      (Folgefragen mit Kontext anreichern)
        └─► Supervisor        (Routing-Entscheidung per LLM)
              ├─► openligadb_agent
              ├─► statsbomb_agent
              ├─► combined_agent
              └─► rag_agent
                    └─► Aggregator   (Teilergebnisse zusammenfassen)
                          └─► Validator  (Halluzinations-Check + Confidence Score)
                                └─► Finale Antwort
```

Der Supervisor kann mehrere Agenten iterativ aufrufen, bevor er aggregiert. Der Validator gibt einen Confidence-Score (0.0–1.0) zurück — niedrige Werte signalisieren, dass die Antwort nicht ausreichend durch Quellen belegbar ist.

---

## Projektstruktur

```
gen-soccer-analyzer/
├── agents/
│   ├── orchestrator.py        # LangGraph-Graph (Supervisor-Pattern)
│   ├── agent_openligadb.py    # SQL-Agent für OpenLigaDB
│   ├── agent_statsbomb.py     # SQL-Agent für StatsBomb
│   ├── agent_combined.py      # Cross-Source-Agent
│   ├── agent_rag.py           # RAG-Agent (Pinecone + Wikipedia)
│   ├── agent_validator.py     # Halluzinations-Validator
│   ├── prompts.yaml           # Alle System-Prompts
│   ├── shared.py              # LLM, GraphState, gemeinsame Konfiguration
│   └── db.py                  # Datenbankverbindung
├── frontend/
│   ├── design.py              # Streamlit-App (Einstiegspunkt)
│   ├── tab_chat.py            # Chat-Interface
│   ├── tab_statistics.py      # Statistik-Tab
│   ├── tab_clustering.py      # Clustering-Tab
│   └── helpers.py             # UI-Hilfsfunktionen
├── data/
│   ├── evaluate_end_to_end.py     # End-to-End Pipeline Evaluation
│   ├── evaluate_validator.py      # Validator Catch Rate Evaluation
│   ├── evaluate_tool_selection.py # Routing Accuracy Evaluation
│   ├── structured_data/           # Datenbankbefüllung (OpenLigaDB, StatsBomb)
│   └── rag_data/                  # RAG-Pipeline und Evaluation
├── services/                  # Datenlogik, KPI-Services, Sentiment
├── Grundlagen/                # Vorbereitende Notebooks
└── langgraph.json             # LangGraph Studio Konfiguration
```

---

## Voraussetzungen

- Python 3.12+
- API-Keys: `OPENAI_API_KEY`, `PINECONE_API_KEY`, `LANGSMITH_API_KEY`

Erstelle eine `.env`-Datei im Projektroot:

```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
LANGSMITH_API_KEY=...
```

---

## Installation

```bash
# Empfohlen: mit uv
uv sync

# Alternativ: mit pip
pip install -r requirements.txt
```

---

## App starten

```bash
uv run streamlit run frontend/design.py
```

---

## Evaluation

Die Evaluation besteht aus drei unabhängigen Skripten:

```bash
# 1. Routing-Genauigkeit des Supervisors
uv run python data/evaluate_tool_selection.py

# 2. Halluzinations-Erkennung des Validators
uv run python data/evaluate_validator.py

# 3. End-to-End Pipeline (dauert ~5–10 Minuten)
uv run python data/evaluate_end_to_end.py

#  4. RAG Evaluation
uv run python data/rag_data/evaluate_rag.py
```
## Multi-Agenten System

| Metrik | Beschreibung |
|---|---|
| **Tool Selection Accuracy** | Anteil korrekt gerouteter Fragen |
| **Validator Catch Rate** | Anteil erkannter Halluzinationen (confidence < 0.6) |
| **Auto-Correction Rate** | Anteil tatsächlich veränderter Antworten |
| **False Positive Rate** | Korrekte Antworten fälschlich markiert |
| **Functional Pass Rate** | Route + Antwortinhalt korrekt |
| **Strict Pass Rate** | Route + Inhalt + Confidence ≥ 0.4 |

---

### RAG-Agent

| Metrik | Beschreibung |
|---|---|
| **Faithfulness** | Ist die Antwort treu gegenüber den abgerufenen Chunks — keine erfundenen Fakten? |
| **Answer Relevancy** | Beantwortet die Antwort tatsächlich die gestellte Frage? |
| **Context Precision** | Sind die abgerufenen Chunks relevant für die Frage? |

## Visualisierungen

![Wortwolke](docs/images/wortwolke.png)

Die App enthält u.a. eine Wortwolken-Visualisierung auf Basis von Wikipedia-Artikeln zu Vereinen und Ligen.

---

## LangGraph Studio

```bash
uv run langgraph dev
```

Anschließend im Browser öffnen: [smith.langchain.com](https://smith.langchain.com) → Studio

---

## Hinweise

- `data/structured_data/soccer.db` ist die lokale SQLite-Datenbank und nicht für Git-Deployment geeignet — für produktiven Betrieb eine Cloud-Datenbank verwenden.
- Falls Sentiment-Daten fehlen: `data/wikipedia_articles.json` prüfen.
- Falls Wortwolken fehlen: `data/haeufigkeiten_wortwolken.json` prüfen.
- NLTK lädt beim ersten Start automatisch benötigte Ressourcen nach.
