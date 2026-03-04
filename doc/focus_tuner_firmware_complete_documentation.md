# Focus Tuner Firmware -- Complete Documentation Package

Platform: Arduino Zero (SAMD21)\
Interfaces: SerialUSB (115200) + TCP (Port 12001)\
Motor Driver: A3967 (STEP/DIR)\
Protocol: SCPI‑ish (case-insensitive)

------------------------------------------------------------------------

# 1. Overview

This firmware implements a dual-axis motorized tuner controller with:

-   Independent X and Y axes
-   Smart homing with endstop validation
-   Blocking command execution (OK sent after motion completes)
-   Error queue (SCPI-style)
-   Command queue (prevents command loss during motion)
-   EEPROM IP storage
-   Endstop polarity configurable per axis

All commands are ASCII, LF terminated.

------------------------------------------------------------------------

# 2. Transport Layer

## SerialUSB

-   115200 baud
-   LF terminated
-   Full duplex

## TCP

-   Port 12001
-   Single client
-   ASCII protocol identical to SerialUSB

------------------------------------------------------------------------

# 3. Command Execution Model

1.  Incoming commands are placed into an internal command queue.
2.  Commands are executed sequentially.
3.  Motion-related commands are blocking.
4.  OK is returned only after motion has completed.
5.  Errors are pushed into error queue.

------------------------------------------------------------------------

# 4. Command Reference

## Identification

Command: \*IDN?

Response: Manufacturer,Model,Serial,FW_Version

------------------------------------------------------------------------

## System Reset

Command: \*RST

Response: RESET

------------------------------------------------------------------------

## Error Queue

Command: :SYST:ERR?

Response: `<code>`{=html},`<message>`{=html}

If empty: 0,No error

Clear queue: :SYST:ERR:CLE

------------------------------------------------------------------------

## Network Configuration

Query IP: :SYST:COMM:LAN:IP?

Response: a.b.c.d

Set IP: :SYST:COMM:LAN:IP 192.168.1.200

EEPROM readback: :SYST:COMM:LAN:IP:EEP?

------------------------------------------------------------------------

# 5. Motor Commands

## Homing

Commands: :MOT:HOME:ALL :MOT:HOME:X :MOT:HOME:Y

Response: OK (after completion)

Smart homing behavior: - If endstop active at start → move +100 steps -
If still active → error - Otherwise normal negative homing - Position
set to 0

------------------------------------------------------------------------

## Absolute Move

Command: :MOT:X:GOTO `<position>`{=html} :MOT:Y:GOTO `<position>`{=html}

Constraints: - Must be homed - Position \>= 0 - Position \<= configured
max

Response: OK (after motion complete)

------------------------------------------------------------------------

## Relative Move

Command: :MOT:X:MOVE `<steps>`{=html} :MOT:Y:MOVE `<steps>`{=html}

Response: OK (after motion complete)

------------------------------------------------------------------------

## Position Query

Command: :MOT:X:POS? :MOT:Y:POS?

Response: `<signed integer>`{=html}

------------------------------------------------------------------------

## Axis Status

Command: :MOT:X:STAT? :MOT:Y:STAT?

Response: RUN/STOP,HOMED/UNHOMED,POS=`<value>`{=html}

------------------------------------------------------------------------

## Endstop Query

Command: :MOT:X:ENDSTOP? :MOT:Y:ENDSTOP?

Response: 1 = active 0 = inactive

------------------------------------------------------------------------

## Motors Present

Command: :MOT:PRES?

Response: 1 = connected 0 = not connected

------------------------------------------------------------------------

# 6. Error Codes

-350 TIMEOUT\
-360 HOME_FAIL_X\
-361 HOME_FAIL_Y\
-221 EEPROM_WRITE_FAIL\
-100 UNKNOWN_COMMAND

------------------------------------------------------------------------

# 7. Smart Homing Logic

1.  Check endstop.
2.  If active → move +100 steps.
3.  Re-check endstop.
4.  If still active → fail.
5.  Move negative until endstop triggers.
6.  Stop and set position=0.

------------------------------------------------------------------------

# 8. Limits

Configured in firmware:

X_MAX_STEPS\
Y_MAX_STEPS

Movement outside limits is rejected.

------------------------------------------------------------------------

# 9. Timing

Motion speed defined by: slow_sps (steps per second)

All motion is constant low speed.

------------------------------------------------------------------------

# 10. Example Session

\*IDN? :MOT:HOME:ALL :MOT:X:GOTO 7000 :MOT:X:POS? :MOT:X:GOTO 700
:MOT:X:POS?

------------------------------------------------------------------------

# 11. Electrical Interface Summary

Endstops: - Configurable active LOW/HIGH per axis - Interrupt-driven

Motors: - STEP/DIR - ENABLE support

------------------------------------------------------------------------

# 12. Firmware Behavior Guarantees

-   No OK before motion completes
-   No command loss during motion
-   Deterministic motion control
-   Explicit error reporting

------------------------------------------------------------------------

End of Document
