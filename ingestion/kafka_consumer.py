"""
Kafka Consumer — process enterprise events
"""
import json
import signal
from typing import Callable
from confluent_kafka import Consumer, KafkaError, Message
from loguru import logger
from config.kafka_config import get_consumer_config, CONSUMER_GROUPS


class EnterpriseConsumer:
    def __init__(self, group: str = "etl", topics: list[str] | None = None):
        group_id = CONSUMER_GROUPS.get(group, group)
        self._consumer = Consumer(get_consumer_config(group_id))
        self._topics = topics or []
        self._running = False
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, *_):
        logger.info("Shutting down consumer...")
        self._running = False

    def subscribe(self, topics: list[str]) -> None:
        self._topics = topics
        self._consumer.subscribe(topics)
        logger.info(f"Subscribed: {topics}")

    def consume(
        self,
        handler: Callable[[dict, str], None],
        poll_timeout: float = 1.0,
        batch_size: int = 100,
    ) -> None:
        """Main consume loop. handler(payload, topic) → None"""
        if not self._topics:
            raise ValueError("No topics subscribed.")
        self._running = True
        batch: list[tuple[dict, str]] = []

        try:
            while self._running:
                msg: Message = self._consumer.poll(timeout=poll_timeout)
                if msg is None:
                    if batch:
                        self._flush_batch(batch, handler)
                        batch.clear()
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.error(f"Kafka error: {msg.error()}")
                    continue
                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    batch.append((payload, msg.topic()))
                except Exception as e:
                    logger.error(f"Parse error: {e}")
                if len(batch) >= batch_size:
                    self._flush_batch(batch, handler)
                    self._consumer.commit(asynchronous=False)
                    batch.clear()
        finally:
            if batch:
                self._flush_batch(batch, handler)
            self._consumer.commit(asynchronous=False)
            self._consumer.close()

    def _flush_batch(self, batch: list, handler: Callable) -> None:
        for payload, topic in batch:
            try:
                handler(payload, topic)
            except Exception as e:
                logger.error(f"Handler error [{topic}]: {e}")
