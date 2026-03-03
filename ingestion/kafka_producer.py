"""
Kafka Producer — publish enterprise events to topics
"""
import json
import uuid
from datetime import datetime
from confluent_kafka import Producer
from loguru import logger
from config.kafka_config import get_producer_config
from config.settings import settings


class EnterpriseProducer:
    def __init__(self):
        self._producer = Producer(get_producer_config())

    def _on_delivery(self, err, msg):
        if err:
            logger.error(f"Delivery failed [{msg.topic()}]: {err}")
        else:
            logger.debug(f"Delivered [{msg.topic()}] offset={msg.offset()}")

    def publish(self, topic: str, key: str, value: dict) -> None:
        payload = {
            **value,
            "_meta": {
                "event_id": str(uuid.uuid4()),
                "ts": datetime.utcnow().isoformat(),
            },
        }
        self._producer.produce(
            topic=topic,
            key=key.encode("utf-8"),
            value=json.dumps(payload, default=str).encode("utf-8"),
            on_delivery=self._on_delivery,
        )
        self._producer.poll(0)

    def publish_company(self, company: dict) -> None:
        self.publish(settings.kafka_topic_companies, company["company_id"], company)

    def publish_relationship(self, rel: dict) -> None:
        key = f"{rel['source_id']}-{rel['target_id']}"
        self.publish(settings.kafka_topic_relationships, key, rel)

    def publish_transaction(self, tx: dict) -> None:
        self.publish(settings.kafka_topic_transactions, tx["transaction_id"], tx)

    def publish_alert(self, alert: dict) -> None:
        key = alert.get("entity_id", str(uuid.uuid4()))
        self.publish(settings.kafka_topic_alerts, key, alert)

    def flush(self, timeout: float = 30.0) -> None:
        self._producer.flush(timeout=timeout)

    def close(self) -> None:
        self.flush()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
