import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import aio_pika
import httpx

from messaging.connection import RabbitMQConnection

EXCHANGE_NAME = "rpg.events"

QUEUE_NAME = "reward_queue"
ROUTING_KEYS = ["quest.completed"]
HERO_SERVICE_URL = "http://localhost:8001"


async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        payload = json.loads(message.body.decode())
        routing_key = message.routing_key

        print(f"[Reward] Evento recebido: {routing_key}")
        print(f"[Reward] Payload: {json.dumps(payload, ensure_ascii=False)}")

        if routing_key == "quest.completed":
            hero_id = payload.get("hero_id")
            xp = payload.get("xp", 0)
            gold = payload.get("gold", 0)

            print(f"[Reward] Distribuindo +{xp} XP e +{gold} ouro para herói {hero_id}")

            try:
                async with httpx.AsyncClient() as client:
                    if xp > 0:
                        resp = await client.patch(
                            f"{HERO_SERVICE_URL}/heroes/{hero_id}/xp",
                            json={"quantidade": xp},
                        )
                        print(f"[Reward] XP distribuído → {resp.status_code}")

                    if gold > 0:
                        resp = await client.patch(
                            f"{HERO_SERVICE_URL}/heroes/{hero_id}/gold",
                            json={"quantidade": gold},
                        )
                        print(f"[Reward] Gold distribuído → {resp.status_code}")
            except httpx.ConnectError:
                print(f"[Reward] ERRO: Hero Service indisponível em {HERO_SERVICE_URL}")

            print(f"[Reward] Recompensas distribuidas para herói {hero_id}")


async def main():
    connection = await RabbitMQConnection.get_connection()
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)

    for key in ROUTING_KEYS:
        await queue.bind(exchange, routing_key=key)

    print(f"[Reward] Aguardando eventos: {', '.join(ROUTING_KEYS)}")
    print(f"[Reward] Pressione Ctrl+C para parar")

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
        print("\n[Reward] Encerrado.")
