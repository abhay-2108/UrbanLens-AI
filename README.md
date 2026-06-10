# UrbanLens AI 🏙️

UrbanLens AI is a sophisticated urban liveability analysis system that transforms raw city data and street-level imagery into a quantifiable, personalized Liveability Index. Unlike static scoring systems, UrbanLens uses a hierarchical matrix of factors and a dynamic Profile Engine to tailor neighborhood recommendations to the specific needs of different user personas.

## 🚀 Core Concept

The system breaks down "Liveability" into a structured matrix of **Factors** and **Sub-Factors**, allowing the backend to apply adjustable weights based on user profiles (e.g., Students, Remote Engineers, Families).

## 📊 The Liveability Matrix

### 🛡️ 1. Safety & Security (The Absolute Baseline)
*Focuses on both statistical crime data and the psychological feeling of safety.*
- **Crime Rate Index:** Localized incident frequency from municipal data.
- **"Eyes on the Street" Vector:** Density of 24/7 commercial establishments.
- **Street-Level Illumination:** Detection of functioning streetlights via nighttime imagery.
- **Emergency Response Proximity:** Distance to police, fire, and medical facilities.

### 🍏 2. Sustenance & Daily Essentials (The Conveniences)
*Measures the ease of handling daily logistics.*
- **Food Ecosystem:** Density and variety of dining and delivery options.
- **Grocery & Fresh Produce Access:** Walking distance to markets and supermarkets.
- **Pharmacy & Healthcare Access:** Proximity to clinics and chemists.

### 🚇 3. Connectivity & Mobility (The Commute)
*Evaluates accessibility for both vehicle owners and public transit users.*
- **Public Transit Density:** Proximity to metro, bus, and train stations.
- **Last-Mile Accessibility:** Availability of ride-sharing and rentals.
- **Traffic Congestion Index:** Peak-hour bottleneck analysis.
- **Pedestrian Infrastructure:** Quality of sidewalks and crossings (via Computer Vision).

### 🌳 4. Health & Environmental Vibe (The Long-Term Comfort)
*Analyzes factors impacting physical and mental well-being.*
- **The Green Canopy Score:** Percentage of foliage at eye level (via `DeepLabV3` segmentation).
- **Air Quality Index (AQI):** Real-time and historical $PM_{2.5}$ and $PM_{10}$ levels.
- **Acoustic Comfort:** Noise pollution levels from industrial/highway proximity.
- **Climate Resilience:** Topographical elevation and flooding history.

### 🎭 5. Lifestyle, Recreation & Community (The "Vibe" Check)
*Captures the cultural and social character of a neighborhood.*
- **Public Social Spaces:** Access to parks, lakes, and walking tracks.
- **Entertainment Hubs:** Proximity to malls, theaters, and cultural centers.
- **Fitness Infrastructure:** Density of gyms and sports complexes.
- **Neighborhood Sentiment Layer:** Analysis of community discussions (Reddit, local forums).

## ⚙️ The Profile Engine

The system maps the matrix to specific user presets to provide personalized scoring:

| Preset | High Weight Factors | Low Weight Factors |
| :--- | :--- | :--- |
| **Student** | Food Ecosystem, Public Transit, Entertainment | Schools, Hospitals |
| **Remote Engineer** | Acoustic Comfort, Grocery Access, Sentiment Layer | Commute Density |
| **Family** | Safety Indexes, Schools/Healthcare, Social Spaces | Nightlife Density |

## 🛠️ Technical Stack (Planned)
- **Computer Vision:** `DeepLabV3` for semantic segmentation of street imagery.
- **Data Sources:** Municipal APIs, OpenStreetMap, Social Media (Reddit), Environmental Sensors.
- **Analysis:** Weighted Matrix Algorithm for personalized liveability scoring.

## 📈 Future Roadmap
- [ ] Integration of Rent-to-Income ratios for economic accessibility.
- [ ] Utility reliability tracking (Power/Water consistency).
- [ ] "15-Minute City" binary scoring.
