from flask import Flask, request
from services.predictor import predict

app = Flask(__name__)

@app.route("/")
def home():
    return "Sunscreen Recommendation API"

@app.route("/predict", methods=["POST"])
def predict_api():

    data = request.get_json()

    result = predict(data)

    return result

if __name__ == "__main__":
    app.run(debug=True)