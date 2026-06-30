"""
weather.py
Mengambil UV Index dari Open-Meteo berdasarkan provinsi yang dipilih user.

Alur:
  1. Nama provinsi -> Open-Meteo Geocoding API -> koordinat (lat, lon)
     (https://geocoding-api.open-meteo.com/v1/search)
  2. Koordinat -> Open-Meteo Forecast API -> UV Index harian
     (https://api.open-meteo.com/v1/forecast)
  3. UV Index numerik -> kategori sesuai standar WHO

Koordinat TIDAK di-hardcode -- selalu diambil real-time dari Geocoding API,
supaya tidak bergantung pada data koordinat manual yang berisiko kurang akurat.
"""

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Fallback koordinat representatif tiap provinsi (lat, lon), dipakai HANYA
# kalau Geocoding API gagal/error (timeout, down, atau provinsi tidak
# ditemukan). Sumber: estimasi titik ibu kota/pusat provinsi, BUKAN hasil
# verifikasi presisi -- cukup untuk fallback kasar, bukan sumber utama.
PROVINSI_COORDS_FALLBACK = {
    "Aceh": (5.5483, 95.3238),
    "Sumatera Utara": (3.5952, 98.6722),
    "Sumatera Barat": (-0.9471, 100.4172),
    "Riau": (0.5333, 101.4500),
    "Kepulauan Riau": (0.9167, 104.4500),
    "Jambi": (-1.6101, 103.6131),
    "Sumatera Selatan": (-2.9909, 104.7566),
    "Bengkulu": (-3.7928, 102.2608),
    "Lampung": (-5.4500, 105.2667),
    "Bangka Belitung": (-2.1333, 106.1167),
    "DKI Jakarta": (-6.2088, 106.8456),
    "Jawa Barat": (-6.9175, 107.6191),
    "Jawa Tengah": (-7.1500, 110.1403),
    "DI Yogyakarta": (-7.7956, 110.3695),
    "Jawa Timur": (-7.2504, 112.7688),
    "Banten": (-6.1200, 106.1500),
    "Bali": (-8.4095, 115.1889),
    "Nusa Tenggara Barat": (-8.5833, 116.1167),
    "Nusa Tenggara Timur": (-10.1772, 123.6070),
    "Kalimantan Barat": (-0.0263, 109.3425),
    "Kalimantan Tengah": (-1.6815, 113.3824),
    "Kalimantan Selatan": (-3.3186, 114.5944),
    "Kalimantan Timur": (0.5387, 116.4194),
    "Kalimantan Utara": (3.0731, 116.0414),
    "Sulawesi Utara": (1.4748, 124.8421),
    "Sulawesi Tengah": (-0.8917, 119.8707),
    "Sulawesi Selatan": (-5.1477, 119.4327),
    "Sulawesi Tenggara": (-4.1449, 122.1746),
    "Gorontalo": (0.5435, 123.0568),
    "Sulawesi Barat": (-2.8441, 119.2321),
    "Maluku": (-3.6954, 128.1814),
    "Maluku Utara": (0.7903, 127.3781),
    "Papua": (-2.5337, 140.7181),
    "Papua Barat": (-1.3361, 133.1747),
    "Papua Tengah": (-3.9700, 136.1100),
    "Papua Pegunungan": (-4.0833, 138.9500),
    "Papua Selatan": (-7.3833, 140.4167),
    "Papua Barat Daya": (-1.0833, 131.2500),
}


def get_coordinates(provinsi: str) -> dict:
    """
    Mencari koordinat (lat, lon) sebuah provinsi di Indonesia lewat
    Open-Meteo Geocoding API. Kalau API gagal (timeout, down, atau provinsi
    tidak ditemukan), otomatis fallback ke PROVINSI_COORDS_FALLBACK.

    Catatan: Geocoding API ini awalnya dirancang untuk kota/tempat,
    bukan unit administratif provinsi, jadi hasil pertama yang muncul
    biasanya berupa ibu kota atau kota besar yang representatif untuk
    provinsi tersebut.
    """
    params = {
        "name": provinsi,
        "count": 5,
        "language": "id",
        "format": "json",
        "country": "ID",  # batasi hasil ke Indonesia saja
    }

    try:
        response = requests.get(GEOCODING_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get("results")

        if results:
            lokasi_terpilih = results[0]
            return {
                "nama": lokasi_terpilih.get("name"),
                "latitude": lokasi_terpilih.get("latitude"),
                "longitude": lokasi_terpilih.get("longitude"),
                "admin1": lokasi_terpilih.get("admin1"),
                "sumber": "geocoding_api",
            }
        # Geocoding API jalan tapi tidak ada hasil -> lanjut ke fallback di bawah

    except (requests.RequestException, ValueError, KeyError):
        # Geocoding API gagal (timeout/down/respons aneh) -> lanjut ke fallback di bawah
        pass

    # Fallback: pakai koordinat hardcode kalau provinsi ada di daftar
    if provinsi in PROVINSI_COORDS_FALLBACK:
        lat, lon = PROVINSI_COORDS_FALLBACK[provinsi]
        return {
            "nama": provinsi,
            "latitude": lat,
            "longitude": lon,
            "admin1": provinsi,
            "sumber": "fallback_hardcode",
        }

    raise ValueError(
        f"Lokasi tidak ditemukan: {provinsi!r} (Geocoding API gagal/kosong, "
        f"dan tidak ada di daftar fallback)"
    )


def get_uv_index(latitude: float, longitude: float) -> float:
    """
    Mengambil nilai UV Index maksimum hari ini dari Open-Meteo Forecast API
    berdasarkan koordinat.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "uv_index_max",
        "timezone": "Asia/Jakarta",
    }

    response = requests.get(FORECAST_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    uv_value = data["daily"]["uv_index_max"][0]
    return float(uv_value)


def kategorikan_uv(uv_value: float) -> str:
    """
    Mengkonversi nilai UV Index numerik menjadi kategori sesuai
    standar WHO, dipakai sebagai input ke spf_mapping.tentukan_spf_minimum().
        Rendah        : UV 0 - 2
        Sedang        : UV 3 - 5
        Tinggi        : UV 6 - 7
        SangatTinggi  : UV 8 - 10
        Ekstrem       : UV 11+
    """
    if uv_value < 0:
        raise ValueError(f"Nilai UV index tidak valid: {uv_value}")
    if uv_value <= 2:
        return "Rendah"
    if uv_value <= 5:
        return "Sedang"
    if uv_value <= 7:
        return "Tinggi"
    if uv_value <= 10:
        return "SangatTinggi"
    return "Ekstrem"


def get_uv_kategori(provinsi: str) -> dict:
    """
    Fungsi gabungan: cari koordinat provinsi -> ambil UV index -> kategorikan.
    Mengembalikan dict lengkap supaya nilai mentahnya juga bisa ditampilkan di UI.
    Field "sumber_koordinat" berguna untuk debug/log: "geocoding_api" kalau
    berhasil dari Open-Meteo, atau "fallback_hardcode" kalau API gagal.
    """
    lokasi = get_coordinates(provinsi)
    uv_value = get_uv_index(lokasi["latitude"], lokasi["longitude"])

    return {
        "uv_value": uv_value,
        "uv_kategori": kategorikan_uv(uv_value),
        "lokasi_terdeteksi": lokasi["nama"],
        "latitude": lokasi["latitude"],
        "longitude": lokasi["longitude"],
        "sumber_koordinat": lokasi["sumber"],
    }