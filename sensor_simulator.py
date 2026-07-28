"""
sensor_simulator.py
----------------------------------------------------------------------
MODULE 1: Virtual IoT Sensor Simulator -- INTEGRATED with Aegis Watch

Simulates live sensor data for the 10 existing Aegis Watch machines
(M-01..M-10), each with a realistic, gradually-evolving fault profile
(not random noise), matching the EXACT feature space the trained AEGIS
XGBoost model expects:

    air_temp (K), process_temp (K), rpm, torque (Nm), tool_wear (min)

Every TICK_SECONDS, new readings are appended to the SAME `readings`
table utils/db_utils.py already uses -- so Home, My Machines, Machine
Detail, Reports and Live Monitoring all light up with real, continuously
changing data automatically, with no other changes needed on those pages.

Machine fault profiles (assigned to the 10 seeded machines, in id order):
    M-01  Healthy
    M-02  Gradual overheating (temperature drifting up)
    M-03  Rapid tool wear
    M-04  Cooling degradation           -> Heat Dissipation risk
    M-05  Motor overload                -> Power Failure risk (overloaded)
    M-06  Under-load drift              -> Power Failure risk (under-loaded)
    M-07  Healthy
    M-08  Torque fluctuation            -> intermittent Overstrain risk
    M-09  Severe tool wear              -> Tool Wear + Overstrain risk
    M-10  Random fault after a short delay (good for a live demo)

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

import math
import random
import time
import threading
from datetime import datetime

from db_manager import get_connection, init_db
from utils.db_utils import DEFAULT_READING_BY_TYPE

TICK_SECONDS = 3


def _noise(scale):
    return random.gauss(0, scale)


# ----------------------------------------------------------------------
# Machine profiles
# Each profile evolves its own internal tick counter so drift is gradual
# and repeatable-looking, not jumping randomly between calls. Every
# profile is seeded from the machine's ACTUAL latest reading in the DB
# (falling back to a type-based baseline) so the simulator picks up
# smoothly from wherever the seeded/demo data left off.
# ----------------------------------------------------------------------

class MachineProfile:
    """Default / healthy profile. Small noise + slow, normal tool wear only."""

    def __init__(self, machine_id, start_values):
        self.machine_id = machine_id
        self.tick = 0
        self.values = dict(start_values)

    def step(self):
        self.tick += 1
        v = self.values
        v["air_temp"] = v["air_temp"] + _noise(0.05)
        v["process_temp"] = v["process_temp"] + _noise(0.06)
        v["rpm"] = v["rpm"] + _noise(4)
        v["torque"] = v["torque"] + _noise(0.4)
        v["tool_wear"] = min(v["tool_wear"] + 0.03, 50)
        return dict(v)


class GradualOverheating(MachineProfile):
    """M-02 -- process temperature climbs faster than air temperature,
    narrowing the temp differential the model uses for Heat Dissipation risk."""

    def step(self):
        self.tick += 1
        v = self.values
        drift = min(self.tick * 0.015, 4.5)
        v["air_temp"] = v["air_temp"] + _noise(0.05) + drift * 0.2
        v["process_temp"] = v["process_temp"] + _noise(0.06) + drift * 0.5
        v["rpm"] = v["rpm"] + _noise(4)
        v["torque"] = v["torque"] + _noise(0.4)
        v["tool_wear"] = min(v["tool_wear"] + 0.03, 50)
        return dict(v)


class RapidToolWear(MachineProfile):
    """M-03 -- tool wear climbs steadily, dragging torque up with it
    (approaching the Overstrain / Tool Wear thresholds)."""

    def step(self):
        self.tick += 1
        v = self.values
        v["tool_wear"] = min(v["tool_wear"] + 0.6, 245)
        v["torque"] = v["torque"] + 0.03 + _noise(0.4)
        v["air_temp"] = v["air_temp"] + _noise(0.05)
        v["process_temp"] = v["process_temp"] + _noise(0.06)
        v["rpm"] = v["rpm"] + _noise(4)
        return dict(v)


class CoolingDegradation(MachineProfile):
    """M-04 -- classic Heat Dissipation Failure setup: the temp
    differential shrinks below ~8.6K while rpm sags below ~1380."""

    def step(self):
        self.tick += 1
        v = self.values
        drift = min(self.tick * 0.02, 6.0)
        v["air_temp"] = v["air_temp"] + drift * 0.4 + _noise(0.05)
        v["process_temp"] = v["process_temp"] + drift * 0.15 + _noise(0.06)
        v["rpm"] = max(1150, v["rpm"] - self.tick * 1.2 + _noise(4))
        v["torque"] = v["torque"] + _noise(0.4)
        v["tool_wear"] = min(v["tool_wear"] + 0.03, 50)
        return dict(v)


class MotorOverload(MachineProfile):
    """M-05 -- torque and rpm both climb, pushing power draw
    (torque * rpm) toward the Power Failure "overloaded" threshold."""

    def step(self):
        self.tick += 1
        v = self.values
        drift = min(self.tick * 0.08, 22)
        v["torque"] = v["torque"] + drift * 0.3 + _noise(0.5)
        v["rpm"] = v["rpm"] + self.tick * 1.5 + _noise(5)
        v["air_temp"] = v["air_temp"] + drift * 0.05 + _noise(0.05)
        v["process_temp"] = v["process_temp"] + drift * 0.08 + _noise(0.06)
        v["tool_wear"] = min(v["tool_wear"] + 0.03, 50)
        return dict(v)


class UnderloadDrift(MachineProfile):
    """M-06 -- torque and rpm both sag, pushing power draw toward the
    Power Failure "under-loaded" threshold."""

    def step(self):
        self.tick += 1
        v = self.values
        drift = min(self.tick * 0.05, 15)
        v["torque"] = max(2.0, v["torque"] - drift * 0.4 + _noise(0.4))
        v["rpm"] = max(900, v["rpm"] - self.tick * 1.0 + _noise(4))
        v["air_temp"] = v["air_temp"] + _noise(0.05)
        v["process_temp"] = v["process_temp"] + _noise(0.06)
        v["tool_wear"] = min(v["tool_wear"] + 0.03, 50)
        return dict(v)


class TorqueFluctuation(MachineProfile):
    """M-08 -- torque oscillates with growing amplitude (seal/coupling
    instability), intermittently spiking wear*torque past Overstrain."""

    def step(self):
        self.tick += 1
        v = self.values
        amplitude = min(self.tick * 0.1, 14)
        v["torque"] = max(2.0, v["torque"] + amplitude * math.sin(self.tick / 4) * 0.3 + _noise(0.4))
        v["air_temp"] = v["air_temp"] + _noise(0.05)
        v["process_temp"] = v["process_temp"] + _noise(0.06)
        v["rpm"] = v["rpm"] + _noise(4)
        v["tool_wear"] = min(v["tool_wear"] + 0.03, 50)
        return dict(v)


class SevereToolWear(MachineProfile):
    """M-09 -- fast-forward end-of-life cutting tool: wear ramps hard
    into both the Tool Wear Risk band and the Overstrain threshold."""

    def step(self):
        self.tick += 1
        v = self.values
        v["tool_wear"] = min(v["tool_wear"] + 1.1, 250)
        v["torque"] = v["torque"] + 0.05 + _noise(0.4)
        v["air_temp"] = v["air_temp"] + _noise(0.05)
        v["process_temp"] = v["process_temp"] + v["tool_wear"] * 0.002 + _noise(0.06)
        v["rpm"] = v["rpm"] + _noise(4)
        return dict(v)


class RandomFaultAfterDelay(MachineProfile):
    """M-10 -- runs healthy, then after a short random delay develops a
    randomly chosen fault. Good for demoing a LIVE state transition +
    alert firing mid-presentation instead of waiting the whole time."""

    FAULT_TYPES = ["overheat", "overload", "toolwear"]

    def __init__(self, machine_id, start_values):
        super().__init__(machine_id, start_values)
        # fault appears roughly 60-150s after start (20-50 ticks @ 3s)
        self.fault_start_tick = random.randint(20, 50)
        self.fault_type = random.choice(self.FAULT_TYPES)

    def step(self):
        self.tick += 1
        v = self.values
        v["air_temp"] = v["air_temp"] + _noise(0.05)
        v["process_temp"] = v["process_temp"] + _noise(0.06)
        v["rpm"] = v["rpm"] + _noise(4)
        v["torque"] = v["torque"] + _noise(0.4)
        v["tool_wear"] = min(v["tool_wear"] + 0.03, 50)

        if self.tick >= self.fault_start_tick:
            elapsed = self.tick - self.fault_start_tick
            drift = min(elapsed * 0.15, 20)
            if self.fault_type == "overheat":
                v["process_temp"] += drift * 0.6
                v["rpm"] = max(1150, v["rpm"] - elapsed * 1.0)
            elif self.fault_type == "overload":
                v["torque"] += drift * 0.5
                v["rpm"] += elapsed * 1.2
            elif self.fault_type == "toolwear":
                v["tool_wear"] = min(v["tool_wear"] + elapsed * 0.8, 250)
                v["torque"] += drift * 0.1

        return dict(v)


# Profiles assigned to the 10 existing seeded machines, in id order.
PROFILE_SEQUENCE = [
    MachineProfile,          # M-01 Healthy
    GradualOverheating,      # M-02
    RapidToolWear,           # M-03
    CoolingDegradation,      # M-04
    MotorOverload,           # M-05
    UnderloadDrift,          # M-06
    MachineProfile,          # M-07 Healthy
    TorqueFluctuation,       # M-08
    SevereToolWear,          # M-09
    RandomFaultAfterDelay,   # M-10
]


def _load_machine_ids_and_types():
    """Returns [(machine_id, machine_type), ...] in id order, for
    whatever machines currently exist (works even if machines were
    added/removed through the UI -- any machines beyond the original 10
    just cycle back through the profile list)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT id, machine_type FROM machines ORDER BY id").fetchall()
    return [(r["id"], r["machine_type"]) for r in rows]


def _load_start_values(machine_id, machine_type):
    """Seed each profile from the machine's actual latest reading (so the
    simulator continues smoothly from the seeded/demo data) -- falling
    back to the type-based baseline if the machine has no readings yet."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT air_temp, process_temp, rpm, torque, tool_wear
               FROM readings WHERE machine_id = ? ORDER BY reading_id DESC LIMIT 1""",
            (machine_id,),
        ).fetchone()
    if row:
        return dict(row)
    return dict(DEFAULT_READING_BY_TYPE[machine_type])


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
    machines = {}
    for i, (machine_id, machine_type) in enumerate(machine_ids):
        profile_cls = PROFILE_SEQUENCE[i % len(PROFILE_SEQUENCE)]
        start_values = _load_start_values(machine_id, machine_type)
        machines[machine_id] = profile_cls(machine_id, start_values)

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
