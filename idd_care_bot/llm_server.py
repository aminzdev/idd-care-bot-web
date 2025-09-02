from functools import lru_cache
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

from .prompts import FEWSHOT, SYSTEM_PROMPT
from .safety import NON_DIAGNOSTIC_PREFACE, check_red_flags

# Load environment
load_dotenv()
INDEX_DIR = os.getenv("INDEX_DIR", "storage")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
)
TOP_K = int(os.getenv("TOP_K", 5))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 700))

# LLM provider config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
API_URL = os.getenv("API_URL", "http://0.0.0.0:8000/chat")

# FastAPI app
app = FastAPI(title="IDDCareBot API")


# Load FAISS + metadata
@lru_cache(maxsize=1)
def get_embedder():
    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_index():
    return faiss.read_index(os.path.join(INDEX_DIR, "index.faiss"))


@lru_cache(maxsize=1)
def get_meta():
    with open(os.path.join(INDEX_DIR, "meta.json"), "r", encoding="utf-8") as f:
        return json.load(f)


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
    emb = get_embedder().encode([text])  # returns (1, dim)
    return emb[0]


# Extend smalltalk patterns
smalltalk_patterns = {
    "greetings": {"hi", "hello", "hey", "good morning", "good evening"},
    "gratitude": {"thanks", "thank you", "thx"},
    "farewell": {"bye", "goodbye", "see you", "take care"},
    "how_are_you": {"how are you", "how’s it going", "how are u"},
    "capabilities": {
        "what can you do",
        "how can you help",
        "who are you",
        "what are you",
        "what is your role",
        "help",
        "i need help",
        "support",
        "assist me",
    },
}


def handle_smalltalk(user_input: str):
    text = user_input.lower().strip()

    if any(text.startswith(g) for g in smalltalk_patterns["greetings"]):
        return {
            "answer": "👋 Hi there! I’m glad you reached out. How can I support you today?",
            "citations": [],
        }

    if any(g in text for g in smalltalk_patterns["gratitude"]):
        return {
            "answer": "💜 You’re very welcome. Caring for a child with IDD is a big job—you’re doing great.",
            "citations": [],
        }

    if any(text.startswith(g) for g in smalltalk_patterns["farewell"]):
        return {
            "answer": "👋 Take care! Remember, you can come back anytime with questions or just to talk.",
            "citations": [],
        }

    if any(g in text for g in smalltalk_patterns["how_are_you"]):
        return {
            "answer": "😊 Thanks for asking! I’m here and ready to help with anything about caregiving or resources.",
            "citations": [],
        }

    if any(text == g or g in text for g in smalltalk_patterns["capabilities"]):
        return {
            "answer": (
                "🤖 I’m **IDDCareBot**, here to support caregivers of children with Down Syndrome and other intellectual or "
                "developmental disabilities (IDD). I can:\n"
                "- Share caregiver-friendly tips and strategies (not medical advice).\n"
                "- Explain information from research in plain language.\n"
                "- Suggest resources you can discuss with your child’s providers.\n\n"
                "How can I help you today?"
            ),
            "citations": [],
        }

    return None


def retrieve(query: str, top_k: int = TOP_K) -> List[Dict]:
    q_emb = embed(query)  # must match ingest.py embedding model
    q_emb = np.array(q_emb, dtype="float32")

    # Ensure correct shape: (1, dim)
    if q_emb.ndim == 1:
        q_emb = q_emb[np.newaxis, :]

    D, I = get_index().search(q_emb, top_k)

    out = []
    for idx, score in zip(I[0], D[0]):
        rec = get_meta()[
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

    # --- Ollama local ---
    if OLLAMA_MODEL:
        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        return response.message.content.strip()

    return "⚠️ No LLM provider configured. Please set OPENAI_API_KEY or OLLAMA_MODEL in .env."


# ------------------------------
# Endpoint
# ------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    flagged, crisis = check_red_flags(req.query)

    if res := handle_smalltalk(req.query):
        return ChatResponse(**res)

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
