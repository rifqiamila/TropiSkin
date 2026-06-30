from flask import Flask, request, render_template, jsonify
from services.predictor import predict
from services.spf_mapping import tentukan_spf_minimum
from services.weather import get_uv_kategori
from services.recommender import get_rekomendasi, get_produk_by_id

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analysis")
def analysis():
    return render_template("formAnalisis.html")


@app.route("/loading")
def loading():
    return render_template("loading.html")


@app.route("/hasil")
def hasil():
    return render_template("hasilAnalisis.html")


@app.route("/rekomendasi")
def rekomendasi():
    return render_template("rekomendasi.html")


@app.route("/detail-produk")
def detail_produk():
    return render_template("detailProduk.html")


@app.route("/predict", methods=["POST"])
def predict_api():
    data = request.get_json()

    # 5 fitur utama -> masuk ke model Random Forest
    main_features = {
        "Jenis_Kulit": data.get("Jenis_Kulit"),
        "Kondisi_Kulit": data.get("Kondisi_Kulit"),
        "Paparan_Matahari": data.get("Paparan_Matahari"),
        "Kelembapan": data.get("Kelembapan"),
        "Budget": data.get("Budget"),
    }

    # Lokasi & Fitzpatrick -> tidak masuk model, dipakai untuk SPF & rekomendasi
    lokasi = data.get("Lokasi")
    fitzpatrick = data.get("Fitzpatrick", "Medium")

    if not lokasi:
        return jsonify({"error": "Lokasi wajib diisi."}), 400

    # 1. Prediksi tekstur dari model Random Forest
    hasil_prediksi = predict(main_features)

    # 2. Ambil UV index real-time dari Open-Meteo berdasarkan provinsi
    try:
        uv_info = get_uv_kategori(lokasi)
    except Exception as e:
        return jsonify({"error": f"Gagal mengambil data UV index: {str(e)}"}), 502

    # 3. Tentukan SPF_Label lewat rule engine (WHO + override Fitzpatrick)
    spf_label = tentukan_spf_minimum(
        paparan=main_features["Paparan_Matahari"],
        uv_kategori=uv_info["uv_kategori"],
        fitzpatrick=fitzpatrick,
    )

    result = {
        "tekstur": hasil_prediksi["prediction"],
        "confidence": hasil_prediksi["confidence"],
        "spf_label": spf_label,
        "uv_value": uv_info["uv_value"],
        "uv_kategori": uv_info["uv_kategori"],
        "input": {
            **main_features,
            "Lokasi": lokasi,
            "Fitzpatrick": fitzpatrick,
        },
    }

    return jsonify(result)


@app.route("/recommend", methods=["POST"])
def recommend_api():
    """
    Menerima hasil analisis (tekstur, spf_label, budget) dari frontend
    (biasanya dikirim dari localStorage hasil /predict sebelumnya), lalu
    mengembalikan daftar produk sunscreen yang cocok dari data/sunscreen.csv.

    Body JSON yang diharapkan:
        {
            "tekstur": "Stick",
            "spf_label": "30-50",
            "budget": "Under 50K"
        }
    """
    data = request.get_json()

    tekstur = data.get("tekstur")
    spf_label = data.get("spf_label")
    budget = data.get("budget")

    if not tekstur or not spf_label or not budget:
        return jsonify({
            "error": "Field 'tekstur', 'spf_label', dan 'budget' wajib diisi."
        }), 400

    hasil = get_rekomendasi(tekstur, spf_label, budget)

    return jsonify(hasil)


@app.route("/produk/<id_produk>", methods=["GET"])
def produk_api(id_produk):
    """
    Mengembalikan detail satu produk berdasarkan Id_Produk (misal STK-01),
    dipakai oleh detailProduk.html lewat fetch setelah ID diambil dari
    localStorage.
    """
    produk = get_produk_by_id(id_produk)

    if produk is None:
        return jsonify({"error": f"Produk dengan ID '{id_produk}' tidak ditemukan."}), 404

    return jsonify(produk)


if __name__ == "__main__":
    app.run(debug=True)