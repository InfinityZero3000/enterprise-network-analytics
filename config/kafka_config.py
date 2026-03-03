"""
Kafka Producer/Consumer Config + Topic Setup
"""
from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka.error import KafkaException
from loguru import logger
from config.settings import settings


CONSUMER_GROUPS = {
    "etl": "ena-etl-consumer",
    "graph": "ena-graph-consumer",
    "analytics": "ena-analytics-consumer",
}


def get_producer_config() -> dict:
    return {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "acks": "all",
        "retries": 5,
        "compression.type": "lz4",
    }


def get_consumer_config(group_id: str, offset: str = "earliest") -> dict:
    return {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": offset,
        "enable.auto.commit": False,
    }


def create_topics_if_not_exist():
    """Tạo Kafka topics cần thiết."""
    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})
    topics = [
        NewTopic(settings.kafka_topic_companies, num_partitions=3, replication_factor=1),
        NewTopic(settings.kafka_topic_relationships, num_partitions=3, replication_factor=1),
        NewTopic(settings.kafka_topic_transactions, num_partitions=6, replication_factor=1),
        NewTopic(settings.kafka_topic_alerts, num_partitions=3, replication_factor=1),
    ]
    results = admin.create_topics(topics)
    for topic, future in results.items():
        try:
            future.result()
            logger.info(f"Topic '{topic}' đã tạo.")
        except KafkaException as e:
            if "TOPIC_ALREADY_EXISTS" in str(e):
                logger.debug(f"Topic '{topic}' đã tồn tại.")
            else:
                logger.error(f"Lỗi tạo topic '{topic}': {e}")
