# UrbanLens AI - Run Guide & API Key Setup 🚀

This guide explains how to set up the local environment, acquire all necessary API keys, run the data ingestion scrapers, and configure the local Model Context Protocol (MCP) server.

---

## 📋 Prerequisites

Ensure you have the following installed on your machine:
- **Python 3.12+**
- **uv** (highly recommended fast package installer)
- **MongoDB** running locally on port `27017`
- **PostgreSQL** (PostGIS enabled) running locally on port `5432`

---

## 🛠️ Step 1: Environment Setup

1. **Initialize the Virtual Environment**:
   Using `uv`, run this command in the project root directory:
   ```powershell
   uv venv
   ```

2. **Activate the Virtual Environment**:
   - **Windows PowerShell**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Linux/macOS**:
     ```bash
     source .venv/bin/activate
     ```

3. **Install Dependencies**:
   ```powershell
   uv pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy the example template to create your active `.env` file:
   ```powershell
   copy .env.example .env
   ```

---

## 🔑 Step 2: Acquire API Keys

Fill in the corresponding values in `.env` using the instructions below:

### 1. Mapillary Client Token
*Used for downloading street-level imagery.*
1. Go to the [Mapillary Developer Portal](https://www.mapillary.com/developer).
2. Sign in or create a free account.
3. Register a new application:
   - **Name:** `UrbanLensAI`
   - **Redirect URI:** `http://localhost` (or any valid URL)
4. Under the **Developer** section, copy the generated **Client Token** (starts with `MLY|`).
5. Paste it in `.env` as `MAPILLARY_CLIENT_TOKEN`.

### 2. Reddit API Credentials
*Used for scraping local neighborhood subreddits to analyze community sentiment.*
1. Go to [Reddit Apps Page](https://www.reddit.com/prefs/apps).
2. Scroll to the bottom and click **"Are you a developer? Create an app..."**
3. Configure the fields:
   - **Name:** `UrbanLensAI`
   - **App Type:** Select **script**
   - **Description:** `Geospatial Liveability Analyzer`
   - **Redirect URI:** `http://localhost:8080`
4. Click **Create app**.
5. Copy your credentials:
   - **Client ID:** The string displayed directly below the app name and "personal use script" (e.g., 14 characters).
   - **Client Secret:** Listed next to **secret**.
6. Set `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env`.

### 3. OpenAQ API Key
*Used to scrape real-time air quality index observations.*
1. Visit the [OpenAQ Portal](https://openaq.org/).
2. Register a free developer account.
3. Access your profile dashboard to locate your **API Key**.
4. Set it as `OPENAQ_API_KEY` in `.env`.

---

## 🏃 Step 3: Run the Ingestion Scrapers

You can execute the scrapers individually by passing a `--city` argument. The scrapers automatically save raw JSON logs to MongoDB/local backup files and write consolidated factors into PostgreSQL.

### 1. Run OpenStreetMap POI Ingestion:
```powershell
python -m src.scrapers.osm_scraper --city Chennai
```

### 2. Run Air Quality & Predictions Scraper:
*Uses the local MCP server's deep learning models if running, or falls back to standard estimations.*
```powershell
python -m src.scrapers.aqi_scraper --city Chennai
```

### 3. Run Topographical Elevation Scraper:
```powershell
python -m src.scrapers.elevation_scraper --city Chennai
```

### 4. Run Mapillary Street View Ingestion:
```powershell
python -m src.scrapers.mapillary_scraper --city Chennai
```

### 5. Run Reddit Neighborhood Sentiment Ingestion:
```powershell
python -m src.scrapers.reddit_scraper --city Chennai
```

---

## 🤖 Step 4: Configure the Local MCP Server

The local **Air Quality Reasoning MCP Server** (`mcp_server/server.py`) hosts Keras LSTM and ONNX models to predict future AQI forecasts and compute environmental health risks.

### Running the Server Manually
To start the FastMCP server in standalone mode (useful for debugging):
```powershell
.venv\Scripts\python.exe mcp_server\server.py
```

### Integrating with your IDE / LLM client
To integrate this server into an agentic IDE, write this entry into your `mcp_config.json`:

```json
{
    "mcpServers": {
        "air-quality": {
            "command": "p:\\Hackathons\\UrbanLens AI\\.venv\\Scripts\\python.exe",
            "args": [
                "p:\\Hackathons\\UrbanLens AI\\mcp_server\\server.py"
            ],
            "env": {
                "PYTHONPATH": "p:\\Hackathons\\UrbanLens AI"
            }
        }
    }
}
```

---

## 🧪 Step 5: Running Unit Tests

Verify that your installation is fully functional by executing the test suite:
```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```
*All 11 unit tests should output `OK`.*
