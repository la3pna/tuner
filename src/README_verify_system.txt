verify_system.py

Purpose
-------
Simple test and verification script for:
- client -> tuner_service
- tuner movement
- VNA measurement
- calibration file loading
- SETZ lookup

Typical use
-----------
1) Quick service + VNA check:
   python verify_system.py --config config.json --tuner tuner2 --measure

2) Full practical check:
   python verify_system.py --config config.json --tuner tuner2 --home --setxy --measure --expect-cal cal\f_1000MHz.csv --setz --freq-mhz 1000

3) Check with explicit target impedance:
   python verify_system.py --config config.json --tuner tuner2 --setz --freq-mhz 1000 --target-r 25 --target-x 0 --expect-cal cal\f_1000MHz.csv

Notes
-----
- --expect-cal is optional, but recommended before --setz.
- --states-csv only checks file existence.
- --timeout-s is the per-call timeout used by this script.
