import logging
from datetime import datetime, timezone

from confluent_kafka import Consumer, TopicPartition
from confluent_kafka.admin import AdminClient

from app.sources.contract import SIGNAL_OBSERVATION, CollectionContext, EvidenceRecord

logger = logging.getLogger(__name__)

_METADATA_GROUP = "notifications"


class LiveKafkaSource:
    """Read-only probes against the demo Kafka.

    Uses a Consumer (not a member of any group, only reading watermarks and
    committed offsets) plus an AdminClient to report topics, partitions,
    consumer groups, and consumer-group lag.
    """

    def __init__(self, bootstrap_servers: str) -> None:
        self._bootstrap = bootstrap_servers
        self._consumer: Consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": "incident-os-kafka-source",
                "session.timeout.ms": 8000,
                "enable.auto.commit": False,
            }
        )
        self._admin: AdminClient = AdminClient(
            {"bootstrap.servers": bootstrap_servers}
        )

    def close(self) -> None:
        self._consumer.close()

    async def collect(self, context: CollectionContext) -> list[EvidenceRecord]:
        now = datetime.now(timezone.utc)
        records: list[EvidenceRecord] = []
        try:
            md = self._consumer.list_topics(timeout=5)
            for topic, tm in sorted(md.topics.items()):
                topic_records: list[EvidenceRecord] = []
                total_lag = 0
                partitions = 0
                for pid, _pm in sorted(tm.partitions.items()):
                    tp = TopicPartition(topic, pid)
                    low, high = self._consumer.get_watermark_offsets(tp, timeout=5)
                    committed = self._consumer.committed([tp], timeout=5)[0].offset
                    lag = None
                    if high is not None and committed >= 0:
                        lag = high - committed
                    partitions += 1
                    if lag is not None:
                        total_lag += lag
                    topic_records.append(
                        EvidenceRecord(
                            source="kafka",
                            service="kafka",
                            signal=SIGNAL_OBSERVATION,
                            timestamp=now,
                            payload={
                                "observation": "partition",
                                "topic": topic,
                                "partition": pid,
                                "low_watermark": low,
                                "high_watermark": high,
                                "committed_offset": committed,
                                "lag": lag,
                            },
                        )
                    )
                topic_records.append(
                    EvidenceRecord(
                        source="kafka",
                        service="kafka",
                        signal=SIGNAL_OBSERVATION,
                        timestamp=now,
                        payload={
                            "observation": "topic_summary",
                            "topic": topic,
                            "partitions": partitions,
                            "total_lag": total_lag,
                        },
                    )
                )
                records.extend(topic_records)

            groups = self._admin.list_consumer_groups().result(5)
            for group in groups.valid:
                records.append(
                    EvidenceRecord(
                        source="kafka",
                        service="kafka",
                        signal=SIGNAL_OBSERVATION,
                        timestamp=now,
                        payload={
                            "observation": "consumer_group",
                            "group": group.group_id,
                            "state": group.state.name if group.state else None,
                        },
                    )
                )
        except Exception:
            logger.exception("LiveKafkaSource collection failed")
            records.append(
                EvidenceRecord(
                    source="kafka",
                    service="kafka",
                    signal=SIGNAL_OBSERVATION,
                    timestamp=datetime.now(timezone.utc),
                    severity="error",
                    payload={"observation": "probe_failed", "error": "connection_error"},
                )
            )
        return records
