"""
sensor_simulator.py
----------------------------------------------------------------------
MODULE 1: Virtual IoT Sensor Simulator -- INTEGRATED with Aegis Watch

Simulates live sensor data for the 10 existing Aegis Watch machines
(M-01..M-10), matching the EXACT feature space the trained AEGIS XGBoost
model expects:

    air_temp (K), process_temp (K), rpm, torque (Nm), tool_wear (min)

Every TICK_SECONDS, new readings are appended to the SAME `readings`
table utils/db_utils.py already uses -- so Home, My Machines, Machine
Detail, Reports and Live Monitoring all light up with real, continuously
changing data automatically, with no other changes needed on those pages.

DESIGN: HEALTH-% FIRST, SENSORS DERIVED
----------------------------------------------------------------------
The rest of the app never stores a health score -- it always recomputes
it live from the latest raw sensor reading via
utils.model_utils.predict_machine_health() (the trained XGBoost model).
That means the only way to *guarantee* a machine's displayed health-%
lands in a specific band is to drive the simulator by the health target
first, then work backwards to sensor values that the model itself will
score at that target -- rather than hand-tuning temp/rpm/torque/wear
drift and hoping it lands in the right place.

So at startup, for each machine TYPE (L/M/H) we build a calibration
table: 150,000 randomly sampled sensor combinations, scored through the
REAL model in one batched call and sorted by health. That gives us an
empirical health_score -> sensor-values lookup we can query instantly
at every tick: "I want health X% right now" -> "here are real sensor
values that make the model say X%". (A straight-line interpolation
between a healthy and a bad baseline was tried first, but this model is
nearly a step function -- health flips ~100% -> ~0% between two
adjacent points on that line -- so random sampling across the whole
space was needed to find real mid-range examples.) This is a one-time
cost (~2 seconds total at startup, cached per type), not a per-tick cost.

MACHINE BEHAVIOR (10 machines, in id order)
----------------------------------------------------------------------
    M-01  Healthy -- flat ~99% (near-constant, tiny wobble only)
    M-02  Healthy -- randomly fluctuates 90-100%, never below 90
    M-03  At-risk -- randomly fluctuates 60-80%
    M-04  Healthy -- randomly fluctuates 90-100%, never below 90
    M-05  Healthy -- randomly fluctuates 90-100%, never below 90
    M-06  At-risk -- sawtooth 0-50%: climbs 0 -> 50, then falls back
                     50 -> 0, repeats forever (never negative)
    M-07  Healthy -- flat ~99% (near-constant, tiny wobble only)
    M-08  Healthy -- randomly fluctuates 90-100%, never below 90
    M-09  At-risk -- sawtooth 0-50%: climbs 0 -> 50, then falls back
                     50 -> 0, repeats forever (never negative)
    M-10  Healthy -- flat ~99% (near-constant, tiny wobble only)

    -> 7 healthy machines total (3 flat-99, 4 fluctuating 90-100)
    -> 3 at-risk machines total (1 fluctuating 60-80, 2 sawtoothing 0-50)

Every target is hard-clamped to its band every tick, and the derived
sensor values pass through the same hard safety-net bounds as before
(temps 290-335K, RPM 800-3000, torque 1-90, wear 0.5-260), so this is
safe to leave running indefinitely on a long-lived shared link.

HOW TO RUN
----------
Standalone (separate terminal, good for a hackathon demo):
    python sensor_simulator.py

Inside the Streamlit app (background thread, non-blocking) -- already
wired up in app.py:
    from sensor_simulator import start_simulator_thread
    if "sim_started" not in st.session_state:
        start_simulator_thread()
        st.session_state.sim_started = True
----------------------------------------------------------------------
"""

import random
import time
import threading
from datetime import datetime

import numpy as np
import pandas as pd

from db_manager import get_connection, init_db
from utils.model_utils import model as _ml_model, TYPE_MAPPING, FEATURE_COLS

TICK_SECONDS = 3

# Hard safety-net bounds -- applied to every derived reading, every tick,
# no matter what the calibration table produced.
BOUNDS = {
    "air_temp": (290.0, 335.0),
    "process_temp": (290.0, 335.0),
    "rpm": (800.0, 3000.0),
    "torque": (1.0, 90.0),
    "tool_wear": (0.5, 260.0),
}


def _noise(scale):
    return random.gauss(0, scale)


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _apply_bounds(values):
    for key, (lo, hi) in BOUNDS.items():
        values[key] = _clamp(values[key], lo, hi)
    return values


# ----------------------------------------------------------------------
# Calibration: health_score -> sensor-values lookup per machine TYPE
# (L/M/H), built once (lazily, on first use).
#
# NOTE: the trained XGBoost classifier on this dataset turns out to be
# extremely confident almost everywhere -- walking a straight line
# between a "healthy" and a "bad" sensor baseline crosses the decision
# boundary in a single step (health jumps ~100% -> ~0% between two
# adjacent samples), so linear interpolation cannot produce reliable
# mid-range values. Instead we randomly sample a large number of
# plausible sensor combinations, score ALL of them through the real
# model in one batched call (fast), and keep the whole table sorted by
# health. Rare bands (e.g. 60-80%) are thinner but still have thousands
# of real samples, which is what makes "wander randomly within 60-80%"
# actually possible instead of chasing an unstable knife-edge.
# ----------------------------------------------------------------------

_CALIBRATION_SAMPLES = 150_000
_calibration_cache = {}


def _score_batch(type_letter, air_temp, process_temp, rpm, torque, tool_wear):
    type_code = TYPE_MAPPING[type_letter]
    temp_diff = process_temp - air_temp
    power_w = torque * rpm * (2 * np.pi / 60)
    wear_torque = tool_wear * torque
    heat_load = process_temp * torque
    df = pd.DataFrame({
        "Type": type_code,
        "Air_temperature_K": air_temp,
        "Process_temperature_K": process_temp,
        "Rotational_speed_rpm": rpm,
        "Torque_Nm": torque,
        "Tool_wear_min": tool_wear,
        "Temp_Difference": temp_diff,
        "Power_W": power_w,
        "Wear_Torque": wear_torque,
        "Heat_Load": heat_load,
    })[FEATURE_COLS]
    failure_prob = _ml_model.predict_proba(df)[:, 1] * 100.0
    return 100.0 - failure_prob


def _build_calibration_table(type_letter, n=_CALIBRATION_SAMPLES, seed=None):
    rng = np.random.default_rng(seed)
    air_temp = rng.uniform(294.0, 304.0, n)
    process_temp = air_temp + rng.uniform(0.0, 15.0, n)
    rpm = rng.uniform(900.0, 2800.0, n)
    torque = rng.uniform(15.0, 85.0, n)
    tool_wear = rng.uniform(0.0, 250.0, n)

    health = _score_batch(type_letter, air_temp, process_temp, rpm, torque, tool_wear)

    order = np.argsort(health)
    return {
        "health": health[order],
        "air_temp": air_temp[order],
        "process_temp": process_temp[order],
        "rpm": rpm[order],
        "torque": torque[order],
        "tool_wear": tool_wear[order],
    }


def _get_calibration(type_letter):
    if type_letter not in _calibration_cache:
        _calibration_cache[type_letter] = _build_calibration_table(type_letter)
    return _calibration_cache[type_letter]


def _sensor_values_for_health(type_letter, target_health):
    table = _get_calibration(type_letter)
    target_health = _clamp(target_health, 0.0, 100.0)

    n = len(table["health"])
    idx = int(np.searchsorted(table["health"], target_health))
    # Jitter within a small neighbourhood of equally-good matches so the
    # same target health doesn't always return byte-identical sensor
    # values (keeps the live telemetry looking like real noisy sensors).
    window = 25
    lo = max(0, idx - window)
    hi = min(n - 1, idx + window)
    pick = random.randint(lo, hi)

    values = {
        "air_temp": float(table["air_temp"][pick]),
        "process_temp": float(table["process_temp"][pick]),
        "rpm": float(table["rpm"][pick]),
        "torque": float(table["torque"][pick]),
        "tool_wear": float(table["tool_wear"][pick]),
    }
    return _apply_bounds(values)


# ----------------------------------------------------------------------
# Health-target profiles. Each one only decides WHAT health-% the
# machine should read this tick (mean-reverting / bouncing within its
# band) -- the actual sensor numbers are derived via the calibration
# table above so the app's own model scores them back to that target.
# ----------------------------------------------------------------------

class HealthTargetProfile:
    def __init__(self, machine_id, type_letter, start_health):
        self.machine_id = machine_id
        self.type_letter = type_letter
        self.tick = 0
        self.target_health = start_health

    def _next_target(self):
        raise NotImplementedError

    def step(self):
        self.tick += 1
        self.target_health = self._next_target()
        return _sensor_values_for_health(self.type_letter, self.target_health)


class FlatHealth99(HealthTargetProfile):
    """Healthy machine that always reads ~99% -- tiny wobble only."""

    LOW, HIGH = 98.5, 99.5

    def __init__(self, machine_id, type_letter):
        super().__init__(machine_id, type_letter, start_health=99.0)

    def _next_target(self):
        return _clamp(99.0 + _noise(0.15), self.LOW, self.HIGH)


class Fluctuate90to100(HealthTargetProfile):
    """Healthy machine that wanders randomly within 90-100%, mean-
    reverting toward the center so it never gets stuck at an edge."""

    LOW, HIGH, CENTER = 90.0, 100.0, 95.0

    def __init__(self, machine_id, type_letter):
        super().__init__(machine_id, type_letter, start_health=random.uniform(90.0, 100.0))

    def _next_target(self):
        h = self.target_health + _noise(1.1) + (self.CENTER - self.target_health) * 0.04
        return _clamp(h, self.LOW, self.HIGH)


class Fluctuate60to80(HealthTargetProfile):
    """At-risk machine that wanders randomly within 60-80%, mean-
    reverting toward the center so it never gets stuck at an edge."""

    LOW, HIGH, CENTER = 60.0, 80.0, 70.0

    def __init__(self, machine_id, type_letter):
        super().__init__(machine_id, type_letter, start_health=random.uniform(60.0, 80.0))

    def _next_target(self):
        h = self.target_health + _noise(1.1) + (self.CENTER - self.target_health) * 0.04
        return _clamp(h, self.LOW, self.HIGH)


class Sawtooth0to50(HealthTargetProfile):
    """At-risk machine that climbs 0 -> 50 then falls back 50 -> 0,
    repeating forever -- a genuine sawtooth/triangle wave, always
    bouncing back up the moment it touches 0, never going negative."""

    LOW, HIGH = 0.0, 50.0

    def __init__(self, machine_id, type_letter):
        super().__init__(machine_id, type_letter, start_health=random.uniform(0.0, 50.0))
        self.direction = random.choice([1, -1])

    def _next_target(self):
        step = 0.8 + abs(_noise(1.0))
        h = self.target_health + self.direction * step
        if h >= self.HIGH:
            h = self.HIGH
            self.direction = -1
        elif h <= self.LOW:
            h = self.LOW
            self.direction = 1
        return h


# Profiles assigned to the 10 existing seeded machines, in id order.
# 3x flat-99, 4x fluctuate-90-100 => 7 healthy machines.
# 1x fluctuate-60-80, 2x sawtooth-0-50 => 3 at-risk machines.
PROFILE_SEQUENCE = [
    FlatHealth99,          # M-01
    Fluctuate90to100,      # M-02
    Fluctuate60to80,       # M-03
    Fluctuate90to100,      # M-04
    Fluctuate90to100,      # M-05
    Sawtooth0to50,         # M-06
    FlatHealth99,          # M-07
    Fluctuate90to100,      # M-08
    Sawtooth0to50,         # M-09
    FlatHealth99,          # M-10
]


def _load_machine_ids_and_types():
    """Returns [(machine_id, machine_type), ...] in id order, for
    whatever machines currently exist (works even if machines were
    added/removed through the UI -- any machines beyond the original 10
    just cycle back through the profile list)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id, machine_type FROM machines ORDER BY id").fetchall()
    return [(r["id"], r["machine_type"]) for r in rows]


def _insert_reading(machine_id, values):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO readings
               (machine_id, timestamp, air_temp, process_temp, rpm, torque, tool_wear)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                machine_id,
                datetime.now().isoformat(),
                values["air_temp"],
                values["process_temp"],
                values["rpm"],
                values["torque"],
                values["tool_wear"],
            ),
        )


def run_simulator(stop_event: threading.Event = None):
    """Main loop: generates + inserts readings for every machine every
    TICK_SECONDS. Pass a threading.Event to allow graceful stop."""
    init_db()
    machine_ids = _load_machine_ids_and_types()

    # Pre-build the calibration table for every distinct machine type up
    # front, so the first few ticks aren't slow.
    for _, machine_type in machine_ids:
        _get_calibration(machine_type)

    machines = {}
    for i, (machine_id, machine_type) in enumerate(machine_ids):
        profile_cls = PROFILE_SEQUENCE[i % len(PROFILE_SEQUENCE)]
        machines[machine_id] = profile_cls(machine_id, machine_type)

    print(f"[sensor_simulator] Simulating {len(machines)} machines every {TICK_SECONDS}s ...")

    while stop_event is None or not stop_event.is_set():
        for machine_id, profile in machines.items():
            values = profile.step()
            _insert_reading(machine_id, values)
        time.sleep(TICK_SECONDS)


def start_simulator_thread():
    """Run the simulator in a background daemon thread so it doesn't
    block the Streamlit app. Returns (thread, stop_event) -- call
    stop_event.set() if you ever need to stop it."""
    stop_event = threading.Event()
    thread = threading.Thread(target=run_simulator, args=(stop_event,), daemon=True)
    thread.start()
    return thread, stop_event


if __name__ == "__main__":
    run_simulator()
