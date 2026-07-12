import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"


class RabbitMQConnection:
    _connection: aio_pika.RobustConnection | None = None
    _channel: aio_pika.RobustChannel | None = None

    @classmethod
    async def get_connection(cls) -> aio_pika.RobustConnection:
        if cls._connection is None or cls._connection.is_closed:
            cls._connection = await aio_pika.connect_robust(RABBITMQ_URL)
        return cls._connection

    @classmethod
    async def get_channel(cls) -> aio_pika.RobustChannel:
        conn = await cls.get_connection()
        if cls._channel is None or cls._channel.is_closed:
            cls._channel = await conn.channel()
        return cls._channel

    @classmethod
    async def close(cls):
        if cls._channel and not cls._channel.is_closed:
            await cls._channel.close()
        if cls._connection and not cls._connection.is_closed:
            await cls._connection.close()
