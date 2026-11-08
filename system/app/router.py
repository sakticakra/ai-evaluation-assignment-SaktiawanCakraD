"""
Router — menentukan apakah query user butuh RAG (informasi/kebijakan)
atau tool call (aksi spesifik, misal cek status tiket).
"""

import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

from app.rag import answer_from_knowledge_base
from app.tools import get_ticket_status

_client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        api_version="v1beta",
        timeout=30_000,
        retry_options=types.HttpRetryOptions(attempts=3), # Ubah dari 1 jadi 3
    ),
)

LLM_MODEL = "gemini-flash-lite-latest"

# Format ticket_id: TICKET-XXXX (4 digit)
TICKET_ID_PATTERN = re.compile(r"TICKET-\d{4}", re.IGNORECASE)


async def detect_intent(query: str) -> str:
    """LLM-based intent detection → 'faq' | 'ticket_status' | 'unknown'."""
    prompt = f"""Klasifikasikan pertanyaan berikut ke dalam salah satu kategori:
- "faq": pertanyaan tentang kebijakan/prosedur/informasi internal perusahaan (HR, IT, operasional)
- "ticket_status": permintaan cek status tiket IT tertentu
- "greeting": sapaan umum seperti halo, pagi, siang, dll.
- "unknown": pertanyaan di luar kedua topik di atas (termasuk topik umum di luar perusahaan)

Jawab HANYA dengan satu kata: faq, ticket_status, greeting, atau unknown.

Pertanyaan: {query}
Kategori:"""

    try:
        response = _client.models.generate_content(model=LLM_MODEL, contents=prompt)
        intent = (response.text or "").strip().lower()
    except Exception as e:
        print(f"[router] intent error: {e}")
        return "unknown"

    # Normalisasi (LLM kadang balas "ticket_status." atau "FAQ")
    if "ticket" in intent:
        return "ticket_status"
    if "faq" in intent:
        return "faq"
    if "greeting" in intent:
        return "greeting"
    return "unknown"


def extract_ticket_id(query: str) -> str | None:
    """Regex TICKET-XXXX. Return None jika tidak ada match."""
    match = TICKET_ID_PATTERN.search(query)
    return match.group(0).upper() if match else None


async def handle_query(query: str) -> dict:
    """Titik masuk utama: intent detection → routing → response."""
    intent = await detect_intent(query)

    if intent == "ticket_status":
        ticket_id = extract_ticket_id(query)
        if not ticket_id:
            return {
                "status": "error",
                "intent": "ticket_status",
                "data": "Mohon sertakan nomor tiket dengan format TICKET-XXXX (contoh: TICKET-0001).",
            }
        return {
            "status": "success",
            "intent": "ticket_status",
            "data": get_ticket_status(ticket_id),
        }

    if intent == "faq":
        return {
            "status": "success",
            "intent": "faq",
            "data": await answer_from_knowledge_base(query),
        }

    if intent == "greeting":
        return {
            "status": "success",
            "intent": "greeting",
            "data": "Halo! Saya asisten IT Helpdesk. Ada yang bisa saya bantu terkait kebijakan HR/IT atau status tiket Anda?",
        }

    return {
        "status": "error",
        "intent": "unknown",
        "data": (
            "Maaf, saya tidak memahami permintaan Anda. Coba tanyakan seputar "
            "kebijakan HR/IT perusahaan, atau cek status tiket (format: TICKET-XXXX)."
        ),
    }