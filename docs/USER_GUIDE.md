# User guide

1. Start CrisisMap with `python run.py`.
2. Click an area on the map or enter part of a local place name and press Enter.
3. Choose Flood, Wildfire, or Earthquake and set intensity, duration, and preparedness.
4. Select **Run assessment**. The map shows a color-coded affected zone and the right panel explains the score.
5. Use **File → Export assessment** to save a local JSON report.

## Maps

- **Map → Load demo region** restores the bundled synthetic dataset.
- **Map → Generate procedural terrain** creates a repeatable local terrain using a numeric seed.
- **File → Open GeoJSON** imports a local FeatureCollection.
- Drag to pan, use the mouse wheel to zoom, and click to select the nearest named feature.

## Interpreting results

The score combines hazard (52%), exposure (25%), and vulnerability (23%). Preparedness reduces vulnerability. The model is intentionally transparent and deterministic so it can be reviewed in a classroom. It does not use live weather, sensor, population, or emergency data and must not be used as an official warning.
