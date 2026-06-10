# UrbanLens AI: Technical Documentation
# This directory contains detailed design documents for the system.

## Project Structure
The project follows a modular architecture:
- `src/database`: Schema definitions for PostGIS and MongoDB.
- `src/pipelines`: Core analysis engines (CV, Walkability).
- `src/scrapers`: Data collection logic.
- `src/orchestration`: Workflow management (Airflow/Prefect).

## Data Flow
1. **Ingestion**: Scrapers pull raw data into MongoDB.
2. **Processing**: Pipelines process raw data into normalized scores.
3. **Storage**: Final scores are stored in PostGIS H3 grids.
4. **Delivery**: API serves personalized scores based on user profiles.
