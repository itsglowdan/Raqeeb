from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from collections import deque
from copy import deepcopy


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


@dataclass(frozen=True)
class Message:
    message_id: str
    sender: str
    receiver: str
    performative: str
    content: dict
    ontology: str
    conversation_id: str
    step: int
    runtime_timestamp: str
    record_ref: str | None
    task_ref: str | None


class MessageBus:
    def __init__(self, run_id):
        self.run_id = run_id
        self.queue = deque()
        self.log = []

    def send(self, sender, receiver, performative, content, step, record_ref=None, task_ref=None):
        message = Message(f'{self.run_id}-M{len(self.log)+1:06d}', sender, receiver,
                          performative, deepcopy(content), 'raqeeb.water-monitoring.v1',
                          f'{self.run_id}:{record_ref or "run"}', step, utc_now(), record_ref, task_ref)
        self.log.append(asdict(message))
        self.queue.append(message)
        return message
