"""
MCP Server for Air Quality Reasoning System
============================================
4 Tools backed by trained ONNX + Keras models.
Rebuilt from deep analysis of training notebooks & ONNX inspection.
"""
import os
import numpy as np
import tensorflow as tf
from mcp.server.fastmcp import FastMCP
from PIL import Image
import onnxruntime as ort

mcp = FastMCP("Air Quality Reasoning System")

# Model Paths
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
AQI_LSTM_KERAS_PATH   = os.path.join(MODELS_DIR, "aqi_lstm_saved_model.keras")
EMISSION_ONNX_PATH    = os.path.join(MODELS_DIR, "emission_model_final.onnx")
HEALTH_ONNX_PATH      = os.path.join(MODELS_DIR, "best_air_quality_model.onnx")
CNN_ONNX_PATH         = os.path.join(MODELS_DIR, "AQI CNN", "aqi_cnn.onnx")

EMISSION_SCALER = {
    "mean": np.array([3.369630, 14.490000, 148995.708000, 59.448818, 2.491924,
                      14.935772, 50.144758, 10.027946, 1000.199354]),
    "scale": np.array([1.495677, 8.584339, 87068.385915, 34.437175, 1.446130,
                       14.432900, 28.787763, 5.735533, 28.789590]),
}
EMISSION_CAT_ENCODINGS = {
    "Vehicle Type":       {"Bus": 0, "Car": 1, "Motorcycle": 2, "Truck": 3},
    "Fuel Type":          {"Diesel": 0, "Electric": 1, "Gasoline": 2, "Hybrid": 3},
    "Road Type":          {"City": 0, "Highway": 1, "Rural": 2},
    "Traffic Conditions": {"Free flow": 0, "Heavy": 1, "Moderate": 2},
}
EMISSION_CLASSES = ["High", "Low", "Medium"]

HEALTH_SCALER = {
    "mean": np.array([248.4385, 148.6550, 100.2237, 102.2934, 49.4568,
                      149.3124, 14.9755, 54.7769, 9.9892, 4.9246, 820.2230]),
    "scale": np.array([144.7652, 85.6911, 58.0916, 57.7082, 28.5279,
                       86.5268, 14.4818, 26.0185, 5.7765, 120.2189, 957.0258]),
}
HEALTH_CLASSES = ["Very Low", "Low", "Moderate", "High", "Very High"]

LSTM_SCALER = {
    "min":   np.array([0.03, 1.0, 0.01, 0.1, 0.0, 0.01, 0.0, 0.01, 0.02, 0.0, 0.0, 0.0, 18.0]),
    "range": np.array([999.96, 999.0, 419.77, 266.63, 408.25, 485.51, 31.62, 199.92, 219.76, 120.08, 198.05, 261.95, 742.0]),
}
AQI_TARGET_MIN   = 18.0
AQI_TARGET_RANGE = 742.0

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406])
IMAGENET_STD  = np.array([0.229, 0.224, 0.225])
CNN_CLASSES = ["Good", "Moderate", "Unhealthy for Sensitive Groups", "Unhealthy", "Very Unhealthy", "Severe"]
aqi_model        = None
emission_session = None
health_session   = None
cnn_session      = None

def ensure_models_loaded():
    global aqi_model, emission_session, health_session, cnn_session
    if all([aqi_model, emission_session, health_session, cnn_session]):
        return
    try:
        print("Loading models...")
        if aqi_model is None:
            aqi_model = tf.keras.models.load_model(AQI_LSTM_KERAS_PATH)
        if emission_session is None:
            emission_session = ort.InferenceSession(EMISSION_ONNX_PATH)
        if health_session is None:
            health_session = ort.InferenceSession(HEALTH_ONNX_PATH)
        if cnn_session is None:
            cnn_session = ort.InferenceSession(CNN_ONNX_PATH)
        print("All models loaded.")
    except Exception as e:
        print(f"Error loading models: {e}")
        raise

@mcp.tool()
def predict_aqi_forecast(pm25: float, pm10: float, no: float, no2: float,
                         nox: float, nh3: float, co: float, so2: float,
                         o3: float, benzene: float, toluene: float,
                         xylene: float) -> dict:
    """
    Predicts the next 4 hours of AQI based on current pollutant levels.
    Requires 12 pollutant features.
    """
    ensure_models_loaded()

    current_aqi = max(pm25 * 1.5, pm10, no2 * 2.0, so2 * 0.5, o3 * 1.2, co * 10.0)
    current_aqi = min(500, max(0, current_aqi))

    raw = np.array([pm25, pm10, no, no2, nox, nh3, co, so2, o3, benzene, toluene, xylene, current_aqi])
    scaled = (raw - LSTM_SCALER["min"]) / LSTM_SCALER["range"]
    scaled = np.clip(scaled, 0, 1)

    seq = np.tile(scaled.reshape(1, 1, 13), (1, 24, 1)).astype(np.float32)

    prediction = aqi_model.predict(seq, verbose=0)

    forecast = prediction[0] * AQI_TARGET_RANGE + AQI_TARGET_MIN

    return {
        "estimated_current_aqi": round(current_aqi, 1),
        "forecast_1h": round(float(forecast[0]), 1),
        "forecast_2h": round(float(forecast[1]), 1),
        "forecast_3h": round(float(forecast[2]), 1),
        "forecast_4h": round(float(forecast[3]), 1),
        "unit": "AQI Index",
        "note": "Single-snapshot broadcast; 24h history recommended for higher accuracy."
    }

@mcp.tool()
def classify_pollution_image(image_path: str) -> str:
    """
    Analyzes an urban image for visual pollution signatures (ONNX).
    """
    ensure_models_loaded()
    try:
        img = Image.open(image_path).convert('RGB').resize((224, 224))
        img_array = np.array(img).astype('float32') / 255.0

        img_array = (img_array - IMAGENET_MEAN) / IMAGENET_STD

        img_array = np.transpose(img_array, (2, 0, 1)).astype(np.float32)
        img_array = np.expand_dims(img_array, axis=0)  # (1, 3, 224, 224)

        prediction = cnn_session.run(None, {"image": img_array})[0]
        predicted_idx = int(np.argmax(prediction[0]))

        return f"Image AQI Classification: {CNN_CLASSES[predicted_idx]}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def predict_vehicle_emission(engine_size: float, mileage: float, speed: float,
                              vehicle_type: str = "Car", fuel_type: str = "Gasoline",
                              road_type: str = "Highway", traffic: str = "Moderate",
                              age: int = 5, acceleration: float = 2.5,
                              temperature: float = 25.0, humidity: float = 50.0,
                              wind_speed: float = 10.0, air_pressure: float = 1013.0) -> str:
    """
    Predicts vehicle emission level (Low/Medium/High) using ONNX model.
    Note: Standardized for 3 primary numerical features.
    """
    ensure_models_loaded()

    numeric_raw = np.array([engine_size, age, mileage, speed, acceleration,
                            temperature, humidity, wind_speed, air_pressure])
    numeric_scaled = ((numeric_raw - EMISSION_SCALER["mean"]) / EMISSION_SCALER["scale"]).reshape(1, -1).astype(np.float32)
    vt = EMISSION_CAT_ENCODINGS["Vehicle Type"].get(vehicle_type, 1)
    ft = EMISSION_CAT_ENCODINGS["Fuel Type"].get(fuel_type, 2)
    rt = EMISSION_CAT_ENCODINGS["Road Type"].get(road_type, 1)
    tc = EMISSION_CAT_ENCODINGS["Traffic Conditions"].get(traffic, 2)

    feed = {
        "numeric_input":            numeric_scaled,
        "Vehicle Type_input":       np.array([[vt]], dtype=np.int64),
        "Fuel Type_input":          np.array([[ft]], dtype=np.int64),
        "Road Type_input":          np.array([[rt]], dtype=np.int64),
        "Traffic Conditions_input": np.array([[tc]], dtype=np.int64),
    }

    prediction = emission_session.run(None, feed)[0]
    predicted_idx = int(np.argmax(prediction[0]))
    level = EMISSION_CLASSES[predicted_idx]

    return f"Emission Level: {level}"

@mcp.tool()
def estimate_health_risk(aqi: float, pm10: float, pm25: float,
                         no2: float, so2: float, o3: float,
                         temperature: float, humidity: float,
                         wind_speed: float) -> dict:
    """
    Estimates health impact score and category using Multi-Task ONNX model.
    Accepts 9 environmental features and calculates 2 engineered features internally.
    """
    ensure_models_loaded()

    pm_ratio = pm25 / (pm10 + 1e-6)
    no2_o3_interaction = no2 * o3

    raw = np.array([aqi, pm10, pm25, no2, so2, o3, temperature, humidity, wind_speed,
                    pm_ratio, no2_o3_interaction])

    scaled = ((raw - HEALTH_SCALER["mean"]) / HEALTH_SCALER["scale"]).reshape(1, -1).astype(np.float32)

    outputs = health_session.run(None, {"input_features": scaled})
    risk_score = float(outputs[0][0][0])
    risk_score_pct = max(0.0, min(100.0, risk_score * 100))  # Convert 0-1 range to percentage
    risk_class_idx = int(np.argmax(outputs[1][0]))

    return {
        "health_impact_score": round(risk_score_pct, 2),
        "risk_category": HEALTH_CLASSES[risk_class_idx],
        "recommendation": "⚠️ High risk. Limit outdoor activity." if risk_score_pct > 60
                          else "✅ Acceptable air quality risk."
    }
if __name__ == "__main__":
    mcp.run()
