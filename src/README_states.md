# Calibration state meshes

Generated for:
- tuner1: xmax=14750, ymax=2970
- tuner2: xmax=14750, ymax=3030

Defaults used:
- nx=80, ny=14
- serpentine=True
- sanity points=True (corners + center)
- margins: x_margin=200 steps, y_margin=50 steps
- y_edge_power=1.6

Ranges after margins:
- tuner1: x=[200..14550], y=[50..2920]
- tuner2: x=[200..14550], y=[50..2980]

Files:
- states/states_tuner1.csv
- states/states_tuner2.csv

Regenerate (same defaults):
python gen_calstates.py --xmax 14750 --ymax 2970 --nx 80 --ny 14 --x-margin 200 --y-margin 50 --y-edge-power 1.6 --serpentine --sanity --out states/states_tuner1.csv
python gen_calstates.py --xmax 14750 --ymax 3030 --nx 80 --ny 14 --x-margin 200 --y-margin 50 --y-edge-power 1.6 --serpentine --sanity --out states/states_tuner2.csv
