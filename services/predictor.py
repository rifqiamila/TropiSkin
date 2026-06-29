import joblib
import json
import pandas as pd

# Load model sekali saat aplikasi dijalankan
rf = joblib.load("models/model_rf.pkl")
encoders = joblib.load("models/encoders.pkl")

with open("models/model_meta.json", encoding="utf-8") as f:
    meta = json.load(f)

FEATURES = meta["features"]
TARGET = meta["target"]


def predict(sample):
    """
    sample berupa dictionary, contoh:
    {
        "Jenis_Kulit": "Berminyak",
        "Kondisi_Kulit": "Berjerawat",
        "Paparan_Matahari": "Tinggi",
        "Kelembapan": "Sedang",
        "Budget": "Semua"
    }
    """

    row = pd.DataFrame([sample])

    # Encode semua fitur
    for col in FEATURES:
        row[col] = encoders[col].transform(row[col])

    # Prediksi
    pred_enc = rf.predict(row[FEATURES])[0]

    # Confidence
    probabilities = rf.predict_proba(row[FEATURES])[0]

    # Decode hasil
    prediction = encoders[TARGET].inverse_transform([pred_enc])[0]

    return {
        "prediction": prediction,
        "confidence": round(float(max(probabilities)), 4)
    }