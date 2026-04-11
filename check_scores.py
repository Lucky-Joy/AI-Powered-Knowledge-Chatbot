import sys, time
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from embeddings.embedder import embed_query
from vectorstore.chroma_store import search

print("Embedding query...")
q = embed_query('What are the guidelines for opening a small account?')

print("Searching ChromaDB...")
results = search(q)

print("\nRaw scores from ChromaDB:")
for i, r in enumerate(results):
    raw = r.get('score', 'N/A')
    converted = max(0.0, 1.0 - raw)
    print(f"  Chunk {i+1}: raw_distance={raw:.4f} -> confidence={converted:.4f} | {r['source']} p{r['page']}")
