"""
GenSoccerAnalyzer – Schritt 2: Pinecone-Indexierung

Autorin: Susanne Schmid
=====================================================
Liest die gesammelten Wikipedia-Artikel und indexiert sie in Pinecone.

Chunk-Strategie:
  - Infobox → atomare Chunks pro Themengruppe (Trainer, Stadion, Gründung, Name, Liga, Finanzen, Sonstiges)
    → themenreine Chunks für präzises Retrieval bei Faktenfragen
  - Kader   → ein Chunk pro Verein (komplette Liste)
  - Erfolge → ein Chunk pro Verein (komplette Liste)
  - Fließtext → SentenceSplitter (1024 Tokens, 100 Overlap)

Embedding-Modell: text-embedding-3-small (1536 Dimensionen, multilingual)
Vektordatenbank: Pinecone (Cosine Similarity)

Ergebnis: ~1776 Chunks in Pinecone (836 strukturiert, 940 Fließtext)

Voraussetzungen:
    pip install llama-index-core llama-index-embeddings-openai pinecone python-dotenv tqdm
"""

import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from llama_index.core import Document, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from tqdm import tqdm

# ─────────────────────────────────────────────
# 1. KONFIGURATION
# ─────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME       = "gensocceranalyzer-wikipedia"   # neuer Index, alter bleibt als Backup
EMBEDDING_MODEL  = "text-embedding-3-small"
EMBEDDING_DIM    = 1536
CHUNK_SIZE       = 1024   # Tokens pro Fließtext-Chunk
CHUNK_OVERLAP    = 100
BATCH_SIZE       = 100

TEAMS_FILE       = "data/wikipedia_articles.json"
LEAGUES_FILE     = "data/wikipedia_leagues.json"


# ─────────────────────────────────────────────
# 2. OPENAI EMBEDDING KONFIGURIEREN
# ─────────────────────────────────────────────
def setup_embedding() -> OpenAIEmbedding:
    embed_model = OpenAIEmbedding(model=EMBEDDING_MODEL, api_key=OPENAI_API_KEY)
    Settings.embed_model   = embed_model
    Settings.chunk_size    = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP
    print(f"Embedding-Modell: {EMBEDDING_MODEL} ({EMBEDDING_DIM} Dimensionen)")
    return embed_model


# ─────────────────────────────────────────────
# 3. PINECONE INDEX ERSTELLEN
# ─────────────────────────────────────────────
def setup_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    existing = [idx.name for idx in pc.list_indexes()]

    if INDEX_NAME not in existing:
        print(f"🆕 Erstelle Pinecone Index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"Index '{INDEX_NAME}' erstellt.")
    else:
        print(f"Index '{INDEX_NAME}' bereits vorhanden – wird verwendet.")

    return pc.Index(INDEX_NAME)


# ─────────────────────────────────────────────
# 4a. ID-SAFE SLUGS
#     Pinecone Vector-IDs erlauben nur ASCII – Umlaute etc. müssen raus.
#     Die lesbaren Originaltitel bleiben unverändert in den Metadaten.
# ─────────────────────────────────────────────
import re
import unicodedata

def slugify(text: str) -> str:
    """Wandelt einen String in eine ASCII-sichere ID um (für Pinecone Vector-IDs)."""
    # Umlaute/Akzente in Basis-Zeichen umwandeln (ö → o, é → e, etc.)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    # Alles außer Buchstaben/Zahlen durch Unterstrich ersetzen
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")
    return slug


# ─────────────────────────────────────────────
# 4b. STRUKTURIERTE CHUNKS
# ─────────────────────────────────────────────

# Thematische Gruppen für atomare Infobox-Chunks.
# Jede Gruppe wird ein eigener Chunk → präzises Retrieval pro Frage-Typ.
INFOBOX_GROUPS = {
    "trainer":   ["Head coach", "Manager"],
    "stadion":   ["Ground", "Stadium", "Capacity"],
    "gruendung": ["Founded"],
    "name":      ["Full name", "Short name", "Nicknames", "Nickname"],
    "liga":      ["League", "2025–26", "2024–25"],
    "finanzen":  ["Owner", "Owners", "Owner(s)", "President", "Chairman", "CEO"],
}

# Deutsche Synonyme (gleiche Map wie im Collector)
INFOBOX_FIELD_SYNONYMS = {
    "Founded":      "Founded / Gegründet",
    "Full name":    "Full name / Vollständiger Name",
    "Capacity":     "Capacity / Kapazität (Stadion)",
    "League":       "League / Liga",
    "Head coach":   "Head coach / Trainer / Cheftrainer",
    "Manager":      "Manager / Trainer / Cheftrainer",
    "Nicknames":    "Nicknames / Spitzname",
    "Nickname":     "Nickname / Spitzname",
    "President":    "President / Präsident",
    "Owner":        "Owner / Besitzer / Eigentümer",
    "Owners":       "Owners / Besitzer / Eigentümer",
    "Owner(s)":     "Owner(s) / Besitzer / Eigentümer",
    "Ground":       "Ground / Stadion",
    "Stadium":      "Stadium / Stadion",
    "Short name":   "Short name / Kurzname",
    "Chairman":     "Chairman / Vorsitzender",
    "CEO":          "CEO / Geschäftsführer",
    "Home colours": "Home colours / Heimfarben",
}


def build_structured_chunks(article: dict) -> list[dict]:
    """
    Baut strukturierte Chunks aus einem Artikel:
    - Infobox → atomare Chunks pro Themengruppe (Trainer, Stadion, Gründung, ...)
      → präzises Retrieval, weil jeder Chunk themenrein ist
    - Kader   → ein Chunk pro Verein (komplette Liste gewünscht)
    - Erfolge → ein Chunk pro Verein (komplette Liste gewünscht)
    """
    team = article.get("team", article.get("liga", ""))
    safe_id = slugify(article.get("wikipedia_title", team))

    base_metadata = {
        "team":            team,
        "liga":            article["liga"],
        "wikipedia_title": article.get("wikipedia_title", ""),
        "source":          article.get("source", "wikipedia"),
        "language":        "en",
    }

    results = []

    # ── Atomare Infobox-Chunks ─────────────────
    infobox = article.get("infobox", {})
    if infobox:
        field_to_group = {}
        for group_name, fields in INFOBOX_GROUPS.items():
            for field in fields:
                field_to_group[field] = group_name

        grouped = {g: {} for g in INFOBOX_GROUPS}
        grouped["sonstige"] = {}

        for key, value in infobox.items():
            group = field_to_group.get(key, "sonstige")
            grouped[group][key] = value

        for group_name, fields in grouped.items():
            if not fields:
                continue
            lines = [f"{team} – {group_name.capitalize()}:"]
            for key, value in fields.items():
                display_key = INFOBOX_FIELD_SYNONYMS.get(key, key)
                lines.append(f"  {display_key}: {value}")
            text = "\n".join(lines)
            results.append({
                "id":       f"{safe_id}_infobox_{group_name}",
                "text":     text,
                "metadata": {**base_metadata, "chunk_type": f"infobox_{group_name}"},
            })

    # ── Kader – ein Chunk pro Verein ──────────
    kader_text = article.get("rag_chunks", {}).get("kader_text")
    if kader_text:
        results.append({
            "id":       f"{safe_id}_kader",
            "text":     kader_text,
            "metadata": {**base_metadata, "chunk_type": "kader"},
        })

    # ── Erfolge – ein Chunk pro Verein ────────
    erfolge_text = (
        article.get("rag_chunks", {}).get("erfolge_text") or
        article.get("rag_chunks", {}).get("rekorde_text")
    )
    if erfolge_text:
        results.append({
            "id":       f"{safe_id}_erfolge",
            "text":     erfolge_text,
            "metadata": {**base_metadata, "chunk_type": "erfolge"},
        })

    return results


# ─────────────────────────────────────────────
# 5. ARTIKEL LADEN (Vereine + Ligen)
# ─────────────────────────────────────────────
def load_articles() -> tuple[list[dict], list[dict]]:
    """Lädt Vereins- und Liga-Artikel getrennt, da Liga-Artikel kein 'team' haben."""
    print(f"\n📂 Lade Vereinsartikel aus '{TEAMS_FILE}'...")
    with open(TEAMS_FILE, "r", encoding="utf-8") as f:
        teams = json.load(f)
    print(f"{len(teams)} Vereinsartikel geladen.")

    leagues = []
    if Path(LEAGUES_FILE).exists():
        print(f"📂 Lade Liga-Artikel aus '{LEAGUES_FILE}'...")
        with open(LEAGUES_FILE, "r", encoding="utf-8") as f:
            leagues = json.load(f)
        print(f"{len(leagues)} Liga-Artikel geladen.")
    else:
        print(f"'{LEAGUES_FILE}' nicht gefunden – Liga-Artikel werden übersprungen.")

    return teams, leagues


# ─────────────────────────────────────────────
# 6. ALLES ZU CHUNKS VERARBEITEN
#    (strukturiert + generischer Fließtext-Split)
# ─────────────────────────────────────────────
def build_all_chunks(teams: list[dict], leagues: list[dict]) -> list[dict]:
    """
    Baut die komplette Chunk-Liste:
      - strukturierte Chunks (infobox/kader/erfolge) direkt aus den Feldern
      - Fließtext (text_en) via LlamaIndex SentenceSplitter gesplittet
    Jeder Chunk ist ein dict mit id/text/metadata, bereit für Embedding.
    """
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    all_articles = teams + leagues
    all_chunks = []

    print(f"\nBaue Chunks für {len(all_articles)} Artikel...")
    for article in tqdm(all_articles, desc="Artikel verarbeiten"):
        # 1. Strukturierte Chunks (infobox, kader, erfolge)
        all_chunks.extend(build_structured_chunks(article))

        # 2. Fließtext chunken (Englisch, da Übersetzung deaktiviert)
        text_en = (article.get("text_en") or "").strip()
        if not text_en:
            continue

        wikipedia_title = article.get("wikipedia_title", "")
        safe_id = slugify(wikipedia_title) or slugify(article.get("team", article.get("liga", "")))
        base_metadata = {
            "team":            article.get("team", article.get("liga", "")),
            "liga":            article["liga"],
            "wikipedia_title": wikipedia_title,
            "source":          article.get("source", "wikipedia"),
            "language":        "en",
            "chunk_type":      "text",
        }

        doc = Document(text=text_en, metadata=base_metadata)
        nodes = splitter.get_nodes_from_documents([doc])

        for i, node in enumerate(nodes):
            all_chunks.append({
                "id":       f"{safe_id}_text_{i}",
                "text":     node.get_content(),
                "metadata": base_metadata,
            })

    n_structured = sum(1 for c in all_chunks if c["metadata"]["chunk_type"] != "text")
    n_text       = sum(1 for c in all_chunks if c["metadata"]["chunk_type"] == "text")
    print(f"{len(all_chunks)} Chunks gesamt "
          f"({n_structured} strukturiert: infobox/kader/erfolge, {n_text} Fließtext)")

    return all_chunks


# ─────────────────────────────────────────────
# 7. EMBEDDINGS ERSTELLEN & IN PINECONE HOCHLADEN
# ─────────────────────────────────────────────
def embed_and_upload(chunks: list[dict], pinecone_index, embed_model: OpenAIEmbedding):
    # Index leeren – nur einkommentieren wenn Neu-Befüllung gewünscht:
    # pinecone_index.delete(delete_all=True)

    # Prüfen ob Index bereits Daten enthält
    stats = pinecone_index.describe_index_stats()
    existing_count = stats["total_vector_count"]

    if existing_count > 0:
        print(f"\nIndex enthält bereits {existing_count} Vektoren – Upload übersprungen.")
        print("   Zum Neu-Befüllen: oben 'pinecone_index.delete(delete_all=True)' einkommentieren.")
        return

    print(f"\nErstelle Embeddings und lade {len(chunks)} Chunks in Pinecone hoch...")

    vectors = []
    texts = [c["text"] for c in chunks]

    print("Erstelle Embeddings via OpenAI...")
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding Batches"):
        batch_texts = texts[i:i + BATCH_SIZE]
        batch_chunks = chunks[i:i + BATCH_SIZE]

        embeddings = embed_model.get_text_embedding_batch(batch_texts)

        for chunk, embedding in zip(batch_chunks, embeddings):
            vectors.append({
                "id":       chunk["id"] or str(uuid.uuid4()),
                "values":   embedding,
                "metadata": {**chunk["metadata"], "text": chunk["text"]},
            })

    print(f"Lade {len(vectors)} Vektoren in Pinecone hoch...")
    for i in tqdm(range(0, len(vectors), BATCH_SIZE), desc="Pinecone Upsert"):
        batch = vectors[i:i + BATCH_SIZE]
        pinecone_index.upsert(vectors=batch)

    print(f"Alle {len(vectors)} Chunks erfolgreich in Pinecone gespeichert!")


# ─────────────────────────────────────────────
# 8. SCHNELLTEST: RETRIEVAL PRÜFEN
# ─────────────────────────────────────────────
def test_retrieval(pinecone_index, embed_model: OpenAIEmbedding, top_k: int = 3):
    print("\nSchnelltest: Retrieval...")

    test_queries = [
        "Wann wurde Bayern München gegründet?",
        "Wer ist der aktuelle Trainer von Bayern München?",
        "Welche Erfolge hat Borussia Dortmund?",
        "Wer spielt im Kader von RB Leipzig?"
    ]

    for query in test_queries:
        print(f"\n  Frage: '{query}'")
        query_vector = embed_model.get_query_embedding(query)

        results = pinecone_index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
        )

        for i, match in enumerate(results["matches"]):
            meta = match["metadata"]
            print(f"  [{i+1}] {meta.get('team')} | {meta.get('chunk_type')} "
                  f"| Score: {match['score']:.3f}")
            print(f"       {meta.get('text', '')[:150]}...")


# ─────────────────────────────────────────────
# 9. HAUPTPROGRAMM
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not OPENAI_API_KEY or not PINECONE_API_KEY:
        raise ValueError(
            "API Keys fehlen! Bitte OPENAI_API_KEY und PINECONE_API_KEY "
            "in der .env Datei setzen."
        )

    if not Path(TEAMS_FILE).exists():
        raise FileNotFoundError(
            f"'{TEAMS_FILE}' nicht gefunden! "
            "Bitte zuerst wikipedia_collector.py ausführen."
        )

    embed_model    = setup_embedding()
    pinecone_index = setup_pinecone()
    teams, leagues = load_articles()
    chunks         = build_all_chunks(teams, leagues)
    embed_and_upload(chunks, pinecone_index, embed_model)
    test_retrieval(pinecone_index, embed_model)

    print("\nFertig! Pinecone Index ist bereit für den Wikipedia-Agenten.")