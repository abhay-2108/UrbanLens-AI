"""
MCP Server Template for Remote (Vercel) APIs
=============================================
This is an MCP server that delegates the prediction tasks to the deployed FastAPI application
hosted on Vercel or any other cloud provider.

Update the `BASE_API_URL` variable to your deployed vercel project link.
"""

import os
import requests
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Remote Prediction API System")

BASE_API_URL = "https://mcp-powered-multi-agent-air-quality.vercel.app" 

@mcp.tool()
def predict_loan(
    gender: str,
    married: str,
    dependents: str,
    education: str,
    self_employed: str,
    applicant_income: float,
    coapplicant_income: float,
    loan_amount: float,
    loan_amount_term: float,
    credit_history: float,
    property_area: str
) -> dict:
    """
    Calls the external Loan Prediction API to determine if a loan should be approved.
    """
    payload = {
        "Gender": gender,              # "Male" / "Female"
        "Married": married,            # "Yes" / "No"
        "Dependents": dependents,      # "0", "1", "2", "3+"
        "Education": education,        # "Graduate" / "Not Graduate"
        "Self_Employed": self_employed,# "Yes" / "No"
        "ApplicantIncome": applicant_income,
        "CoapplicantIncome": coapplicant_income,
        "LoanAmount": loan_amount,
        "Loan_Amount_Term": loan_amount_term,
        "Credit_History": credit_history, # 1.0 or 0.0
        "Property_Area": property_area # "Urban", "Semiurban", "Rural"
    }

    try:
        response = requests.post(f"{BASE_API_URL}/predict_loan", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to reach API: {str(e)}"}

@mcp.tool()
def predict_heart_disease(
    age: float,
    sex: int,
    cp: int,
    trestbps: float,
    chol: float,
    fbs: int,
    restecg: int,
    thalach: float,
    exang: int,
    oldpeak: float,
    slope: int,
    ca: int,
    thal: int
) -> dict:
    """
    Calls the external Heart Disease Prediction API to assess health risk.
    """
    payload = {
        "age": age,
        "sex": sex,               # 1 = male, 0 = female
        "cp": cp,                 # Chest pain type (0-3)
        "trestbps": trestbps,     # Resting blood pressure
        "chol": chol,             # Serum cholestoral in mg/dl
        "fbs": fbs,               # Fasting blood sugar (1 = true; 0 = false)
        "restecg": restecg,       # Resting electrocardiographic results (0-2)
        "thalach": thalach,       # Maximum heart rate achieved
        "exang": exang,           # Exercise induced angina (1 = yes; 0 = no)
        "oldpeak": oldpeak,       # ST depression
        "slope": slope,           # Slope of the peak exercise ST segment (0-2)
        "ca": ca,                 # Number of major vessels (0-4)
        "thal": thal              # Thalassemia (0-3)
    }

    try:
        response = requests.post(f"{BASE_API_URL}/predict_heart_disease", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to reach API: {str(e)}"}

@mcp.tool()
def predict_stock_price(
    stock_data: list[dict]
) -> dict:
    """
    Predicts the next day's closing price for a stock given exactly 20 days of historical data.
    Each entry in stock_data must have: 'open', 'high', 'low', 'close', 'volume', and 'average'.
    """
    if len(stock_data) != 20:
        return {"error": "Exactly 20 days of historical stock data are required."}
    
    payload = {"data": stock_data}

    try:
        response = requests.post(f"{BASE_API_URL}/predict_stock_price", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to reach API: {str(e)}"}

if __name__ == "__main__":
    # Runs the standard MCP stdio communication
    mcp.run()
