import json
import os
from typing import Dict, List

import faiss
import httpx
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI
import ollama  # noqa: F401
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from prompts import FEWSHOT, SYSTEM_PROMPT
from safety import NON_DIAGNOSTIC_PREFACE, check_red_flags

# Load environment
load_dotenv()
INDEX_DIR = os.getenv("INDEX_DIR", "storage")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/multi-qa-mpnet-base-dot-v1"
)
TOP_K = int(os.getenv("TOP_K", 5))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 700))

# LLM provider config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
API_URL = os.getenv("API_URL", "http://localhost:8000/chat")

# FastAPI app
app = FastAPI(title="IDDCareBot RAG API")

# Load FAISS + metadata
index = faiss.read_index(os.path.join(INDEX_DIR, "index.faiss"))
with open(os.path.join(INDEX_DIR, "meta.json"), "r", encoding="utf-8") as f:
    META = json.load(f)

embedder = SentenceTransformer(EMBEDDING_MODEL)


# ------------------------------
# Schemas
# ------------------------------
class ChatRequest(BaseModel):
    query: str


class Citation(BaseModel):
    title: str | None
    authors: str | None
    year: str | None
    url: str | None
    source_file: str | None
    chunk_id: int | None
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]


# ------------------------------
# Retrieval
# ------------------------------
def embed(text: str):
    emb = embedder.encode([text])  # returns (1, dim)
    return emb[0]


def retrieve(query: str, top_k: int = TOP_K) -> List[Dict]:
    q_emb = embed(query)  # must match ingest.py embedding model
    q_emb = np.array(q_emb, dtype="float32")

    # Ensure correct shape: (1, dim)
    if q_emb.ndim == 1:
        q_emb = q_emb[np.newaxis, :]

    D, I = index.search(q_emb, top_k)

    out = []
    for idx, score in zip(I[0], D[0]):
        rec = META[
            int(idx)
        ]  # rec has keys: title, authors, abstract, source_file, chunk_id
        out.append(
            {
                "score": float(score),
                "text": rec.get("abstract", ""),  # text is the chunked abstract
                "meta": rec,  # store full metadata
            }
        )
    return out


def format_context(snippets: List[Dict]) -> str:
    blocks = []
    for s in snippets:
        m = s["meta"]
        header = f"Title: {m.get('title', 'N/A')} | Authors: {m.get('authors', 'N/A')} | Year: {m.get('year', '')}"
        blocks.append(f"[{header}]\n{s['text']}")
    return "\n\n".join(blocks)


# ------------------------------
# Build LLM messages
# ------------------------------
def build_messages(query: str, context: str):
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}, *FEWSHOT]
    msgs.append(
        {
            "role": "user",
            "content": (
                f"Caregiver question: {query}\n\n"
                f"Context (use to ground your answer):\n{context}\n\n"
                f"Remember: {NON_DIAGNOSTIC_PREFACE}"
            ),
        }
    )
    return msgs


# ------------------------------
# Call LLM
# ------------------------------
async def call_llm(messages: List[Dict]) -> str:
    # --- OpenAI ---
    if OPENAI_API_KEY:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json={
                    "model": OPENAI_MODEL,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": MAX_TOKENS,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

    # --- Azure OpenAI ---
    if AZURE_KEY and AZURE_ENDPOINT and AZURE_DEPLOYMENT:
        headers = {"api-key": AZURE_KEY}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{AZURE_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version=2024-06-01",
                headers=headers,
                json={
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": MAX_TOKENS,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

    # --- Ollama local ---
    if OLLAMA_MODEL:
        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        print(f"{response=}")
        print("\n" * 10)
        return response.message.content.strip()

    return "⚠️ No LLM provider configured. Please set OPENAI_API_KEY or OLLAMA_MODEL in .env."


# ------------------------------
# Endpoint
# ------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    flagged, crisis = check_red_flags(req.query)

    hits = retrieve(req.query)
    ctx = format_context(hits)

    msgs = build_messages(req.query, ctx)
    answer = await call_llm(msgs)

    if flagged:
        answer = f"{crisis}\n\n" + answer

    citations = []
    for h in hits:
        m = h["meta"]
        citations.append(
            Citation(
                title=m.get("title"),
                authors=m.get("authors"),
                year=m.get("year"),
                url=m.get("url"),
                source_file=m.get("source_file"),
                chunk_id=m.get("chunk_id"),
                score=h.get("score", 0.0),
            )
        )

    return ChatResponse(answer=answer, citations=citations)
