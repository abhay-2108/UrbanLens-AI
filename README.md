# UrbanLens AI 🏙️
> Transform raw city data, street imagery, and social sentiment into a personalized, hyper-local Liveability Index.

UrbanLens AI is a modular geospatial intelligence system that evaluates neighborhood liveability at the H3 hexagonal grid level. Unlike static rating systems, UrbanLens uses a hierarchical liveability matrix combined with a dynamic Profile Engine to customize neighborhood scores for different user personas (e.g., Students, Remote Engineers, Families).

---

## 📊 The Liveability Matrix & Factors

Liveability is computed across 5 core factors, each backed by real-time scrapers and deep-learning inference pipelines:

### 1. 🛡️ Safety & Security
- **Crime Rate Index:** Localized incident tracking from municipal records.
- **Street-Level Illumination:** Automatic streetlight detection via night street-imagery segmentation.
- **Emergency Proximity:** Spatial driving/walking distance to police, fire stations, and hospitals.

### 2. 🍏 Sustenance & Daily Essentials
- **Food Ecosystem & Groceries:** Density and walking distance to supermarkets, fresh produce markets, and restaurants (OpenStreetMap / Overpass API).
- **Healthcare Access:** Proximity to pharmacies and clinics.

### 3. 🚇 Connectivity & Mobility
- **Public Transit Density:** Distance to metro stations, bus stops, and railway hubs.
- **Last-Mile Accessibility:** Density of ride-share pick-ups and pedestrian infrastructure.
- **Sidewalk Quality:** Semantic segmentation of sidewalk surfaces via Computer Vision.

### 4. 🌳 Health & Environmental Vibe
- **Green Canopy Score:** Foliage percentage calculated via `DeepLabV3` segmentation on street view images.
- **Air Quality Index (AQI):** 4-hour forecasts and pollutant prediction using LSTM and CNN models.
- **Climate Resilience:** Elevation mapping from Open-Elevation API to assess flood risks.

### 5. 🎭 Lifestyle & Community Vibe
- **Public Spaces:** Access to parks, lakes, and walking tracks.
- **Neighborhood Sentiment:** Real-time social signal analysis of local subreddits (Reddit API) to capture neighborhood complaints (e.g., water logging, power cuts).

---

## 🛠️ Technology Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Grid System** | Uber H3 (Res 8) | Discretizes urban areas into hexagons (~0.73 km²) |
| **Databases** | MongoDB & PostgreSQL (PostGIS) | Dual setup: raw ingestion logs (NoSQL) & spatial indices (PostGIS) |
| **Inference Engine** | Keras / ONNX Runtime | Hosts LSTM, CNN, MLP, and multi-task models |
| **Orchestration** | Apache Airflow | Schedules weekly scrapers and CV pipeline jobs |
| **Data Ingest** | Python HTTP Agents | Custom scrapers for OSM Overpass, Open-Elevation, Reddit, and Mapillary |

---

## 📂 Repository Structure

```
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── mcp_server/               # Air Quality Model Reasoning MCP Server
│   ├── server.py             # FastMCP entry point (LSTM, CNN, MLP, Health models)
│   └── remote_api_mcp.py     # Remote API testing script
├── models/                   # Deep learning binaries (ONNX, Keras saved models)
├── src/                      # Source Code
│   ├── database/             # MongoDB & PostgreSQL schemas
│   ├── scrapers/             # Ingestion scripts (OSM, AQI, Elevation, Reddit, Mapillary)
│   ├── pipelines/            # Analysis engines (Walkability, Computer Vision)
│   └── orchestration/        # Workflow DAGs (Airflow, Prefect)
├── tests/                    # Integration and unit tests
└── docs/                     # Documentation & Architecture logs
```

---

## 🚀 Getting Started

To run the project, set up your local environment, configure databases, and launch the scrapers:
1. Refer to [RUNNING_INSTRUCTIONS.md](file:///p:/Hackathons/UrbanLens%20AI/RUNNING_INSTRUCTIONS.md) for detailed deployment commands and API key generation steps.
2. Read [docs/implementation_details.md](file:///p:/Hackathons/UrbanLens%20AI/docs/implementation_details.md) to understand the technical architecture and phase-by-phase development timeline.
