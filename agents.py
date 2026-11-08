from math import asin, cos, radians, sin, sqrt


def distance_km(first, second):
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    value = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(min(1, max(0, value))))


class Agent:
    def __init__(self, name, system):
        self.name = name
        self.system = system
        self.status = "Idle"

    def send(self, receiver, performative, content):
        self.system.send(self.name, receiver, performative, content)


class PressureMonitor(Agent):
    def receive(self, message):
        data = message["content"]
        if message["performative"] == "REQUEST":
            self.status = "Checking pressure"
            self.low = data["Pressure"] < self.system.pressure_limit
            self.send("Usage Monitor", "REQUEST", {"reading": data, "pressure_low": self.low})
        elif message["performative"] == "INFORM":
            if self.low and data["flow_high"]:
                self.status = "Leak confirmed"
                self.system.detected = True
                self.send("Leak Locator", "REQUEST", self.system.reading)
            else:
                self.status = "Single anomaly" if self.low or data["flow_high"] else "Normal"
                self.system.result = "Unconfirmed anomaly" if self.low or data["flow_high"] else "Normal reading"


class UsageMonitor(Agent):
    def receive(self, message):
        data = message["content"]
        high = data["reading"]["Flow_Rate"] > self.system.flow_limit
        self.status = "High flow" if high else "Normal flow"
        self.send("Pressure Monitor", "INFORM", {"flow_high": high, "pressure_low": data["pressure_low"]})


class LeakLocator(Agent):
    def receive(self, message):
        reading = message["content"]
        self.status = "Location identified"
        self.system.location = {
            "area": "/".join(reading[key] for key in ("Zone", "Block", "Pipe")),
            "latitude": reading["Latitude"], "longitude": reading["Longitude"],
            "major": reading["Pressure"] <= self.system.major_limit,
        }
        self.send("Dispatch", "REQUEST", self.system.location)


class Dispatch(Agent):
    def __init__(self, name, system):
        super().__init__(name, system)
        self.offers = {}
        self.responses = set()
        self.approved = False

    def collect_offers(self):
        self.offers.clear()
        self.responses.clear()
        self.status = "Requesting teams"
        for team in self.system.teams:
            self.send(team.name, "CFP", self.system.location)

    def receive(self, message):
        action = message["performative"]
        data = message["content"]
        if action == "REQUEST":
            if data["major"]:
                self.status = "Waiting for approval"
                self.system.waiting_approval = True
                self.system.result = "Major leak: supervisor approval required"
            else:
                self.collect_offers()
        elif message["sender"] == "Supervisor":
            self.system.waiting_approval = False
            if action == "ACCEPT":
                self.approved = True
                self.collect_offers()
            else:
                self.status = "Rejected by supervisor"
                self.system.result = "Dispatch rejected; leak still unresolved"
        elif action in ("PROPOSE", "REFUSE"):
            self.responses.add(message["sender"])
            if action == "PROPOSE":
                self.offers[message["sender"]] = data["distance_km"]
            if len(self.responses) == len(self.system.teams):
                if not self.offers:
                    self.status = "No available team"
                    self.system.result = "No available team; leak still unresolved"
                    return
                selected = min(self.offers, key=lambda name: (self.offers[name], name))
                self.system.assigned_team = selected
                self.status = f"Assigned {selected}"
                self.send(selected, "ACCEPT", self.system.location)
                for name in self.offers:
                    if name != selected:
                        self.send(name, "REFUSE", {"reason": "A closer team was selected"})
        elif action == "INFORM" and data.get("state") in ("failed", "unavailable"):
            self.status = "Reassigning task"
            self.system.result = "Team failure: finding another team" if data["state"] == "failed" else "Team unavailable: finding another team"
            self.collect_offers()
        elif action == "INFORM" and data.get("state") == "completed":
            self.status = "Repair completed"
            self.system.result = f"Repair completed by {message['sender']}"
            self.system.repaired = True


class RepairTeam(Agent):
    def __init__(self, name, system, position, fail_on_accept=False, available=True):
        super().__init__(name, system)
        self.position = position
        self.available = available
        self.failed = False
        self.fail_on_accept = fail_on_accept
        self.remaining = 0
        self.target = None
        self.status = "Available" if available else "Unavailable"

    def receive(self, message):
        action = message["performative"]
        location = message["content"]
        if action == "CFP":
            if not self.available or self.failed:
                self.send("Dispatch", "REFUSE", {"reason": self.status})
            else:
                distance = distance_km(self.position, (location["latitude"], location["longitude"]))
                self.status = "Offer sent"
                self.send("Dispatch", "PROPOSE", {"distance_km": distance})
        elif action == "ACCEPT":
            reserve = getattr(self.system, "reserve_team", None)
            if reserve and not reserve(self.name):
                self.send("Dispatch", "INFORM", {"state": "unavailable"})
                return
            if self.fail_on_accept:
                self.failed = True
                self.available = False
                self.status = "Failed"
                self.send("Dispatch", "INFORM", {"state": "failed"})
            else:
                self.available = False
                self.target = (location["latitude"], location["longitude"])
                self.remaining = self.system.repair_ticks
                self.status = "Repairing"
                self.send("Dispatch", "INFORM", {"state": "accepted"})
        elif action == "REFUSE" and self.available:
            self.status = "Available"

    def tick(self):
        if self.remaining:
            self.remaining -= 1
            if self.remaining == 0:
                self.available = True
                self.position = self.target
                self.status = "Available"
                self.send("Dispatch", "INFORM", {"state": "completed"})
