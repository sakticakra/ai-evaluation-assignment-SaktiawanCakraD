"""
Modul Tools — fungsi "aksi" yang dipanggil router ketika intent
BUKAN pertanyaan informasi/kebijakan, melainkan permintaan spesifik
yang butuh pengecekan data langsung (bukan retrieval semantik).
"""

import pandas as pd

MOCK_TICKETS_PATH = "data/mock_tickets.csv"


def get_ticket_status(ticket_id: str) -> str:
    """Cari status tiket berdasarkan ticket_id pada mock_tickets.csv.

    Mengembalikan pesan informatif jika tiket tidak ditemukan (tidak raise).
    """
    try:
        df = pd.read_csv(MOCK_TICKETS_PATH)
    except FileNotFoundError:
        return "Data tiket tidak tersedia saat ini. Silakan hubungi IT Support."

    ticket_id = (ticket_id or "").strip().upper()
    match = df[df["ticket_id"] == ticket_id]

    if match.empty:
        return (
            f"Tiket {ticket_id} tidak ditemukan. "
            "Pastikan nomor tiket sudah benar (format: TICKET-XXXX)."
        )

    row = match.iloc[0]
    return (
        f"Tiket {row['ticket_id']} - {row['subject']}\n"
        f"Kategori : {row['category']}\n"
        f"Status   : {row['status']}\n"
        f"Update   : {row['last_update']}"
    )