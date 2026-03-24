from __future__ import annotations

import cmath
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np


# -----------------------------------------------------------------------------
# Basic RF helpers
# -----------------------------------------------------------------------------

def gamma_from_z(z: complex, z0: float = 50.0) -> complex:
    return (z - z0) / (z + z0)


def z_from_gamma(gamma: complex, z0: float = 50.0) -> complex:
    denom = 1 - gamma
    if abs(denom) < 1e-15:
        raise ZeroDivisionError("Gamma is too close to 1; impedance tends toward infinity.")
    return z0 * (1 + gamma) / denom


def gamma_from_ri(ri: Sequence[float]) -> complex:
    return complex(float(ri[0]), float(ri[1]))


def ri_from_gamma(gamma: complex) -> List[float]:
    return [float(gamma.real), float(gamma.imag)]


def polar_text(gamma: complex) -> str:
    mag = abs(gamma)
    ang = math.degrees(cmath.phase(gamma))
    return f"{mag:.4f} ∠ {ang:.2f}°"


def z_text(z: complex) -> str:
    return f"{z.real:.4f} {'+' if z.imag >= 0 else '-'} j{abs(z.imag):.4f} Ω"


# -----------------------------------------------------------------------------
# Touchstone / S-parameter utilities (2-port only)
# -----------------------------------------------------------------------------

_FREQ_SCALE = {
    "HZ": 1.0,
    "KHZ": 1e3,
    "MHZ": 1e6,
    "GHZ": 1e9,
}


def _complex_from_format(a: float, b: float, data_format: str) -> complex:
    data_format = data_format.upper()
    if data_format == "RI":
        return complex(a, b)
    if data_format == "MA":
        return cmath.rect(a, math.radians(b))
    if data_format == "DB":
        return cmath.rect(10 ** (a / 20.0), math.radians(b))
    raise ValueError(f"Unsupported Touchstone format: {data_format}")


@dataclass
class S2PNetwork:
    freqs_hz: np.ndarray
    s: np.ndarray  # shape (N, 2, 2)
    z0: float = 50.0

    def interpolate(self, freq_hz: float) -> np.ndarray:
        f = self.freqs_hz
        if freq_hz < f[0] or freq_hz > f[-1]:
            raise ValueError(
                f"Frequency {freq_hz} Hz outside S2P range {f[0]} .. {f[-1]} Hz"
            )

        out = np.zeros((2, 2), dtype=complex)
        for i in range(2):
            for j in range(2):
                y = self.s[:, i, j]
                re = np.interp(freq_hz, f, y.real)
                im = np.interp(freq_hz, f, y.imag)
                out[i, j] = complex(re, im)
        return out

    @classmethod
    def from_touchstone(cls, path: str | Path, target_z0: float = 50.0) -> "S2PNetwork":
        path = Path(path)
        header = None
        raw: List[float] = []
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("!"):
                    continue
                if line.startswith("#"):
                    header = line
                    continue
                if "!" in line:
                    line = line.split("!", 1)[0].strip()
                if not line:
                    continue
                raw.extend(float(x) for x in line.split())

        if header is None:
            raise ValueError(f"Touchstone file {path} has no header line")

        parts = header[1:].strip().upper().split()
        # Expected e.g. '# GHZ S RI R 50'
        if len(parts) < 5 or parts[1] != "S":
            raise ValueError(f"Unsupported Touchstone header in {path}: {header}")
        freq_unit = parts[0]
        data_format = parts[2]
        if "R" not in parts:
            raise ValueError(f"Reference impedance missing in {path}: {header}")
        r_index = parts.index("R")
        file_z0 = float(parts[r_index + 1])
        scale = _FREQ_SCALE.get(freq_unit)
        if scale is None:
            raise ValueError(f"Unsupported frequency unit {freq_unit} in {path}")

        if len(raw) % 9 != 0:
            raise ValueError(
                f"Expected 9 numeric values per point in {path}; got {len(raw)} total values"
            )

        n = len(raw) // 9
        freqs = np.zeros(n, dtype=float)
        s = np.zeros((n, 2, 2), dtype=complex)
        for idx in range(n):
            vals = raw[idx * 9 : (idx + 1) * 9]
            freqs[idx] = vals[0] * scale
            s11 = _complex_from_format(vals[1], vals[2], data_format)
            s21 = _complex_from_format(vals[3], vals[4], data_format)
            s12 = _complex_from_format(vals[5], vals[6], data_format)
            s22 = _complex_from_format(vals[7], vals[8], data_format)
            s[idx, 0, 0] = s11
            s[idx, 1, 0] = s21
            s[idx, 0, 1] = s12
            s[idx, 1, 1] = s22

        net = cls(freqs_hz=freqs, s=s, z0=file_z0)
        if abs(file_z0 - target_z0) > 1e-12:
            net = net.renormalize(target_z0)
        return net

    def renormalize(self, new_z0: float) -> "S2PNetwork":
        if abs(self.z0 - new_z0) < 1e-12:
            return self
        z_all = np.zeros_like(self.s)
        for k in range(len(self.freqs_hz)):
            z_all[k] = s2z_2port(self.s[k], self.z0)
        s_new = np.zeros_like(self.s)
        for k in range(len(self.freqs_hz)):
            s_new[k] = z2s_2port(z_all[k], new_z0)
        return S2PNetwork(freqs_hz=self.freqs_hz.copy(), s=s_new, z0=new_z0)


def s2z_2port(s: np.ndarray, z0: float) -> np.ndarray:
    i = np.eye(2, dtype=complex)
    return z0 * (i + s) @ np.linalg.inv(i - s)


def z2s_2port(z: np.ndarray, z0: float) -> np.ndarray:
    i = np.eye(2, dtype=complex)
    zn = z / z0
    return (zn - i) @ np.linalg.inv(zn + i)


def s_to_abcd(s: np.ndarray, z0: float) -> np.ndarray:
    s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
    if abs(s21) < 1e-15:
        raise ZeroDivisionError("S21 too small for S->ABCD conversion")
    a = ((1 + s11) * (1 - s22) + s12 * s21) / (2 * s21)
    b = z0 * ((1 + s11) * (1 + s22) - s12 * s21) / (2 * s21)
    c = ((1 - s11) * (1 - s22) - s12 * s21) / (2 * s21 * z0)
    d = ((1 - s11) * (1 + s22) + s12 * s21) / (2 * s21)
    return np.array([[a, b], [c, d]], dtype=complex)


def abcd_to_s(abcd: np.ndarray, z0: float) -> np.ndarray:
    a, b, c, d = abcd[0, 0], abcd[0, 1], abcd[1, 0], abcd[1, 1]
    den = a + b / z0 + c * z0 + d
    if abs(den) < 1e-15:
        raise ZeroDivisionError("ABCD->S denominator too small")
    s11 = (a + b / z0 - c * z0 - d) / den
    s21 = 2 / den
    s12 = 2 * (a * d - b * c) / den
    s22 = (-a + b / z0 - c * z0 + d) / den
    return np.array([[s11, s12], [s21, s22]], dtype=complex)


def cascade_networks(networks: Sequence[S2PNetwork], z0: float = 50.0) -> S2PNetwork:
    if not networks:
        raise ValueError("At least one S2P network is required for cascade")

    common_freqs = networks[0].freqs_hz
    for net in networks[1:]:
        if len(net.freqs_hz) != len(common_freqs) or not np.allclose(net.freqs_hz, common_freqs):
            raise ValueError(
                "All S2P files must use the same frequency grid before cascading. "
                "Resample them first if needed."
            )

    out_s = np.zeros((len(common_freqs), 2, 2), dtype=complex)
    for k in range(len(common_freqs)):
        abcd = np.eye(2, dtype=complex)
        for net in networks:
            abcd = abcd @ s_to_abcd(net.s[k], z0)
        out_s[k] = abcd_to_s(abcd, z0)
    return S2PNetwork(freqs_hz=common_freqs.copy(), s=out_s, z0=z0)


# -----------------------------------------------------------------------------
# Embedding models
# -----------------------------------------------------------------------------

class Embedding:
    def gamma_dut_from_tuner(self, gamma_tuner: complex, freq_hz: float) -> complex:
        raise NotImplementedError

    def gamma_tuner_from_dut(self, gamma_dut: complex, freq_hz: float) -> complex:
        raise NotImplementedError

    def describe(self) -> dict:
        raise NotImplementedError


@dataclass
class IdentityEmbedding(Embedding):
    def gamma_dut_from_tuner(self, gamma_tuner: complex, freq_hz: float) -> complex:
        return gamma_tuner

    def gamma_tuner_from_dut(self, gamma_dut: complex, freq_hz: float) -> complex:
        return gamma_dut

    def describe(self) -> dict:
        return {"type": "identity"}


@dataclass
class PortExtensionEmbedding(Embedding):
    electrical_delay_ps: float
    one_way_loss_db: float = 0.0

    def _round_trip_factor(self, freq_hz: float) -> complex:
        delay_s = self.electrical_delay_ps * 1e-12
        phase = 4.0 * math.pi * freq_hz * delay_s
        amplitude = 10 ** (-(2.0 * self.one_way_loss_db) / 20.0)
        return amplitude * cmath.exp(-1j * phase)

    def gamma_dut_from_tuner(self, gamma_tuner: complex, freq_hz: float) -> complex:
        return gamma_tuner * self._round_trip_factor(freq_hz)

    def gamma_tuner_from_dut(self, gamma_dut: complex, freq_hz: float) -> complex:
        factor = self._round_trip_factor(freq_hz)
        if abs(factor) < 1e-15:
            raise ZeroDivisionError("Round-trip factor too small")
        return gamma_dut / factor

    def describe(self) -> dict:
        return {
            "type": "port_extension",
            "electrical_delay_ps": self.electrical_delay_ps,
            "one_way_loss_db": self.one_way_loss_db,
        }


@dataclass
class S2PEmbedding(Embedding):
    network: S2PNetwork
    files: List[str]

    def _s(self, freq_hz: float) -> np.ndarray:
        return self.network.interpolate(freq_hz)

    def gamma_dut_from_tuner(self, gamma_tuner: complex, freq_hz: float) -> complex:
        s = self._s(freq_hz)
        s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
        den = 1 - s22 * gamma_tuner
        if abs(den) < 1e-15:
            raise ZeroDivisionError("1 - S22*Gamma_tuner too small")
        return s11 + (s12 * s21 * gamma_tuner) / den

    def gamma_tuner_from_dut(self, gamma_dut: complex, freq_hz: float) -> complex:
        s = self._s(freq_hz)
        s11, s12, s21, s22 = s[0, 0], s[0, 1], s[1, 0], s[1, 1]
        num = gamma_dut - s11
        den = s12 * s21 + s22 * (gamma_dut - s11)
        if abs(den) < 1e-15:
            raise ZeroDivisionError("Inverse embedding denominator too small")
        return num / den

    def describe(self) -> dict:
        return {"type": "s2p", "files": self.files, "z0": self.network.z0}


# -----------------------------------------------------------------------------
# Tuner calibration and search
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class TunerState:
    x: int
    y: int

    @classmethod
    def from_dict(cls, d: dict) -> "TunerState":
        return cls(x=int(d["x"]), y=int(d["y"]))

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y}


class TunerCalibration:
    def __init__(self, z0: float, state_points: Dict[TunerState, List[Tuple[float, complex]]]):
        self.z0 = float(z0)
        self.state_points = state_points
        if not self.state_points:
            raise ValueError("Calibration contains no states")

    @classmethod
    def from_json(cls, path: str | Path) -> "TunerCalibration":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        z0 = float(data.get("z0", 50.0))
        states_data = data.get("states")
        if not isinstance(states_data, list) or not states_data:
            raise ValueError(f"Calibration file {path} must contain a non-empty 'states' list")

        state_points: Dict[TunerState, List[Tuple[float, complex]]] = {}
        for entry in states_data:
            state = TunerState.from_dict(entry)
            pts = entry.get("points")
            if not isinstance(pts, list) or not pts:
                raise ValueError(f"State {state} in {path} has no 'points'")
            point_list: List[Tuple[float, complex]] = []
            for p in pts:
                if "freq_hz" in p:
                    freq_hz = float(p["freq_hz"])
                elif "freq_mhz" in p:
                    freq_hz = float(p["freq_mhz"]) * 1e6
                else:
                    raise ValueError(f"Point in {path} must contain 'freq_hz' or 'freq_mhz'")
                if "gamma_ri" in p:
                    gamma = gamma_from_ri(p["gamma_ri"])
                elif "gamma_mag_ang_deg" in p:
                    mag, ang = p["gamma_mag_ang_deg"]
                    gamma = cmath.rect(float(mag), math.radians(float(ang)))
                else:
                    raise ValueError(
                        f"Point in {path} must contain 'gamma_ri' or 'gamma_mag_ang_deg'"
                    )
                point_list.append((freq_hz, gamma))
            point_list.sort(key=lambda t: t[0])
            state_points[state] = point_list
        return cls(z0=z0, state_points=state_points)

    def gamma_for_state(self, state: TunerState, freq_hz: float) -> complex:
        pts = self.state_points[state]
        freqs = np.array([f for f, _ in pts], dtype=float)
        if freq_hz < freqs[0] or freq_hz > freqs[-1]:
            raise ValueError(
                f"Frequency {freq_hz} Hz outside calibration range for state {state}: "
                f"{freqs[0]} .. {freqs[-1]} Hz"
            )
        gammas = np.array([g for _, g in pts], dtype=complex)
        re = np.interp(freq_hz, freqs, gammas.real)
        im = np.interp(freq_hz, freqs, gammas.imag)
        return complex(re, im)

    def states_at_freq(self, freq_hz: float) -> List[Tuple[TunerState, complex]]:
        return [(state, self.gamma_for_state(state, freq_hz)) for state in self.state_points.keys()]

    def nearest_state(self, freq_hz: float, gamma_target: complex) -> Tuple[TunerState, complex, float]:
        best = None
        for state, gamma in self.states_at_freq(freq_hz):
            err = abs(gamma - gamma_target)
            if best is None or err < best[2]:
                best = (state, gamma, err)
        assert best is not None
        return best


# -----------------------------------------------------------------------------
# Side and system objects
# -----------------------------------------------------------------------------

@dataclass
class SolveResult:
    side: str
    freq_hz: float
    z0: float
    requested_gamma_dut: complex
    required_gamma_tuner: complex
    chosen_state: TunerState
    chosen_gamma_tuner: complex
    actual_gamma_dut: complex
    actual_z_dut: complex
    gamma_error: float
    embedding: dict

    def as_dict(self) -> dict:
        return {
            "side": self.side,
            "freq_hz": self.freq_hz,
            "freq_mhz": self.freq_hz / 1e6,
            "z0": self.z0,
            "requested_gamma_dut": ri_from_gamma(self.requested_gamma_dut),
            "required_gamma_tuner": ri_from_gamma(self.required_gamma_tuner),
            "chosen_state": self.chosen_state.as_dict(),
            "chosen_gamma_tuner": ri_from_gamma(self.chosen_gamma_tuner),
            "actual_gamma_dut": ri_from_gamma(self.actual_gamma_dut),
            "actual_z_dut_ohm": [float(self.actual_z_dut.real), float(self.actual_z_dut.imag)],
            "gamma_error_abs": float(self.gamma_error),
            "embedding": self.embedding,
        }


class TunerSide:
    def __init__(self, name: str, calibration: TunerCalibration, embedding: Embedding, z0: float):
        self.name = name
        self.calibration = calibration
        self.embedding = embedding
        self.z0 = float(z0)

    def solve_for_gamma_dut(self, freq_hz: float, gamma_target_dut: complex) -> SolveResult:
        gamma_required_tuner = self.embedding.gamma_tuner_from_dut(gamma_target_dut, freq_hz)
        chosen_state, chosen_gamma_tuner, gamma_error_tuner = self.calibration.nearest_state(
            freq_hz, gamma_required_tuner
        )
        actual_gamma_dut = self.embedding.gamma_dut_from_tuner(chosen_gamma_tuner, freq_hz)
        actual_z_dut = z_from_gamma(actual_gamma_dut, self.z0)
        return SolveResult(
            side=self.name,
            freq_hz=freq_hz,
            z0=self.z0,
            requested_gamma_dut=gamma_target_dut,
            required_gamma_tuner=gamma_required_tuner,
            chosen_state=chosen_state,
            chosen_gamma_tuner=chosen_gamma_tuner,
            actual_gamma_dut=actual_gamma_dut,
            actual_z_dut=actual_z_dut,
            gamma_error=abs(actual_gamma_dut - gamma_target_dut),
            embedding=self.embedding.describe(),
        )

    def solve_for_z_dut(self, freq_hz: float, z_target: complex) -> SolveResult:
        return self.solve_for_gamma_dut(freq_hz, gamma_from_z(z_target, self.z0))

    def dut_impedance_from_state(self, freq_hz: float, state: TunerState) -> dict:
        gamma_tuner = self.calibration.gamma_for_state(state, freq_hz)
        gamma_dut = self.embedding.gamma_dut_from_tuner(gamma_tuner, freq_hz)
        z_dut = z_from_gamma(gamma_dut, self.z0)
        return {
            "side": self.name,
            "freq_hz": freq_hz,
            "freq_mhz": freq_hz / 1e6,
            "state": state.as_dict(),
            "gamma_tuner": ri_from_gamma(gamma_tuner),
            "gamma_dut": ri_from_gamma(gamma_dut),
            "z_dut_ohm": [float(z_dut.real), float(z_dut.imag)],
            "embedding": self.embedding.describe(),
        }


class LoadPullSystem:
    def __init__(self, z0: float, source: TunerSide | None, load: TunerSide | None):
        self.z0 = float(z0)
        self.source = source
        self.load = load

    @classmethod
    def from_json(cls, config_path: str | Path) -> "LoadPullSystem":
        config_path = Path(config_path)
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        z0 = float(cfg.get("z0", 50.0))
        base_dir = config_path.parent

        def build_side(name: str) -> TunerSide | None:
            s = cfg.get(name)
            if s is None:
                return None
            cal_path = base_dir / s["calibration"]
            calibration = TunerCalibration.from_json(cal_path)
            embedding_cfg = s.get("embedding", {"type": "identity"})
            embedding = build_embedding(embedding_cfg, base_dir=base_dir, z0=z0)
            return TunerSide(name=name, calibration=calibration, embedding=embedding, z0=z0)

        return cls(z0=z0, source=build_side("source"), load=build_side("load"))

    def side(self, name: str) -> TunerSide:
        if name == "source" and self.source is not None:
            return self.source
        if name == "load" and self.load is not None:
            return self.load
        raise KeyError(f"Side '{name}' is not configured")


def build_embedding(cfg: dict, base_dir: Path, z0: float) -> Embedding:
    etype = cfg.get("type", "identity")
    if etype == "identity":
        return IdentityEmbedding()
    if etype == "port_extension":
        return PortExtensionEmbedding(
            electrical_delay_ps=float(cfg["electrical_delay_ps"]),
            one_way_loss_db=float(cfg.get("one_way_loss_db", 0.0)),
        )
    if etype in ("s2p", "cascade_s2p"):
        files = cfg.get("files") or []
        if not files:
            raise ValueError("S2P embedding requires a non-empty 'files' list")
        networks = [S2PNetwork.from_touchstone(base_dir / p, target_z0=z0) for p in files]
        network = networks[0] if len(networks) == 1 else cascade_networks(networks, z0=z0)
        return S2PEmbedding(network=network, files=list(files))
    raise ValueError(f"Unknown embedding type: {etype}")


# -----------------------------------------------------------------------------
# Convenience CLI-style demo helper
# -----------------------------------------------------------------------------

def summarize_result(result: SolveResult) -> str:
    lines = [
        f"Side: {result.side}",
        f"Frequency: {result.freq_hz/1e6:.6f} MHz",
        f"Requested Γ_DUT: {polar_text(result.requested_gamma_dut)}",
        f"Required Γ_tuner: {polar_text(result.required_gamma_tuner)}",
        f"Chosen state: x={result.chosen_state.x}, y={result.chosen_state.y}",
        f"Chosen Γ_tuner: {polar_text(result.chosen_gamma_tuner)}",
        f"Actual Γ_DUT: {polar_text(result.actual_gamma_dut)}",
        f"Actual Z_DUT: {z_text(result.actual_z_dut)}",
        f"|Γ_error|: {result.gamma_error:.6f}",
        f"Embedding: {json.dumps(result.embedding, ensure_ascii=False)}",
    ]
    return "\n".join(lines)
