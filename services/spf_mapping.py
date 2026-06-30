"""
spf_mapping.py
Rule-based (bukan ML) untuk menentukan rekomendasi SPF minimum.
Sumber: WHO UV Index Guidelines (Step 1) + Override Fitzpatrick (Step 2),
divalidasi dr. Nisrina Alya Khoirunnisa Toha, 14 Juni 2026.

Hasil akhir berupa SPF_Label: "30" | "30-50" | "50+"
Tidak ada pencocokan ke produk di sini -- itu urusan services/recommendation.py
"""

# =====================================================================
# STEP 1 — BASE SPF: Paparan Matahari x UV Index (WHO)
# Tier "50+" murni direservasi untuk UV Sangat Tinggi/Ekstrem (8+),
# karena di situ risiko tinggi terlepas dari durasi paparan.
# Tier "30-50" dipakai untuk kasus yang naik dari "30" akibat durasi
# paparan lama pada UV Sedang/Tinggi (bukan karena UV-nya sendiri ekstrem).
# =====================================================================
BASE_SPF_TABLE = {
    ("Rendah", "Rendah"):       "30",
    ("Rendah", "Sedang"):       "30",
    ("Rendah", "Tinggi"):       "30",
    ("Rendah", "SangatTinggi"): "50+",
    ("Rendah", "Ekstrem"):      "50+",

    ("Sedang", "Rendah"):       "30",
    ("Sedang", "Sedang"):       "30",
    ("Sedang", "Tinggi"):       "30-50",   # naik dari 30 (durasi sedang + UV tinggi)
    ("Sedang", "SangatTinggi"): "50+",
    ("Sedang", "Ekstrem"):      "50+",

    ("Tinggi", "Rendah"):       "30",
    ("Tinggi", "Sedang"):       "30-50",   # naik dari 30 (durasi lama + UV sedang)
    ("Tinggi", "Tinggi"):       "30-50",   # naik dari 30 (durasi lama + UV tinggi)
    ("Tinggi", "SangatTinggi"): "50+",
    ("Tinggi", "Ekstrem"):      "50+",
}

# Urutan tier dari rendah ke tinggi -- dipakai untuk perbandingan/override
TIER_URUTAN = ["30", "30-50", "50+"]

# Kategori UV yang termasuk "rendah-menengah" untuk keperluan override
# Dark skin di Step 2. Di atas ini (SangatTinggi/Ekstrem), override TIDAK
# berlaku -- siapa pun tetap wajib SPF 50+.
UV_RENDAH_HINGGA_TINGGI = {"Rendah", "Sedang", "Tinggi"}


# =====================================================================
# STEP 2 — OVERRIDE FITZPATRICK (diterapkan setelah Step 1)
# =====================================================================
def _terapkan_override_fitzpatrick(base_tier, fitzpatrick: str, uv_kategori: str):
    """
    fitzpatrick: "Fair" (I-II) | "Medium" (III-IV) | "Dark" (V-VI)
    """
    if fitzpatrick == "Fair":
        # Kulit fair: kalau base belum di tier tertinggi, paksa naik ke 50+
        if base_tier != "50+":
            return "50+"
        return base_tier

    if fitzpatrick == "Medium":
        # Tidak ada override, ikuti hasil Step 1 apa adanya
        return base_tier

    if fitzpatrick == "Dark":
        # Kalau base BUKAN tier terendah ("30") DAN UV masih <= Tinggi
        # (bukan SangatTinggi/Ekstrem) -> boleh diturunkan ke tier "30".
        # Di atas UV Tinggi, override tidak berlaku (tetap ikut base).
        if base_tier != "30" and uv_kategori in UV_RENDAH_HINGGA_TINGGI:
            return "30"
        return base_tier

    raise ValueError(f"Kategori Fitzpatrick tidak dikenal: {fitzpatrick!r}")


# =====================================================================
# FUNGSI UTAMA — hitung tier SPF yang dibutuhkan
# =====================================================================
def tentukan_spf_minimum(paparan: str, uv_kategori: str, fitzpatrick: str = "Medium") -> str:
    """
    Mengembalikan salah satu tier (SPF_Label): "30" | "30-50" | "50+"

    paparan       : "Rendah" | "Sedang" | "Tinggi"
    uv_kategori   : "Rendah" | "Sedang" | "Tinggi" | "SangatTinggi" | "Ekstrem"
    fitzpatrick   : "Fair" | "Medium" | "Dark" (default "Medium" jika user
                     tidak mengisi field opsional di form)
    """
    key = (paparan, uv_kategori)
    if key not in BASE_SPF_TABLE:
        raise ValueError(f"Kombinasi paparan/UV tidak dikenal: {key}")

    base = BASE_SPF_TABLE[key]
    return _terapkan_override_fitzpatrick(base, fitzpatrick, uv_kategori)