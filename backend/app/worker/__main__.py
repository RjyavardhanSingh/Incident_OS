import asyncio
import logging

from app.core.db import async_session_factory
from app.events.kafka import KafkaEventConsumer, KafkaEventPublisher
from app.models.investigation import STEP_TOPIC_MAP
from app.worker.service import handle_envelope


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    publisher = KafkaEventPublisher()
    consumer = KafkaEventConsumer(topics=list(STEP_TOPIC_MAP.values()))

    async def on_message(envelope):
        await handle_envelope(async_session_factory, publisher, envelope)

    consumer.start(loop, on_message)
    logging.info("worker pool consuming %d topics", len(STEP_TOPIC_MAP))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        publisher.flush()
        loop.close()


if __name__ == "__main__":
    main()
