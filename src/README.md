# Tuner TCP Service (Full System)

This package provides a modular TCP service (JSON Lines protocol) that owns a single Focus tuner and a LibreVNA connection.
Run one service instance per tuner (Variant A). The service keeps connections open so measurement scripts can run frequently
without reconnect overhead.

## Files
- `tuner_service.py`: TCP service (JSON Lines) on the port defined for the selected tuner in `config.json`.
- `client.py`: simple JSON-lines client.
- `cli_setz.py`: command-line tool to set impedance (R+jX) or gamma.
- `cli_measure.py`: command-line tool to measure S-parameters at one frequency point.
- `calibration_store.py`: load/save per-frequency calibration CSV files.
- `lookup_engine.py`: pick best tuner state based on gamma match + insertion loss.
- `tuner_backend.py`: connects to tuner controller via TCP or serial (from config).
- `vna_backend.py`: uses LibreVNA SCPI to measure one point (imports your `measure_one_point_via_scpi_trace_v4.py`).
- `service_protocol.py`: JSON-line helpers.
- `config_loader.py`: shared config reader.

## Setup
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Ensure LibreVNA-GUI is running and SCPI is enabled (default port 19542).
3. Copy your `measure_one_point_via_scpi_trace_v4.py` into the same folder (already included here).
4. Edit `config.json` with your tuner IP/COM settings.

## Run service (one per tuner)
```bash
python tuner_service.py --config config.json --tuner tuner1
```

## Set impedance and measure
```bash
python cli_setz.py --tuner tuner1 --freq 2400e6 --R 30 --X 15 --pretty
python cli_measure.py --tuner tuner1 --freq 2400e6 --pretty
```

## Calibration folder layout
- `cal/` contains CSV files like `f_2400MHz.csv` (full complex S2P per tuner state)
- `states.csv` or `states/*.csv` define the (X,Y) state list to sweep during calibration (not included).
