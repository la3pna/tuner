import json
from pathlib import Path

from load_pull_embedding import LoadPullSystem, TunerState, summarize_result

base = Path(__file__).resolve().parent
system = LoadPullSystem.from_json(base / "example_system_config.json")

freq_hz = 433e6
z_target = complex(12.0, 18.0)

result_source = system.side("source").solve_for_z_dut(freq_hz, z_target)
result_load = system.side("load").solve_for_z_dut(freq_hz, z_target)

print("=== SOURCE SIDE ===")
print(summarize_result(result_source))
print()
print("=== LOAD SIDE ===")
print(summarize_result(result_load))
print()

known_state = TunerState(x=12000, y=850)
check = system.side("load").dut_impedance_from_state(freq_hz, known_state)
print("=== IMPEDANCE FROM KNOWN TUNER STATE ===")
print(json.dumps(check, indent=2))
