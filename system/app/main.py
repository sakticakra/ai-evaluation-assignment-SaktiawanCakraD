"""
Entry point aplikasi FastAPI — IT Helpdesk Assistant.

Alur endpoint utama:
  1. Menerima pertanyaan/permintaan dari user
  2. Meneruskan ke router (router.py) untuk menentukan intent
  3. Router memanggil RAG (rag.py) atau tool (tools.py) sesuai intent
  4. Mengembalikan response terstruktur ke client
"""

from fastapi import FastAPI
from pydantic import BaseModel

from app.router import handle_query
from app.rag import build_index

app = FastAPI(title="IT Helpdesk Assistant API")


class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    status: str
    intent: str
    data: str


@app.on_event("startup")
async def startup():
    """Bangun FAISS index sekali saat aplikasi start (bukan per request)."""
    build_index()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """Endpoint utama: terima query → routing → response terstruktur."""
    try:
        result = await handle_query(request.query)
        return AskResponse(**result)
    except Exception as e:
        # Defensive layer: exception tak terduga dari router/LLM
        print(f"[main] unexpected error: {e}")
        return AskResponse(
            status="error",
            intent="unknown",
            data="Maaf, terjadi kesalahan pada server. Silakan coba lagi.",
        )