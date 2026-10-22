# CrisisMap

CrisisMap is a desktop application for exploring disaster scenarios across Pune. It combines an interactive, multi-layer map with a transparent impact assessment, visual summaries, and a local question-answering assistant.

> **Intended use:** planning and educational exploration. Model outputs are estimates, not live forecasts, official guidance, or a substitute for emergency services.

## What it does

- Browse Pune with street, satellite, and terrain basemaps; search and select locations directly on the map.
- Explore earthquake, flood, and wildfire scenarios with animated overlays and configurable inputs.
- Review impact indicators, charts, and a concise detailed analysis for the active assessment.
- Ask questions about the selected location and assessment using the bundled Qwen2.5-0.5B assistant.
- Load GeoJSON datasets and export assessment summaries as JSON.

## Requirements

- Windows 10/11 (the primary supported desktop platform)
- Python 3.12.x
- 4 GB or more of available memory recommended for local assistant inference
- Internet access for map tiles and Leaflet assets

The assistant model is included in the repository. The application is **partially offline**: assessment calculations, bundled datasets, and assistant inference run locally, while basemap tiles and Leaflet assets are fetched online.

## Install and run

Install 64-bit Python 3.12, then run these commands in PowerShell from the project directory:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

For development, install the package in editable mode with `python -m pip install -e .`. This also makes `python -m crisismap` and the `crisismap` command available.

## Map and data

Bundled datasets are stored in `src/crisismap/resources/data/`:

- **Pune wards:** 58 ward boundaries attributed to OpenCity/Oorvani Foundation; licensed under ODbL-1.0.
- **Pune roads, shelters, and flood zones:** local GeoJSON layers for map context.
- **Demo region:** synthetic demonstration features.

Map layers use Leaflet, OpenStreetMap, Esri World Imagery, and OpenTopoMap. An internet connection is required to load the map assets and tiles. Keep the attribution shown in the map when redistributing screenshots or derived map products, and follow each provider's usage and attribution terms.

Use **File → Open GeoJSON** to load a local FeatureCollection. CrisisMap supports Polygon/MultiPolygon areas and Point features. Feature properties can provide `name`, `elevation` (metres), `vegetation`, `density`, `soil`, and `water_distance` values; normalized factors use a 0–1 range. Alternate ward-name and coordinate conventions are also handled by the importer.

## Local assistant

CrisisMap packages [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) for local inference. The model is licensed under Apache-2.0; see its bundled license at `src/crisismap/resources/model/qwen2.5-0.5b-instruct/LICENSE`. The assistant receives the current assessment context, but generated answers can still be incorrect. Verify safety-critical decisions with local authorities and emergency services.

## Build a distributable package

From an environment with the requirements installed:

```powershell
python -m pip install build
python -m build
```

The wheel includes the bundled model and map data, so it is large. Distribute it through a channel that supports large files; the model weights are tracked with Git LFS in this repository. Recipients need Python 3.12 and internet access for the interactive basemap.

## Project structure

```text
src/crisismap/
  app.py                 application entry point
  models.py              assessment and location data models
  simulation.py          scenario scoring and impact estimates
  assistant_model.py     local assistant and assessment context
  data_repository.py     GeoJSON loading and bundled datasets
  ui/                    desktop interface and interactive map
  resources/data/        Pune and demonstration GeoJSON
  resources/model/       bundled Qwen assistant
tests/                   simulation-core checks
docs/                    user and project guidance
```
