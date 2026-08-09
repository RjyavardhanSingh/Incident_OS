import json
import logging
import threading
from collections.abc import Callable

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from app.core.config import settings
from app.events.base import EventEnvelope

logger = logging.getLogger(__name__)


def client_config(extra: dict | None = None) -> dict:
    """Base confluent-kafka client config, adding SASL auth when configured.

    Local dev uses PLAINTEXT (the default); Zerops-managed Kafka uses SASL PLAIN
    with generated credentials, wired in via env vars.
    """
    cfg: dict = {"bootstrap.servers": settings.kafka_bootstrap_servers}
    if settings.kafka_security_protocol.upper() != "PLAINTEXT":
        cfg.update(
            {
                "security.protocol": settings.kafka_security_protocol,
                "sasl.mechanism": settings.kafka_sasl_mechanism or "PLAIN",
                "sasl.username": settings.kafka_sasl_username,
                "sasl.password": settings.kafka_sasl_password,
            }
        )
    if extra:
        cfg.update(extra)
    return cfg


def ensure_topics(
    topics: list[str],
    bootstrap_servers: str | None = None,
    timeout: float = 10.0,
) -> None:
    """Create missing topics so consumers never subscribe to an absent topic.

    Without this, a consumer subscribed before a topic is auto-created only
    rebalances after the metadata cache expires (default ~5 min), stalling the
    workflow. Runs at worker startup so every subscribed topic pre-exists.
    """
    bootstrap = bootstrap_servers or settings.kafka_bootstrap_servers
    admin = AdminClient(client_config({"bootstrap.servers": bootstrap}))
    metadata = admin.list_topics(timeout=timeout)
    missing = [topic for topic in topics if topic not in metadata.topics]
    if not missing:
        return
    futures = admin.create_topics(
        [NewTopic(topic, num_partitions=1, replication_factor=1) for topic in missing]
    )
    for topic, future in futures.items():
        future.result(timeout)
    logger.info("ensured kafka topics exist: %s", missing)


class KafkaEventPublisher:
    """Kafka-backed EventPublisher.

    Publishing is fire-and-forget with a delivery callback; callers must
    call ``flush()`` on shutdown to drain queued messages.
    """

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        cfg = client_config()
        if bootstrap_servers:
            cfg["bootstrap.servers"] = bootstrap_servers
        self._producer = Producer(cfg)

    def publish(self, envelope: EventEnvelope) -> None:
        topic = envelope.event_type
        value = envelope.model_dump_json()
        try:
            self._producer.produce(
                topic,
                key=str(envelope.event_id),
                value=value,
                callback=self._delivery_callback,
            )
            self._producer.poll(0)
        except KafkaException as exc:
            logger.error("kafka publish failed topic=%s event_id=%s error=%s", topic, envelope.event_id, exc)

    @staticmethod
    def _delivery_callback(err, msg) -> None:
        if err is not None:
            logger.error("kafka delivery failed topic=%s error=%s", msg.topic() if msg else "?", err)

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout)


class KafkaEventConsumer:
    """Kafka-backed EventConsumer.

    The confluent-kafka Consumer is polled on a dedicated thread; messages are
    dispatched onto the caller's asyncio event loop. The offset is committed on
    the polling thread only after the async handler returns successfully, so a
    crash produces a redelivery (at-least-once) which the worker handles
    idempotently via step claims.
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str | None = None,
        bootstrap_servers: str | None = None,
    ) -> None:
        self._topics = topics
        cfg = client_config(
            {
                "group.id": group_id or settings.kafka_group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        if bootstrap_servers:
            cfg["bootstrap.servers"] = bootstrap_servers
        self._consumer = Consumer(cfg)
        self._loop = None
        self._on_message: Callable | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self, loop, on_message: Callable) -> None:
        self._loop = loop
        self._on_message = on_message
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, name="kafka-consumer", daemon=True)
        self._thread.start()

    def _poll_loop(self) -> None:
        self._consumer.subscribe(self._topics)
        while self._running:
            msg = self._consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("kafka consumer error: %s", msg.error())
                continue
            try:
                envelope = EventEnvelope.model_validate_json(msg.value())
            except Exception as exc:
                logger.error("invalid event payload topic=%s error=%s", msg.topic(), exc)
                continue
            future = _submit(self._loop, self._on_message, envelope)
            try:
                future.result(timeout=300)
            except Exception:
                logger.exception("worker handler failed topic=%s event_id=%s; will retry via redelivery", msg.topic(), envelope.event_id)
                continue
            self._consumer.commit(msg, asynchronous=False)

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._consumer.close()


def _submit(loop, fn, envelope):
    import asyncio

    return asyncio.run_coroutine_threadsafe(fn(envelope), loop)
