import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
#client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#response = client.chat.completions.create(
   # model="gpt-4o-mini",
   # messages=[{"role": "user", "content": "Hallo!"}]
#)
#print(response.choices[0].message.content)

# import wikipedia
# from llama_index.readers.wikipedia import WikipediaReader

# wikipedia.set_lang("de")
# wikipedia.set_user_agent("GenSoccerAnalyzer/1.0 (Educational Project)")

# reader = WikipediaReader()
# documents = reader.load_data(
#     pages=["FC Bayern München", "Bayer Leverkusen"]
# )

# print(f"{len(documents)} Artikel geladen")
# print(documents[0].text[:300])

# import requests
# import time

# time.sleep(30)  # kurz warten

# response = requests.get(
#     "https://en.wikipedia.org/w/api.php",
#     params={
#         "action": "query",
#         "format": "json",
#         "titles": "SV Werder Bremen",
#         "prop": "extracts",
#         "explaintext": True,
#         "redirects": True,
#     },
#     headers={"User-Agent": "GenSoccerAnalyzer (Educational Project, Hochschule der Medien)"}
# )
# print(response.status_code)

from pinecone import Pinecone
from llama_index.embeddings.openai import OpenAIEmbedding
from dotenv import load_dotenv
import os

load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("gensocceranalyzer-wikipedia")
embed_model = OpenAIEmbedding(model="text-embedding-3-small", api_key=os.getenv("OPENAI_API_KEY"))

# Mit Filter nur Bayern-Chunks suchen und top_k erhöhen
query = "Wann wurde Bayern München gegründet?"
vector = embed_model.get_query_embedding(query)

results = index.query(
    vector=vector,
    top_k=10,  # mehr Chunks anzeigen
    include_metadata=True,
    filter={"team": "FC Bayern Munich"}
)

for i, match in enumerate(results["matches"]):
    print(f"[{i+1}] Score: {match['score']:.3f}")
    print(f"     {match['metadata']['text'][:200]}")
    print()

# Nach der Schleife
print("\n=== Chunk 5 komplett ===")
print(results["matches"][4]["metadata"]["text"])