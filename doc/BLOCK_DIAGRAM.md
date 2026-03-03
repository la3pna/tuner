# SYSTEM BLOCK DIAGRAM

                +-------------------+
                |   CLI / Scripts   |
                | (Load Pull / NF)  |
                +---------+---------+
                          |
                          | TCP JSON (53190/53191)
                          v
                +-------------------+
                |  tuner_service.py |
                +---------+---------+
                          |
        +-----------------+------------------+
        |                                    |
        v                                    v
+---------------+                   +----------------+
| Tuner Backend |                   |  VNA Backend   |
| TCP / Serial  |                   | LibreVNA SCPI  |
+-------+-------+                   +--------+-------+
        |                                    |
        v                                    v
   +----------+                       +--------------+
   |  Tuner   |                       |  LibreVNA   |
   | Hardware |                       |  Hardware   |
   +----------+                       +--------------+

Calibration Files (CSV per frequency)
Stored in: cal/

Lookup Engine selects X/Y based on Γ target and insertion loss.
