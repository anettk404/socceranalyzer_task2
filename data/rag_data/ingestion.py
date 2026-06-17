"""
GenSoccerAnalyzer – Schritt 2: Chunking & Pinecone-Upload
==========================================================
Liest die wikipedia_articles.json, chunked die deutschen Texte mit LlamaIndex
(1024 Tokens, 100 Overlap), erstellt OpenAI Embeddings und speichert alles
direkt über den Pinecone Python Client (v9.x) in Pinecone.

LlamaIndex: nur für Chunking & Embedding
Pinecone:   direkt für Upload & Retrieval (kein Wrapper nötig)

Voraussetzungen (einmalig installieren):
    uv add llama-index-core llama-index-embeddings-openai pinecone python-dotenv tqdm
"""

import json
import os
import uuid
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

from llama_index.core import Document, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding

from pinecone import Pinecone, ServerlessSpec

# ─────────────────────────────────────────────
# 1. KONFIGURATION
# ─────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME       = "gensocceranalyzer-wikipedia"
EMBEDDING_MODEL  = "text-embedding-3-small"  # multilingual, 1536 Dimensionen
EMBEDDING_DIM    = 1536
CHUNK_SIZE       = 1024  # Tokens pro Chunk
CHUNK_OVERLAP    = 100   # Überlappung zwischen Chunks
BATCH_SIZE       = 100   # Wie viele Vektoren pro Pinecone-Upsert-Aufruf

INPUT_FILE       = "data/wikipedia_articles.json"


# ─────────────────────────────────────────────
# 2. OPENAI EMBEDDING KONFIGURIEREN
# ─────────────────────────────────────────────
def setup_embedding() -> OpenAIEmbedding:
    embed_model = OpenAIEmbedding(
        model=EMBEDDING_MODEL,
        api_key=OPENAI_API_KEY,
    )
    # LlamaIndex global konfigurieren
    Settings.embed_model = embed_model
    Settings.chunk_size = CHUNK_SIZE
    Settings.chunk_overlap = CHUNK_OVERLAP
    print(f"✅ Embedding-Modell: {EMBEDDING_MODEL} ({EMBEDDING_DIM} Dimensionen)")
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
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"  # Gratis-Tier Region
            )
        )
        print(f"✅ Index '{INDEX_NAME}' erstellt.")
    else:
        print(f"✅ Index '{INDEX_NAME}' bereits vorhanden – wird verwendet.")

    return pc.Index(INDEX_NAME)


# ─────────────────────────────────────────────
# 4. ARTIKEL LADEN & IN LLAMAINDEX DOCUMENTS UMWANDELN
# ─────────────────────────────────────────────
def load_documents(input_file: str) -> list[Document]:
    print(f"\n📂 Lade Artikel aus '{input_file}'...")

    with open(input_file, "r", encoding="utf-8") as f:
        articles = json.load(f)

    documents = []
    for article in articles:
        # Deutschen Text bevorzugen, Fallback auf Englisch
        text = article.get("text_de", article.get("text_en", "")).strip()

        # Mehrfache Leerzeilen bereinigen
        text = "\n\n".join(
            block.strip()
            for block in text.split("\n\n")
            if block.strip()
        )

        if not text:
            print(f"  ⚠️  Kein Text für: {article.get('team', '?')}")
            continue

        doc = Document(
            text=text,
            metadata={
                "team":            article.get("team", ""),
                "liga":            article.get("liga", ""),
                "wikipedia_title": article.get("wikipedia_title", ""),
                "source":          "wikipedia",
                "language":        "de",
            },
        )
        documents.append(doc)

    print(f"✅ {len(documents)} Dokumente geladen.")
    return documents


# ─────────────────────────────────────────────
# 5. CHUNKING
# ─────────────────────────────────────────────
def chunk_documents(documents: list[Document]) -> list:
    print(f"\n✂️  Chunking ({CHUNK_SIZE} Tokens, {CHUNK_OVERLAP} Overlap)...")

    splitter = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    nodes = splitter.get_nodes_from_documents(documents, show_progress=True)
    print(f"✅ {len(nodes)} Chunks aus {len(documents)} Dokumenten.")
    print(f"   Ø {len(nodes) / len(documents):.1f} Chunks pro Dokument.")
    return nodes


# ─────────────────────────────────────────────
# 6. EMBEDDINGS ERSTELLEN & IN PINECONE HOCHLADEN
# ─────────────────────────────────────────────
def embed_and_upload(nodes: list, pinecone_index, embed_model: OpenAIEmbedding):
    # Index leeren – nur einkommentieren wenn Neu-Befüllung gewünscht:
    pinecone_index.delete(delete_all=True)
   
    # Prüfen ob Index bereits Daten enthält
    stats = pinecone_index.describe_index_stats()
    existing_count = stats["total_vector_count"]

    if existing_count > 0:
        print(f"\n⚠️  Index enthält bereits {existing_count} Vektoren – Upload übersprungen.")
        print("   Zum Neu-Befüllen: pinecone_index.delete(delete_all=True) ausführen.")
        return

    print(f"\n🚀 Erstelle Embeddings und lade {len(nodes)} Chunks in Pinecone hoch...")

    # Vektoren in Batches verarbeiten (API-Limits vermeiden)
    vectors = []
    texts = [node.get_content() for node in nodes]

    print("  📐 Erstelle Embeddings via OpenAI...")
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding Batches"):
        batch_texts = texts[i:i + BATCH_SIZE]
        batch_nodes = nodes[i:i + BATCH_SIZE]

        # Embeddings für den ganzen Batch auf einmal erstellen
        embeddings = embed_model.get_text_embedding_batch(batch_texts)

        for node, embedding in zip(batch_nodes, embeddings):
            vectors.append({
                "id":       str(uuid.uuid4()),   # eindeutige ID pro Chunk
                "values":   embedding,
                "metadata": {
                    **node.metadata,             # team, liga, wikipedia_title, source, language
                    "text": node.get_content(),  # Text im Metadata speichern für Retrieval
                }
            })

    # In Batches in Pinecone hochladen
    print(f"  📤 Lade {len(vectors)} Vektoren in Pinecone hoch...")
    for i in tqdm(range(0, len(vectors), BATCH_SIZE), desc="Pinecone Upsert"):
        batch = vectors[i:i + BATCH_SIZE]
        pinecone_index.upsert(vectors=batch)

    print(f"✅ Alle {len(vectors)} Chunks erfolgreich in Pinecone gespeichert!")


# ─────────────────────────────────────────────
# 7. SCHNELLTEST: RETRIEVAL PRÜFEN
# ─────────────────────────────────────────────
def test_retrieval(pinecone_index, embed_model: OpenAIEmbedding, top_k: int = 7):
    print("\n🔍 Schnelltest: Retrieval...")

    test_queries = [
        "Wann wurde Bayern München gegründet?",
        "Welche Erfolge hat Borussia Dortmund?",
        "Geschichte von Real Madrid",
    ]

    for query in test_queries:
        print(f"\n  Frage: '{query}'")

        # Frage embedden
        query_vector = embed_model.get_query_embedding(query)

        # In Pinecone suchen
        results = pinecone_index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
        )

        for i, match in enumerate(results["matches"]):
            meta = match["metadata"]
            print(f"  [{i+1}] Team: {meta.get('team')} "
                  f"| Liga: {meta.get('liga')} "
                  f"| Score: {match['score']:.3f}")
            print(f"       Text: {meta.get('text', '')[:150]}...")


# ─────────────────────────────────────────────
# 8. HAUPTPROGRAMM
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not OPENAI_API_KEY or not PINECONE_API_KEY:
        raise ValueError(
            "❌ API Keys fehlen! Bitte OPENAI_API_KEY und PINECONE_API_KEY "
            "in der .env Datei setzen."
        )

    if not Path(INPUT_FILE).exists():
        raise FileNotFoundError(
            f"❌ '{INPUT_FILE}' nicht gefunden! "
            "Bitte zuerst wikipedia_collector.py ausführen."
        )

    embed_model    = setup_embedding()
    pinecone_index = setup_pinecone()
    documents      = load_documents(INPUT_FILE)
    nodes          = chunk_documents(documents)
    embed_and_upload(nodes, pinecone_index, embed_model)
    test_retrieval(pinecone_index, embed_model)

    print("\n🎉 Fertig! Pinecone Index ist bereit für den Wikipedia-Agenten.")