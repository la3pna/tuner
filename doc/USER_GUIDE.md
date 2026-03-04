# USER GUIDE – Tuner TCP Measurement System

## 1. Overview

This system controls Focus slide-screw RF tuners via a TCP service and uses LibreVNA
for S-parameter measurements. One service instance runs per tuner (Variant A).

Main components:

- tuner_service.py (TCP server)
- tuner_backend.py (TCP/Serial transport)
- vna_backend.py (LibreVNA SCPI interface)
- calibration_store.py (CSV-based calibration per frequency)
- lookup_engine.py (state selection logic)
- CLI tools (cli_setz.py, cli_measure.py)

Each tuner runs on its own TCP port:

- tuner1 → 53190
- tuner2 → 53191

---

## 2. Installation

Python 3.10+ recommended.

Install dependencies:

    pip install -r requirements.txt

Ensure:
- LibreVNA GUI is running
- SCPI server enabled (default 19542)
- Calibration active inside LibreVNA

---

## 3. Starting the System

Start one service per tuner:

    python tuner_service.py --config config.json --tuner tuner1

Expected output:

    Tuner service (tuner1) listening on ('0.0.0.0', 53190)

---

## 4. Generating Calibration States

Example for tuner1:

    python gen_calstates.py --xmax 14750 --ymax 2970 --nx 80 --ny 14 --serpentine --sanity --out states/states_tuner1.csv

---

## 5. Calibrating a Frequency

Example (via client):

    {
      "cmd": "cal_add_freq",
      "f_hz": 2400e6,
      "states_csv": "states/states_tuner1.csv",
      "home_first": true
    }

Calibration files are stored in:

    cal/f_2400MHz.csv

---

## 6. Setting Impedance

Set R+jX:

    python cli_setz.py --tuner tuner1 --freq 2400e6 --R 30 --X 15 --pretty

Set Gamma directly:

    python cli_setz.py --tuner tuner1 --freq 2400e6 --gamma-re 0.5 --gamma-im -0.2

---

## 7. Measuring One Point

    python cli_measure.py --tuner tuner1 --freq 2400e6 --pretty

Returns full S2P, IL and Gamma.

---

## 8. Lookup Strategy

Default: topn_min_il

1. Sort by |ΔΓ|
2. Select best N
3. Choose lowest insertion loss

Alternative:

    --select cost --alpha 0.02

J = |ΔΓ| + α·IL

---

## 9. Daily Workflow

1. Start service
2. Load calibration
3. Set impedance
4. Measure
5. Log results

---

## 10. File Structure

project/
│
├── config.json
├── tuner_service.py
├── lookup_engine.py
├── calibration_store.py
├── tuner_backend.py
├── vna_backend.py
├── cli_setz.py
├── cli_measure.py
├── cal/
├── states/
└── logs/

