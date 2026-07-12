import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import aio_pika

from messaging.connection import RabbitMQConnection

EXCHANGE_NAME = "rpg.events"

QUEUE_NAME = "log_queue"
ROUTING_KEY = "#"


async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        payload = json.loads(message.body.decode())
        routing_key = message.routing_key
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"[{timestamp}] EVENTO: {routing_key}")
        print(f"[{timestamp}] DADOS:   {json.dumps(payload, ensure_ascii=False)}")
        print("-" * 70)


async def main():
    connection = await RabbitMQConnection.get_connection()
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key=ROUTING_KEY)

    print(f"[Logger] Aguardando todos os eventos (routing_key: '#')")
    print(f"[Logger] Pressione Ctrl+C para parar")

    await queue.consume(process_message)

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        await connection.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Logger] Encerrado.")
