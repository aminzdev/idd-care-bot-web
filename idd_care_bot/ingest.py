import os
import glob
import json
import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer
from utils import clean_text, chunk_text

DATA_DIR = "data"
STORAGE_DIR = "storage"
EMBEDDING_MODEL = os.getenv(
    # "EMBEDDING_MODEL", "sentence-transformers/multi-qa-mpnet-base-dot-v1"
    "EMBEDDING_MODEL",
    "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
)
os.makedirs(STORAGE_DIR, exist_ok=True)

# Load embedding model
print("Loading embedding model...")
embedder = SentenceTransformer(EMBEDDING_MODEL)

all_chunks = []

# Read all CSVs under data/
for path in glob.glob(os.path.join(DATA_DIR, "**", "*.csv"), recursive=True):
    print(f"Reading {path}")
    df = pd.read_csv(path)

    for _, row in df.iterrows():
        rec = {
            "title": clean_text(str(row.get("Title", ""))),
            "authors": clean_text(str(row.get("Authors", ""))),
            "abstract": clean_text(str(row.get("Abstract", ""))),
            "source_file": os.path.basename(path),
        }
        if not rec["abstract"] and not rec["title"]:
            continue

        # Combine title + abstract into one text
        base_text = f"{rec['title']}\n\n{rec['abstract']}".strip()
        chunks = chunk_text(base_text, max_len=1200, overlap=150)

        for i, ch in enumerate(chunks):
            all_chunks.append(
                {
                    "text": ch,
                    "meta": {**rec, "chunk_id": i},
                }
            )

print(f"Total chunks: {len(all_chunks)}")

# Build embeddings
texts = [c["text"] for c in all_chunks]
print("Embedding chunks...")
embs = embedder.encode(
    texts, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True
)

# Build FAISS index
index = faiss.IndexFlatIP(embs.shape[1])
index.add(embs)

# Save index + metadata
faiss.write_index(index, os.path.join(STORAGE_DIR, "index.faiss"))

with open(os.path.join(STORAGE_DIR, "meta.json"), "w", encoding="utf-8") as f:
    json.dump([c["meta"] for c in all_chunks], f, ensure_ascii=False, indent=2)

print(f"Saved index and metadata in {STORAGE_DIR}/")
