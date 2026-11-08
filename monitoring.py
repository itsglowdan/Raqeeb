from collections import deque

from agents import distance_km
from simulation import Simulation


CITIES = {
    "Zone_1": {"name": "Riyadh", "latitude": 24.7136, "longitude": 46.6753},
    "Zone_2": {"name": "Madinah", "latitude": 24.4672, "longitude": 39.6024},
    "Zone_3": {"name": "Abha", "latitude": 18.2164, "longitude": 42.5053},
    "Zone_4": {"name": "Makkah", "latitude": 21.3891, "longitude": 39.8579},
    "Zone_5": {"name": "Dammam", "latitude": 26.4207, "longitude": 50.0888},
}


def display_reading(reading):
    city = CITIES[reading["Zone"]]
    block = int(reading["Block"].split("_")[-1])
    pipe = int(reading["Pipe"].split("_")[-1])
    return dict(reading, Latitude=city["latitude"] + (block - 3) * 0.012,
                Longitude=city["longitude"] + (pipe - 3) * 0.012)


class ContinuousMonitor:
    def __init__(self, readings, start_index=0, interval=2.0, pressure_limit=54,
                 flow_limit=90, major_limit=40, repair_ticks=8, fail_first=False,
                 unavailable=False, base_cost=250.0, cost_per_km=5.0):
        if not readings or interval < 0.5 or base_cost < 0 or cost_per_km < 0:
            raise ValueError("Invalid monitoring settings")
        self.readings = readings
        self.start_index = start_index % len(readings)
        self.interval_ticks = max(1, round(interval / 0.5))
        self.settings = dict(pressure_limit=pressure_limit, flow_limit=flow_limit,
                             major_limit=major_limit, repair_ticks=repair_ticks)
        self.fail_first = fail_first
        self.unavailable = unavailable
        self.base_cost = base_cost
        self.cost_per_km = cost_per_km
        self.tick = 0
        self.observed = 0
        self.confirmed = 0
        self.completed = 0
        self.total_cost = 0.0
        self.failure_count = 0
        self.error_count = 0
        self.dropped = 0
        self.running = False
        self.history = deque(maxlen=600)
        self.performance = deque(maxlen=600)
        self.messages = deque(maxlen=1500)
        self.traces = deque(maxlen=1500)
        self.incidents = deque(maxlen=500)
        self.total_messages = 0
        self.total_calls = 0
        self.total_duration_ms = 0.0
        self.open_incidents = {}
        self.latest_sim = None
        self.cities = {}
        for zone, city in CITIES.items():
            self.cities[zone] = {
                "latest": None, "classification": "No readings", "active": None,
                "pending": deque(), "last_sim": None,
                "teams": [{"position": (city["latitude"] + offset, city["longitude"]),
                           "failed": False, "available": not unavailable}
                          for offset in (0.002, 0.04)],
            }

    @property
    def seconds(self):
        return self.tick * 0.5

    @property
    def cycle(self):
        return max(1, (self.observed - 1) // len(self.readings) + 1)

    def advance(self, manual=False):
        if not self.running and not manual:
            return
        self.tick += 1
        if (self.tick - 1) % self.interval_ticks == 0:
            self.observe()
        for zone, city in self.cities.items():
            if city["active"] is None and city["pending"]:
                incident = city["pending"].popleft()
                city["active"] = incident
                self.restore_teams(incident["sim"], city)
                incident["status"] = "Processing"
            incident = city["active"]
            if incident is None:
                continue
            sim = incident["sim"]
            if sim.active:
                try:
                    sim.step()
                except Exception as error:
                    sim.queue.clear()
                    for team in sim.teams:
                        team.remaining = 0
                    sim.result = f"Execution error: {type(error).__name__}"
                    incident["status"] = "Unresolved: execution error"
                self.sync(sim, zone)
            incident["status"] = sim.result if sim.result != "Monitoring" else "Processing"
            if sim.waiting_approval:
                incident["status"] = "Waiting for approval"
            elif any(team.remaining for team in sim.teams):
                incident["status"] = "Repairing"
            elif not sim.active:
                incident["finished_seconds"] = self.seconds
                city["last_sim"] = sim
                city["teams"] = [{"position": team.position, "failed": team.failed,
                                  "available": team.available} for team in sim.teams]
                if sim.repaired:
                    self.completed += 1
                    self.open_incidents.pop(incident["key"], None)
                    incident["status"] = "Completed"
                city["active"] = None
        self.performance.append({"seconds": self.seconds, "confirmed": self.confirmed,
                                 "completed": self.completed, "cost_sar": self.total_cost,
                                 "messages": self.total_messages, "failures": self.failure_count,
                                 "errors": self.error_count})

    def observe(self):
        index = (self.start_index + self.observed) % len(self.readings)
        reading = display_reading(self.readings[index])
        self.observed += 1
        zone = reading["Zone"]
        city = self.cities[zone]
        sim = Simulation(reading, **self.settings)
        sim.conversation_id = f"reading-{self.observed}"
        sim.monitor_row = index + 1
        sim.monitor_cycle = self.cycle
        sim.synced_messages = sim.synced_traces = 0
        self.restore_teams(sim, city)
        sim.start()
        # Both monitor agents finish checking each incoming reading.
        for _ in range(3):
            sim.step()
        self.latest_sim = sim
        city["latest"] = reading
        city["last_sim"] = sim
        low = reading["Pressure"] < self.settings["pressure_limit"]
        high = reading["Flow_Rate"] > self.settings["flow_limit"]
        city["classification"] = "Confirmed leak" if sim.detected else "Suspected" if low or high else "Normal"
        self.history.append({"seconds": self.seconds, "row": index + 1, "cycle": self.cycle,
                             "city": CITIES[zone]["name"], "Pressure": reading["Pressure"],
                             "Flow_Rate": reading["Flow_Rate"]})
        if sim.detected:
            key = (zone, reading["Block"], reading["Pipe"])
            if key not in self.open_incidents and len(city["pending"]) < 100:
                incident = {"id": sim.conversation_id, "key": key, "zone": zone, "sim": sim,
                            "status": "Queued", "created_seconds": self.seconds,
                            "finished_seconds": None}
                self.open_incidents[key] = incident
                self.incidents.append(incident)
                city["pending"].append(incident)
                self.confirmed += 1
            else:
                if key not in self.open_incidents:
                    self.dropped += 1
                for message in sim.queue:
                    message["cancelled"] = True
                sim.queue.clear()
        self.sync(sim, zone)

    def restore_teams(self, sim, city):
        for team, saved in zip(sim.teams, city["teams"]):
            team.position = saved["position"]
            team.failed = saved["failed"]
            team.available = saved["available"] and not self.unavailable and not team.failed
            team.status = "Failed" if team.failed else "Available" if team.available else "Unavailable"
            team.fail_on_accept = self.fail_first and team.name == "Team A" and not team.failed

    def sync(self, sim, zone):
        for message in sim.messages[sim.synced_messages:]:
            message.update(city=CITIES[zone]["name"], seconds=self.seconds,
                           row=sim.monitor_row, cycle=sim.monitor_cycle)
            self.messages.append(message)
            self.total_messages += 1
            if message["performative"] == "INFORM" and message["content"].get("state") == "failed":
                self.failure_count += 1
            if message["performative"] == "INFORM" and message["content"].get("state") == "accepted":
                team = sim.agents[message["sender"]]
                position = (sim.reading["Latitude"], sim.reading["Longitude"])
                self.total_cost += self.base_cost + distance_km(team.position, position) * self.cost_per_km
        sim.synced_messages = len(sim.messages)
        for trace in sim.traces[sim.synced_traces:]:
            item = dict(trace, city=CITIES[zone]["name"], seconds=self.seconds,
                        conversation_id=sim.conversation_id)
            self.traces.append(item)
            self.total_calls += 1
            self.total_duration_ms += trace["duration_ms"]
            self.error_count += bool(trace["error"])
        sim.synced_traces = len(sim.traces)

    def approve(self, zone, accepted):
        incident = self.cities[zone]["active"]
        if incident and incident["sim"].waiting_approval:
            incident["sim"].approve(accepted)
            self.sync(incident["sim"], zone)

    def city_status(self, zone):
        incidents = [item for key, item in self.open_incidents.items() if key[0] == zone]
        if incidents:
            active = self.cities[zone]["active"]
            return "Confirmed leak", active["status"] if active else incidents[-1]["status"]
        previous = self.cities[zone]["last_sim"]
        return self.cities[zone]["classification"], "Completed" if previous and previous.repaired else "No open incident"

    def selected_sim(self, zone):
        city = self.cities[zone]
        return city["active"]["sim"] if city["active"] else city["last_sim"]
