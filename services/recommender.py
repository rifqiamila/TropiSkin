"""
recommender.py
Merekomendasikan produk sunscreen dari data/sunscreen.csv berdasarkan
3 kriteria hasil analisis: Tekstur (dari model RF), SPF_Label (dari rule
engine WHO/Fitzpatrick), dan Budget (input user).

Strategi fallback bertingkat -- karena dataset kecil (51 produk), kombinasi
exact 3 kriteria sering kosong. Supaya user TIDAK PERNAH dapat hasil kosong
selama tekstur tsb tersedia di data sama sekali, kriteria dilonggarkan
bertahap sesuai prioritas:

    Level 1: Tekstur + SPF_Label + Budget   (exact match, paling ideal)
    Level 2: Tekstur + SPF_Label            (longgarkan Budget)
    Level 3: Tekstur + Budget               (longgarkan SPF, tapi filter SPF >= minimum)
    Level 4: Tekstur saja                   (longgarkan semua kecuali tekstur)

Tekstur TIDAK PERNAH dilonggarkan karena itu hasil prediksi model ML utama
(alasan inti rekomendasi); SPF_Label dilonggarkan ke "minimal SPF yang
dibutuhkan" dulu sebelum benar-benar diabaikan, supaya proteksi tetap
terjaga walau tidak exact match.
"""

import csv
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sunscreen.csv")

# Urutan kekuatan SPF_Label dari rendah ke tinggi, dipakai untuk Level 3
# (memastikan SPF produk >= SPF minimum yang dibutuhkan, bukan cuma exact match)
SPF_LABEL_ORDER = ["30", "30-50", "50+"]


def _load_products():
    """Membaca seluruh produk dari CSV jadi list of dict."""
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _spf_label_rank(label: str) -> int:
    """Mengembalikan ranking SPF_Label untuk perbandingan >=. Label tak
    dikenal dianggap paling rendah (0) supaya tidak meloloskan produk
    yang sebetulnya di bawah kebutuhan minimum."""
    try:
        return SPF_LABEL_ORDER.index(label)
    except ValueError:
        return 0


def _harga_to_int(harga_str: str) -> int:
    """Konversi string harga seperti 'Rp45,000' jadi integer 45000,
    dipakai untuk sorting termurah saat menampilkan hasil."""
    digits = "".join(ch for ch in harga_str if ch.isdigit())
    return int(digits) if digits else 0


# Deskripsi generik per tekstur, dipakai untuk halaman detail produk karena
# CSV tidak menyimpan kolom deskripsi per produk. Ditulis cukup umum supaya
# masuk akal untuk produk apa pun dengan tekstur tersebut.
DESKRIPSI_PER_TEKSTUR = {
    "Gel": "Sunscreen bertekstur gel yang ringan dan menyegarkan, cepat meresap "
           "tanpa meninggalkan kesan lengket. Cocok untuk kulit berminyak dan "
           "kondisi cuaca lembap karena tidak menyumbat pori-pori.",
    "Lotion": "Sunscreen bertekstur lotion dengan keseimbangan antara kelembapan "
              "dan ringan di kulit. Mudah diratakan dan cocok untuk pemakaian "
              "harian pada berbagai jenis kulit.",
    "Cream": "Sunscreen bertekstur krim yang kaya dan melembapkan, membantu "
             "menjaga kelembapan kulit sepanjang hari. Cocok untuk kulit kering "
             "atau kondisi udara yang gersang.",
    "Serum": "Sunscreen bertekstur serum yang sangat ringan dan cepat meresap, "
             "sering diformulasikan dengan kandungan perawatan tambahan. Cocok "
             "untuk kulit sensitif atau yang menginginkan lapisan tipis tanpa beban.",
    "Stick": "Sunscreen berbentuk stick yang praktis diaplikasikan ulang kapan "
             "saja tanpa perlu sentuhan tangan langsung. Cocok dibawa bepergian "
             "untuk touch-up cepat di tengah aktivitas luar ruangan.",
}

# Placeholder gambar generik per tekstur (bukan foto produk asli, karena CSV
# tidak menyimpan URL gambar). Memakai layanan placeholder berbasis teks
# supaya tetap menampilkan sesuatu yang relevan secara visual di halaman detail.
GAMBAR_PLACEHOLDER_PER_TEKSTUR = {
    "Gel": "https://placehold.co/600x800/A7E8F0/1E3A8A?text=Sunscreen+Gel",
    "Lotion": "https://placehold.co/600x800/BFE3FB/1E3A8A?text=Sunscreen+Lotion",
    "Cream": "https://placehold.co/600x800/FDE9C8/1E3A8A?text=Sunscreen+Cream",
    "Serum": "https://placehold.co/600x800/D8E8FF/1E3A8A?text=Sunscreen+Serum",
    "Stick": "https://placehold.co/600x800/CDEAC0/1E3A8A?text=Sunscreen+Stick",
}

DEFAULT_DESKRIPSI = "Sunscreen yang membantu melindungi kulit dari paparan sinar UV harian."
DEFAULT_GAMBAR = "https://placehold.co/600x800/E5E7EB/1E3A8A?text=Sunscreen"


def get_produk_by_id(id_produk: str):
    """
    Mencari satu produk berdasarkan Id_Produk, dipakai oleh halaman detail
    produk. Mengembalikan None kalau tidak ditemukan, supaya endpoint Flask
    bisa membalas 404 secara eksplisit.

    Dict yang dikembalikan sudah ditambah field 'Deskripsi' dan 'Gambar'
    hasil auto-generate berdasarkan Tekstur, karena kolom tsb tidak ada
    di CSV sumber.
    """
    all_products = _load_products()
    produk = next((p for p in all_products if p["Id_Produk"] == id_produk), None)

    if produk is None:
        return None

    tekstur = produk.get("Tekstur", "")
    produk_lengkap = dict(produk)
    produk_lengkap["Deskripsi"] = DESKRIPSI_PER_TEKSTUR.get(tekstur, DEFAULT_DESKRIPSI)
    produk_lengkap["Gambar"] = GAMBAR_PLACEHOLDER_PER_TEKSTUR.get(tekstur, DEFAULT_GAMBAR)

    return produk_lengkap


def get_rekomendasi(tekstur: str, spf_label: str, budget: str, max_hasil: int = 3) -> dict:
    """
    Mengembalikan daftar produk rekomendasi beserta info level fallback
    yang dipakai, supaya frontend bisa menampilkan keterangan jujur ke user
    (misal: "Tidak ada produk persis sesuai budget, berikut alternatif
    dengan tekstur & SPF yang sama").

    Berbeda dari versi sebelumnya: kalau jumlah produk di satu level masih
    kurang dari max_hasil, sisanya akan diisi dari level fallback berikutnya
    (tanpa duplikat) supaya user selalu dapat sampai max_hasil produk kalau
    datanya tersedia -- bukan berhenti begitu ada 1 produk yang cocok persis.

    Returns:
        {
            "produk": [...list of dict produk, sudah disortir harga termurah...],
            "level_fallback": level tertinggi (paling longgar) yang terpakai,
            "keterangan": str,
        }
    """
    all_products = _load_products()
    produk_tekstur = [p for p in all_products if p["Tekstur"] == tekstur]

    if not produk_tekstur:
        return {
            "produk": [],
            "level_fallback": 0,
            "keterangan": f"Tidak ada produk dengan tekstur '{tekstur}' di database.",
        }

    min_rank = _spf_label_rank(spf_label)

    # Tiap level menghasilkan kandidat list-nya sendiri (urutan dari paling
    # ketat ke paling longgar). Produk digabung berurutan sampai max_hasil
    # terpenuhi, sambil mencatat dipakai_id supaya tidak ada duplikat dan
    # supaya level_fallback yang dilaporkan adalah level TERTINGGI yang
    # benar-benar dipakai untuk melengkapi hasil.
    level_candidates = [
        (1, "Produk sesuai tekstur, proteksi SPF, dan budget yang kamu pilih.",
         [p for p in produk_tekstur if p["SPF_Label"] == spf_label and p["Budget"] == budget]),
        (2, "Produk sesuai tekstur & proteksi SPF (sebagian di luar rentang budget pilihanmu).",
         [p for p in produk_tekstur if p["SPF_Label"] == spf_label]),
        (3, "Produk sesuai tekstur & budget, dengan proteksi SPF setara atau lebih tinggi dari kebutuhanmu.",
         [p for p in produk_tekstur if p["Budget"] == budget and _spf_label_rank(p["SPF_Label"]) >= min_rank]),
        (4, "Sebagian produk di luar budget/SPF persis, berikut pilihan lain dengan tekstur yang sama.",
         [p for p in produk_tekstur if _spf_label_rank(p["SPF_Label"]) >= min_rank] or produk_tekstur),
    ]

    hasil = []
    dipakai_id = set()
    level_terpakai = 1
    keterangan_terpakai = level_candidates[0][1]

    for level, ket, kandidat in level_candidates:
        if len(hasil) >= max_hasil:
            break

        kandidat_baru = [p for p in kandidat if p["Id_Produk"] not in dipakai_id]
        if not kandidat_baru:
            continue

        # kalau level ini menyumbang produk tambahan, level_fallback &
        # keterangan ikut naik ke level ini (level tertinggi yang dipakai)
        if level > 1 and kandidat_baru:
            level_terpakai = level
            keterangan_terpakai = ket

        for p in sorted(kandidat_baru, key=lambda x: _harga_to_int(x["Harga"])):
            if len(hasil) >= max_hasil:
                break
            hasil.append(p)
            dipakai_id.add(p["Id_Produk"])

    hasil_sorted = sorted(hasil, key=lambda p: _harga_to_int(p["Harga"]))

    return {
        "produk": hasil_sorted[:max_hasil],
        "level_fallback": level_terpakai,
        "keterangan": keterangan_terpakai,
    }