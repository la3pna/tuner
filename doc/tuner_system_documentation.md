# Tuner System Documentation

## Overview

This system controls one or two RF tuners through a TCP service and uses a LibreVNA for calibrated S-parameter measurements. The main use case is tuner calibration and later impedance-based measurements such as load pull and noise figure work.

The system is built around these ideas:

- The tuner controller firmware handles motion over UART or TCP.
- `tuner_service.py` exposes a simple JSON/TCP interface for higher-level scripts.
- `vna_backend.py` configures LibreVNA through SCPI and reads calibrated trace data from the JSON stream.
- Calibration is stored as CSV files, one file per frequency.
- Later measurements should normally use the full calibrated table as the measurement grid. If finer resolution is needed, a denser table is measured.

---

## Current System Status

The following has been verified working:

- Tuner control over `tuner_service.py`
- Homing
- Verified `goto_x()` / `goto_y()` with retry after home
- VNA measurement through LibreVNA SCPI + JSON stream
- Calibration run for one frequency
- Lookup with `setz`
- Smith-diagram style plotting from calibration CSV
- Adaptive state generation for calibration

---

## System Architecture

```text
User script
   |
   v
client.py
   |
   v
tuner_service.py  <----> calibration_store.py
   |        |
   |        +----> vna_backend.py ----> LibreVNA
   |
   +----> tuner_backend.py ----> tuner firmware ----> tuner hardware
```

---

## Directory Structure

Recommended structure:

```text
tuner/
├── src/
│   ├── client.py
│   ├── tuner_service.py
│   ├── tuner_backend.py
│   ├── vna_backend.py
│   ├── calibration_store.py
│   ├── lookup_engine.py
│   ├── config_loader.py
│   ├── verify_system.py
│   └── other scripts
├── cal/
│   ├── f_0433MHz.csv
│   ├── f_1000MHz.csv
│   └── ...
├── states/
│   ├── states_433MHz_adaptive.csv
│   ├── states_1000MHz_adaptive.csv
│   └── ...
├── logs/
├── config.json
└── README.md
```

---

## Configuration

Example `config.json`:

```json
{
  "version": 1,
  "service": {
    "bind_host": "0.0.0.0",
    "client_host": "127.0.0.1",
    "client_timeout_s": 1800
  },
  "paths": {
    "cal_dir": "cal",
    "state_sets_dir": "states",
    "log_dir": "logs"
  },
  "tuners": [
    {
      "name": "tuner1",
      "enabled": false,
      "service": { "port": 53190 },
      "transport": "tcp",
      "tcp": { "host": "192.168.1.50", "port": 12001, "timeout_s": 1.0 },
      "serial": { "port": "COM6", "baud": 115200, "timeout_s": 1.0 },
      "motion": {
        "wait_stop_timeout_s": 30.0,
        "poll_s": 0.05,
        "home_on_connect": false,
        "motion_ok_timeout_s": 300.0,
        "move_verify_retries": 2,
        "retry_delay_s": 0.2,
        "post_home_delay_s": 0.1
      }
    },
    {
      "name": "tuner2",
      "enabled": true,
      "service": { "port": 53191 },
      "transport": "serial",
      "tcp": { "host": "192.168.1.182", "port": 12001, "timeout_s": 1.0 },
      "serial": { "port": "COM5", "baud": 115200, "timeout_s": 1.0 },
      "motion": {
        "wait_stop_timeout_s": 30.0,
        "poll_s": 0.5,
        "home_on_connect": false,
        "motion_ok_timeout_s": 300.0,
        "move_verify_retries": 2,
        "retry_delay_s": 0.2,
        "post_home_delay_s": 0.1
      }
    }
  ],
  "vna": {
    "type": "LibreVNA",
    "enabled": true,
    "scpi": { "host": "127.0.0.1", "port": 19542 },
    "measure_one_point": {
      "power_dbm": -10.0,
      "ifbw_hz": 10000.0,
      "avg": 1,
      "span_hz": 400000.0,
      "points": 3,
      "sweep_timeout_s": 8.0
    }
  },
  "lookup": {
    "z0_ohm": 50.0,
    "default_select": "topn_min_il",
    "top_n": 30,
    "alpha": 0.02,
    "x_move_weight": 0.00002,
    "y_move_weight": 0.000002
  }
}
```

### Notes

- `client_timeout_s` should be long for calibration, for example `1800` seconds.
- `points=3` and small span is recommended. This gives start, center, stop and uses the center point.
- `x_move_weight` and `y_move_weight` can be used to prefer smaller motion, especially because X is slower than Y.

---

## Tuner Control Commands

The higher-level scripts use `client.py` and `tuner_service.py`. The firmware itself accepts SCPI-like commands such as:

- `:MOT:HOME:ALL`
- `:MOT:HOME:X`
- `:MOT:HOME:Y`
- `:MOT:X:GOTO <n>`
- `:MOT:Y:GOTO <n>`
- `:MOT:X:POS?`
- `:MOT:Y:POS?`
- `:MOT:X:STAT?`
- `:MOT:Y:STAT?`
- `*IDN?`

### Important behavior

- `HOME` returns `OK` after motion is complete.
- The first `GOTO` after `HOME` may sometimes need one retry.
- `POS?` must be used to verify that the move actually happened.
- `STAT?` may show values such as `STOP,HOMED,POS=0`.

---

## Service Commands

The JSON service supports at least these commands:

### `ping`

```python
{"cmd": "ping"}
```

### `idn`

```python
{"cmd": "idn"}
```

### `home`

```python
{"cmd": "home", "axis": "all"}
{"cmd": "home", "axis": "x"}
{"cmd": "home", "axis": "y"}
```

### `setxy`

```python
{"cmd": "setxy", "x_steps": 800, "y_steps": 400}
```

### `measure`

```python
{"cmd": "measure", "f_hz": 1e9}
```

### `load_cal`

```python
{"cmd": "load_cal", "f_hz": 1e9}
```

### `setz`

```python
{"cmd": "setz", "f_hz": 1e9, "R": 25, "X": 0}
```

Optional motion bias:

```python
{
  "cmd": "setz",
  "f_hz": 1e9,
  "R": 25,
  "X": 0,
  "x_move_weight": 0.00002,
  "y_move_weight": 0.000002
}
```

### `cal_add_freq`

```python
{
  "cmd": "cal_add_freq",
  "f_hz": 1e9,
  "states_csv": "states/states_1000MHz_adaptive.csv",
  "home_first": true
}
```

---

## CLI Examples

### Start the service

```bat
python .\tuner_service.py --config config.json --tuner tuner2
```

### Ping

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'ping'}))"
```

### Home all axes

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'home','axis':'all'}))"
```

### Move to a known point

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'setxy','x_steps':800,'y_steps':400}))"
```

### Measure at 1 GHz

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'measure','f_hz':1e9}))"
```

### Set impedance

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'setz','f_hz':1e9,'R':25,'X':0}))"
```

### Run a calibration

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'cal_add_freq','f_hz':1e9,'states_csv':'states/states_1000MHz_adaptive.csv','home_first':True}, timeout_s=1800))"
```

---

## LibreVNA Integration

### Ports

- SCPI control: `19542`
- Calibrated JSON trace stream: `19001`
- De-embedded or raw JSON stream: `19002`

### Recommended mode

Use:

- SCPI on `19542`
- calibrated JSON stream on `19001`

### Measurement mode

Use a small 3-point sweep:

- `points = 3`
- `span_hz = small`, for example `400000`
- use the center point

This is more robust than single-point mode.

### Returned values

`measure` returns:

- `f_hz`
- `s11`, `s21`, `s12`, `s22` as `[re, im]`
- `il_db` which is currently `20*log10(|S21|)`

In practice this field behaves like S21 in dB. If a clearer name is wanted later, it can be renamed to `s21_db`.

---

## Calibration Philosophy

### Recommended approach

Use Alternative A for later measurements:

- measure the whole calibration table
- use the table itself as the measurement grid
- if more resolution is needed, create a denser table

This is the most robust approach because:

- every point is real and calibrated
- there is no additional lookup uncertainty
- a denser table can be added later only where needed

### Why this is preferred

For load pull or noise figure work, this avoids relying too much on interpolation or nearest-neighbor selection. Instead, the real measured tuner states form the sweep space.

---

## Calibration Procedure

### Step 1: Prepare hardware

Recommended setup:

```text
LibreVNA port 1
   |
   | adapter/cable
   |
tuner input
tuner output
   |
  50 ohm load
```

Assumptions:

- Port 2 is terminated in `50 ohm`
- calibration is referenced so that the tuner is measured correctly at the desired plane

### Step 2: Home the tuner

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'home','axis':'all'}))"
```

### Step 3: Generate states

Example for 1000 MHz:

```bat
python make_adaptive_states_mhz.py --freq-mhz 1000
```

### Step 4: Run calibration

```bat
python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'cal_add_freq','f_hz':1e9,'states_csv':'states/states_1000MHz_adaptive.csv','home_first':True}, timeout_s=1800))"
```

### Step 5: Verify calibration file

This should create:

```text
cal\f_1000MHz.csv
```

---

## Calibration File Format

A calibration file contains one row per tuner state. Example columns:

- `f_hz`
- `x_steps`
- `y_steps`
- `s11_re`
- `s11_im`
- `s21_re`
- `s21_im`
- `s12_re`
- `s12_im`
- `s22_re`
- `s22_im`

These files are used for:

- lookup
- plotting
- direct measurement sweeps over the full calibration table

---

## State Generation

### Why states must be adaptive

A sliding capacitive probe tuner does not produce uniform Smith-diagram coverage from a uniform `(x,y)` grid.

Important behavior:

- small `y` keeps the tuner close to `50 ohm`
- large `y` spreads points outward in the Smith chart
- `x` mainly rotates the reflection phase along the line
- `x` is mechanically slower than `y`

Therefore, a good states generator should:

- place few points near `y = 0`
- place many points near `y = ymax`
- use fewer X positions at low Y
- use more X positions at high Y
- adjust X density with frequency

### Frequency-aware generator

Use:

```bat
python make_adaptive_states_mhz.py --freq-mhz 1000
```

This generates:

- `states_1000MHz_adaptive.csv`
- `states_1000MHz_adaptive_summary.csv`

The generator uses:

- frequency in MHz
- `xmax_used`, default `14600`
- `ymax`, default `3030`
- a Y-bias exponent
- an electrical-phase heuristic for X density

### Why frequency matters

Moving the discontinuity along X changes phase. The phase span across the tuner depends on frequency, so higher frequency should usually use more X positions.

---

## 433 MHz Coverage Notes

The 433 MHz dataset showed these useful observations:

- total points: `157`
- `min |Gamma| ≈ 0.006`
- `max |Gamma| ≈ 0.731`
- many points still clustered near the center
- roughly `40` points had `|Gamma| < 0.1`

This means coverage can be improved by:

- reducing low-Y points
- concentrating more states at higher Y
- keeping X rotation mainly where Y is large

This supports using the adaptive generator rather than a rectangular grid.

---

## Impedance Lookup

`setz` converts the desired impedance to `Gamma`, then searches the calibration table for the best match.

### Lookup basis

For the tuner output plane, the lookup is based on:

- `S22`

This is the correct basis when port 1 sees `50 ohm` and the tuner presents an impedance toward the DUT side.

### Motion-aware lookup

Because X is slower than Y, lookup can include a motion penalty:

```text
cost = |Gamma - Gamma_target| + wx*|dx| + wy*|dy|
```

Use larger `wx` than `wy`.

Recommended starting point:

- `x_move_weight = 0.00002`
- `y_move_weight = 0.000002`

This makes the tuner prefer smaller X motion when two points are otherwise similar.

---

## Measurement Strategy

### Recommended strategy

Use the full calibration table as the measurement grid.

Workflow:

1. Load one calibrated table for a frequency
2. Sweep every calibrated point `(x,y)`
3. Measure DUT response at each point
4. Store the result in a measurement CSV
5. If more resolution is needed, create a denser calibration table in that region

### Why this is best

- no extra lookup uncertainty
- every measured point is already calibrated
- easier to repeat and compare
- ideal for first load-pull and noise-figure runs

### Suggested future measurement scripts

- `measure_state_list.py`
- `measure_load_pull.py`
- `measure_nf.py`

A good first measurement script should:

- read a calibration CSV
- move through all rows
- measure DUT
- log the result

---

## Verification

### Quick checks

Service + VNA:

```bat
python verify_system.py --config config.json --tuner tuner2 --measure
```

Full check:

```bat
python verify_system.py --config config.json --tuner tuner2 --home --setxy --measure --expect-cal cal\f_1000MHz.csv --setz --freq-mhz 1000
```

### What `verify_system.py` tests

- `ping`
- `idn`
- optional file existence checks
- `home`
- `setxy`
- `measure`
- `load_cal`
- `setz`

---

## Plotting and Analysis

A calibration CSV can be plotted on a Smith-chart style plot using either:

- `S22` for tuner output impedance coverage
- `S11` for the port-1 view

Useful analysis:

- plot all points in the Gamma-plane
- color by `S21 dB`
- find the convex hull or outer boundary
- report min and max `|Gamma|`
- convert `Gamma` to impedance and report min/max `R` and `X`

### Interpretation

If many points cluster near the center:

- too many low-Y states are being measured

If outer coverage is weak:

- more high-Y points are needed
- X density may need to increase at high Y

---

## Troubleshooting

### 1. `Expected OK, got ''`

Usually means line termination or timeout problems.

Check:

- firmware line ending
- serial port and baud rate
- motion timeout values

### 2. First move after home does not happen

This has already been handled by retry logic.

The system should:

- send `GOTO`
- check `POS?`
- retry once if the position did not change

### 3. `ERR TIMEOUT` during home

This comes from firmware, not from Python.

Typical causes:

- firmware home timeout too short
- mechanical issue
- switch not reached in time

### 4. Client timeout during long calibration

This means the client stopped waiting, while the server continued working.

Fix:

- increase `client_timeout_s`
- use a long timeout such as `1800` seconds for calibration

### 5. `Task exception was never retrieved` or WinError 10053

This is a client disconnect while the server is still working.

The patched `client_task()` should treat this as a normal disconnect and exit quietly.

### 6. Wrong frequency seen in measurement

Single-point mode was unreliable. Use:

- `points = 3`
- small `span_hz`
- center point selection

### 7. Smith plot too center-heavy

Use an adaptive states file with:

- fewer low-Y states
- more high-Y states
- frequency-aware X density

---

## Recommended Frequency Plan

Initial useful frequencies:

- `432 MHz`
- `433 MHz`
- `434 MHz`
- `868 MHz`
- `1296 MHz`
- `1298 MHz`
- `1420 MHz`
- `2304 MHz`
- `2320 MHz`
- `2400 MHz`
- `3400 MHz`
- `5760 MHz`

Each frequency should normally have:

- its own adaptive states CSV
- its own calibration file

---

## Recommended Workflow for New Frequency

Example for `433 MHz`:

1. Generate states:

   ```bat
   python make_adaptive_states_mhz.py --freq-mhz 433
   ```

2. Home tuner:

   ```bat
   python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'home','axis':'all'}))"
   ```

3. Run calibration:

   ```bat
   python -c "from client import ServiceClient; c=ServiceClient.from_config('config.json','tuner2'); print(c.call({'cmd':'cal_add_freq','f_hz':433e6,'states_csv':'states/states_433MHz_adaptive.csv','home_first':True}, timeout_s=1800))"
   ```

4. Verify:

   ```bat
   python verify_system.py --config config.json --tuner tuner2 --measure --expect-cal cal\f_0433MHz.csv --freq-mhz 433
   ```

5. Use the full table later as the measurement grid.

---

## Future Improvements

Recommended next developments:

- dedicated measurement scripts using the full calibration table
- progress reporting during calibration
- logging of every calibration and measurement run
- automatic multi-frequency calibration runner
- optional re-measurement of dense local tables for promising regions
- clearer naming of `il_db` to `s21_db` if wanted

---

## Summary

The system is now structured so that:

- the tuner can be controlled reliably
- calibration can be run per frequency
- adaptive state tables can be generated from frequency in MHz
- lookup can include motion bias
- later DUT measurements should use the full calibrated table

This is a solid base for:

- load pull
- noise figure optimization
- impedance exploration
- repeated characterization over known tuner states
