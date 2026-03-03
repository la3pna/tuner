# CALIBRATION PROCEDURE – Focus Slide Screw Tuner

## 1. Objective

Measure full S2P for all X/Y states at a specific frequency and generate
a calibration file for impedance lookup.

---

## 2. Preparation

1. Ensure LibreVNA is calibrated.
2. Connect tuner with final adapters (APC7→SMA/N).
3. Do NOT change cables after calibration.
4. Ensure tuner homing works.

---

## 3. Generate State Mesh

Example:

    python gen_calstates.py --xmax 14750 --ymax 2970 --nx 80 --ny 14 --serpentine --sanity --out states/states_tuner1.csv

Use margins to avoid mechanical end-stops.

---

## 4. Start Service

    python tuner_service.py --config config.json --tuner tuner1

---

## 5. Run Calibration

Send:

    {
      "cmd": "cal_add_freq",
      "f_hz": 2400e6,
      "states_csv": "states/states_tuner1.csv",
      "home_first": true
    }

System will:
- Home tuner
- Move to each state
- Measure S11,S21,S12,S22
- Save CSV file

---

## 6. Verification

After completion:

    python cli_setz.py --tuner tuner1 --freq 2400e6 --R 50 --X 0

Then measure and confirm match.

---

## 7. Recommended Frequency List

Common frequencies:
432 MHz
868 MHz
1296 MHz
2400 MHz
3400 MHz
5760 MHz

Calibrate only when mechanical or RF configuration changes.
