"""
Modul RAG — mengubah knowledge base menjadi embedding, menyimpannya ke FAISS,
melakukan semantic search, lalu menghasilkan jawaban menggunakan LLM.

Alur ini serupa dengan yang sudah dibangun di Assignment 3 (Semantic Search &
LLM Application) dan Sesi 11 (Building a Simple RAG System) — di assignment ini,
alur tersebut dibungkus menjadi fungsi yang dipanggil oleh router.py.
"""

import os
import pandas as pd
import numpy as np
import faiss
from dotenv import load_dotenv
from google import genai  
from google.genai import types


load_dotenv() 

_client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        api_version="v1beta",
        timeout=30_000,
        retry_options=types.HttpRetryOptions(attempts=3), # Ubah dari 1 jadi 3
    ),
)
KNOWLEDGE_BASE_PATH = "data/it_helpdesk_knowledge_base.csv"
EMBEDDING_MODEL = "gemini-embedding-2"
LLM_MODEL = "gemini-flash-lite-latest"

# 🔧 TODO: muat knowledge base dan bangun index FAISS saat aplikasi startup
# (bukan di setiap request), agar lebih efisien. Pertimbangkan menggunakan
# FastAPI startup event atau lazy-loading dengan cache sederhana.

_index = None
_documents = None
_df = None


def _get_embedding(text: str):
    result = _client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


def build_index():
    """
        # TODO: implementasikan pembangunan index FAISS dari knowledge base CSV.
        # Referensi: starter_notebook_semantic_search.ipynb dari Assignment 3,
        # Section 1-4 (load data -> unit retrievable -> embedding -> simpan ke FAISS).
    """

    global _index, _documents, _df

    print(f"[rag] Memuat knowledge base: {KNOWLEDGE_BASE_PATH}")
    _df = pd.read_csv(KNOWLEDGE_BASE_PATH)
    print(f"[rag] Berhasil memuat {len(_df)} FAQ.")

    # Susun dokumen retrievable
    _documents = []
    for _, row in _df.iterrows():
        text_for_embedding = (
            f"Kategori: {row['category']}\n"
            f"Pertanyaan: {row['question']}\n"
            f"Jawaban: {row['answer']}"
        )
        _documents.append({
            "faq_id": int(row["faq_id"]),
            "category": str(row["category"]),
            "question": str(row["question"]),
            "answer": str(row["answer"]),
            "text": text_for_embedding,
        })

    # Buat embedding untuk semua dokumen
    print(f"[rag] Membuat embedding untuk {len(_documents)} dokumen ...")
    embeddings = np.array(
        [_get_embedding(doc["text"]) for doc in _documents],
        dtype="float32",
    )
    print(f"[rag] Matriks embedding: {embeddings.shape} (n_docs x dim)")

    # Normalisasi L2 
    faiss.normalize_L2(embeddings)

    # Bangun FAISS index
    dim = embeddings.shape[1]
    _index = faiss.IndexFlatIP(dim)
    _index.add(embeddings)
    print(f"[rag] FAISS index siap: {_index.ntotal} vektor, dimensi {dim}.")

    return _index


def semantic_search(query: str, top_k: int = 3):
    if _index is None or _documents is None:
        raise RuntimeError(
            "FAISS index belum dibangun. Pastikan build_index() dipanggil "
            "saat startup sebelum semantic_search() digunakan."
        )

    if not query or not query.strip():
        return []

    # Embed query & normalisasi
    query_vec = np.array([_get_embedding(query)], dtype="float32")
    faiss.normalize_L2(query_vec)

    # Cari top_k dokumen paling mirip
    scores, indices = _index.search(query_vec, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        doc = dict(_documents[idx])
        doc["score"] = float(score)
        results.append(doc)

    return results


async def answer_from_knowledge_base(query: str) -> str:
    # 1. Retrieval
    retrieved_docs = semantic_search(query, top_k=3)

    if not retrieved_docs:
        return (
            "Maaf, saya tidak menemukan informasi yang relevan dengan pertanyaan Anda "
            "di knowledge base. Silakan hubungi HR atau IT Support untuk bantuan lebih lanjut."
        )

    # 2. Susun Context dari dokumen hasil retrieval 
    context_blocks = []
    for i, doc in enumerate(retrieved_docs, 1):
        context_blocks.append(
            f"[Dokumen {i}] (Kategori: {doc['category']})\n"
            f"Pertanyaan: {doc['question']}\n"
            f"Jawaban: {doc['answer']}"
        )
    context_text = "\n\n".join(context_blocks)

    # 3. Susun prompt (Persona / Task / Context / Format) 
    prompt = f"""### PERSONA
            Anda adalah "IT Helpdesk Assistant", asisten virtual internal perusahaan yang
            ramah, profesional, dan ringkas. Anda membantu karyawan menjawab pertanyaan
            seputar kebijakan HR, IT, dan operasional perusahaan.

            ### TASK
            Jawab pertanyaan user HANYA berdasarkan informasi yang ada pada CONTEXT di bawah.
            Jangan mengarang jawaban, jangan menambahkan informasi di luar context. Jika
            context tidak cukup untuk menjawab, katakan dengan jujur bahwa informasi tidak
            tersedia dan sarankan user menghubungi HR/IT Support.

            ### CONTEXT
            {context_text}

            ### FORMAT
            - Tulis dalam Bahasa Indonesia yang jelas dan mudah dipahami.
            - Panjang jawaban 2-5 kalimat (ringkas, tidak bertele-tele).
            - Sertakan langkah-langkah konkret jika pertanyaan bersifat prosedural.
            - Jangan menyalin pertanyaan dari context; langsung jawab inti pertanyaannya.
            - Jangan menyebut "Dokumen 1/2/3" atau "context" pada jawaban akhir.

            ### PERTANYAAN USER
            {query}

            ### JAWABAN
            """

    # 4. Panggil LLM 
    try:
        response = _client.models.generate_content(
            model=LLM_MODEL,           
            contents=prompt,
        )
        answer = (response.text or "").strip()

        # Guard
        if not answer:
            return (
                "Maaf, saya tidak dapat menyusun jawaban saat ini. "
                "Silakan coba lagi atau hubungi IT Support."
            )

        return answer

    except Exception:
        return "Maaf, terjadi kendala teknis. Silakan coba lagi."