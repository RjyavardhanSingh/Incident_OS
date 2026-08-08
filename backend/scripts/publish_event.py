import sys
import uuid

from app.core.config import settings
from app.events.base import EventEnvelope
from app.events.kafka import KafkaEventPublisher


def main() -> None:
    event_type = sys.argv[1]
    investigation_id = sys.argv[2]
    payload = {"service": "payments", "step_type": sys.argv[3], "window_start": "2026-08-09T03:18:29.000000+00:00"}
    envelope = EventEnvelope(
        event_type=event_type,
        incident_id=uuid.UUID("f31d4285-718d-4020-a717-14623daf14c7"),
        investigation_id=uuid.UUID(investigation_id),
        producer="test-harness",
        payload=payload,
    )
    publisher = KafkaEventPublisher()
    publisher.publish(envelope)
    publisher.flush()
    print("published", event_type)


if __name__ == "__main__":
    main()
