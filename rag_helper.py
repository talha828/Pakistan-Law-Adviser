import pickle
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np

# === Load vector DB ===
def load_faiss_index(index_path="/home/kali/Downloads/AI-laywer/model/faiss_index.index", metadata_path="/home/kali/Downloads/AI-laywer/model/metadata.pkl"):
    index = faiss.read_index(index_path)
    with open(metadata_path, "rb") as f:
        chunks = pickle.load(f)
    return index, chunks

# === Embed the query ===
def embed_query(query, model_name="paraphrase-MiniLM-L3-v2"):
    model = SentenceTransformer(model_name)
    return model.encode([query])

# === Search top N results ===
def search_index(index, query_embedding, chunks, top_k=5):
    D, I = index.search(np.array(query_embedding), top_k)
    return [chunks[i] for i in I[0]]
