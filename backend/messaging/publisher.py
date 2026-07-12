import json

import aio_pika

from .connection import RabbitMQConnection

EXCHANGE_NAME = "rpg.events"


async def publish_event(routing_key: str, payload: dict):
    channel = await RabbitMQConnection.get_channel()
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )

    message = aio_pika.Message(
        body=json.dumps(payload, ensure_ascii=False).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        content_type="application/json",
    )
    await exchange.publish(message, routing_key=routing_key)
