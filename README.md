# CrisisMap

CrisisMap is a fully offline Windows desktop application for educational disaster-impact assessment. It renders local GeoJSON in a native PySide6 map view and simulates flood, wildfire, and earthquake risk without contacting map servers, geocoders, or APIs.

> CrisisMap is an assessment and teaching tool, not a forecasting or emergency-response system.

## Features

- Interactive pan/zoom map with click-to-select locations
- Local place search from the loaded dataset
- Flood, wildfire, and earthquake scenario controls
- Deterministic, explainable risk scoring and map overlays
- Synthetic built-in demo region and procedural terrain generator
- Import of local `.geojson`/`.json` map files
- Export of simulation summaries to JSON
- No login, telemetry, HTTP client, or network configuration

## Requirements

- Windows 11 (Linux/macOS should also work)
- Python 3.13.x
- PySide6 6.8 or newer

Create the environment and install the UI dependency from a previously downloaded wheel or a local package mirror when the target machine must remain air-gapped:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --no-index --find-links C:\path\to\wheels -r requirements.txt
```

For a machine that is allowed to prepare the environment before it is taken offline, a normal `pip install -r requirements.txt` also works. CrisisMap itself does not perform network access.

## Run

```powershell
python run.py
```

The project uses a `src` layout. After a local editable install (`python -m pip install -e .`), `python -m crisismap` and the `crisismap` command are also available.

## Test

The simulation-core tests use only the Python standard library:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m unittest discover -s tests -v
```

## Local map data

Use **File → Open GeoJSON** to load a local FeatureCollection. CrisisMap understands Polygon/MultiPolygon areas and Point features. Useful optional properties are:

| Property | Range | Meaning |
|---|---:|---|
| `name` | text | Search/display label |
| `elevation` | metres | Higher ground reduces flood risk |
| `vegetation` | 0–1 | Increases wildfire risk |
| `density` | 0–1 | Increases exposure |
| `soil` | 0–1 | Softer soil increases earthquake risk |
| `water_distance` | 0–1 | Normalized distance from water |

The app also supports GeoJSON files with alternate property names (`Name1`, `Name2`, `wardnum`) and coordinate ordering ([lat, lon] vs [lon, lat]).

### Bundled datasets

- **Demo region** (`demo_region.geojson`) — synthetic CC0 demonstration data with 8 features.
- **Pune wards** (`pune_wards.geojson`) — real Pune Municipal Corporation ward boundaries (58 wards, ODbL-1.0, source: OpenCity/Oorvani Foundation). Load via **Map → Load Pune wards (real map)**.

OpenStreetMap data is available under ODbL and Natural Earth data is public domain. Export and store only the area needed, retain the source attribution, and load the resulting file locally. The included `demo_region.geojson` is synthetic and CC0.

## Project layout

```text
src/crisismap/
  app.py                 application entry point and theme
  models.py              domain models and validation
  simulation.py          offline risk engine
  data_repository.py     GeoJSON loading and procedural data
  export.py              local JSON reports
  ui/                    PySide6 interface and map renderer
  resources/data/        bundled offline data
tests/                   standard-library core tests
docs/                    installation and user guidance
```

No Git repository is initialized by this project.
