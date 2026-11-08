from collections import deque
from time import perf_counter

from agents import Dispatch, LeakLocator, PressureMonitor, RepairTeam, UsageMonitor


class Simulation:
    def __init__(self, reading, pressure_limit=54.0, flow_limit=90.0,
                 major_limit=40.0, repair_ticks=8, fail_first=False, unavailable=False):
        if not 0 <= major_limit < pressure_limit or flow_limit < 0 or repair_ticks < 1:
            raise ValueError("Invalid simulation settings")
        self.reading = dict(reading)
        self.pressure_limit = pressure_limit
        self.flow_limit = flow_limit
        self.major_limit = major_limit
        self.repair_ticks = repair_ticks
        self.queue = deque()
        self.messages = []
        self.traces = []
        self.conversation_id = "reading-1"
        self.step_number = 0
        self.detected = False
        self.repaired = False
        self.waiting_approval = False
        self.location = None
        self.assigned_team = None
        self.result = "Ready"
        lat, lon = reading["Latitude"], reading["Longitude"]
        # Team positions are simulated near this reading.
        self.teams = [
            RepairTeam("Team A", self, (lat + 0.002, lon), fail_first, not unavailable),
            RepairTeam("Team B", self, (lat + 0.04, lon + 0.03), available=not unavailable),
        ]
        agents = [PressureMonitor("Pressure Monitor", self), UsageMonitor("Usage Monitor", self),
                  LeakLocator("Leak Locator", self), Dispatch("Dispatch", self), *self.teams]
        self.agents = {agent.name: agent for agent in agents}

    def send(self, sender, receiver, performative, content):
        message = {"step": self.step_number, "sender": sender, "receiver": receiver,
                   "performative": performative, "ontology": "water-leak",
                   "conversation_id": self.conversation_id, "content": dict(content), "delivered": False}
        self.messages.append(message)
        self.queue.append(message)

    def start(self):
        if self.result != "Ready":
            return
        self.result = "Monitoring"
        self.send("Sensors", "Pressure Monitor", "REQUEST", self.reading)

    def step(self):
        self.step_number += 1
        for team in self.teams:
            if team.remaining:
                self.call_agent(team.name, "repair_tick", team.tick)
        if self.queue:
            message = self.queue.popleft()
            message["delivered"] = True
            self.call_agent(message["receiver"], message["performative"],
                            lambda: self.agents[message["receiver"]].receive(message))

    def call_agent(self, name, action, callback):
        start = perf_counter()
        error = ""
        try:
            callback()
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
            raise
        finally:
            self.traces.append({"agent": name, "action": action,
                                "duration_ms": (perf_counter() - start) * 1000,
                                "error": error, "step": self.step_number})

    def approve(self, accepted):
        if self.waiting_approval:
            self.waiting_approval = False
            self.send("Supervisor", "Dispatch", "ACCEPT" if accepted else "REFUSE", {})

    @property
    def active(self):
        return bool(self.queue or any(team.remaining for team in self.teams))


def scenario_reading(readings, scenario):
    for index, reading in enumerate(readings):
        pressure, flow = reading["Pressure"], reading["Flow_Rate"]
        matches = {
            "Normal": pressure >= 54 and flow <= 90,
            "Minor leak": 40 < pressure < 54 and flow > 90,
            "Major leak + team failure": pressure <= 40 and flow > 90,
        }
        if matches[scenario]:
            return index, dict(reading)
    raise ValueError(f"No matching reading for {scenario}")


def evaluate(readings, labels, pressure_limit=54, flow_limit=90):
    if not readings or len(readings) != len(labels):
        raise ValueError("Readings and labels must have the same non-zero length")
    tp = fp = tn = fn = 0
    for reading, label in zip(readings, labels):
        predicted = reading["Pressure"] < pressure_limit and reading["Flow_Rate"] > flow_limit
        tp += predicted and label == 1
        fp += predicted and label == 0
        tn += not predicted and label == 0
        fn += not predicted and label == 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "accuracy": (tp + tn) / len(labels), "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
