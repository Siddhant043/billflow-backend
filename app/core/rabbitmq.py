from aio_pika import connect_robust, Message, ExchangeType
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel, AbstractRobustExchange
from typing import Optional, Callable
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class RabbitMQClient:
    def __init__(self):
        self.connection: Optional(AbstractRobustConnection) = None
        self.channel: Optional(AbstractRobustChannel) = None
        self.exchanges: dict[str, AbstractRobustExchange] = {}
    
    async def connect(self):
        """Connect to RabbitMQ."""
        try:
            rabbitmq_url = f"amqp://{settings.RABBITMQ_DEFAULT_USER}:{settings.RABBITMQ_DEFAULT_PASS}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}"
            self.connection = await connect_robust(rabbitmq_url)
            self.channel = await self.connection.channel()

            # Set QoS
            await self.channel.set_qos(prefetch_count=10)

            # Declare Exchanges
            self.exchanges["invoices"] = await self.channel.declare_exchange(
                "invoices",
                ExchangeType.TOPIC,
                durable=True,
            )

            self.exchanges["emails"] = await self.channel.declare_exchange(
                "emails",
                ExchangeType.TOPIC,
                durable=True,
            )
            logger.info("Connected to RabbitMQ successfully")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ."""
        if self.connection:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ successfully")
    
    async def publish(self, exchange_name:str, routing_key:str, message:dict, priority: int = 5):
        """Publish a message to and exchange."""
        if not self.channel or exchange_name not in self.exchanges:
            logger.error(f"Cannot publish: Exchange {exchange_name} not found")
            return
        try:
            exchange = self.exchanges.get(exchange_name)
            message_body = json.dumps(message).encode()
            await exchange.publish(
                Message(
                    body=message_body,
                    content_type="application/json",
                    delivery_mode=2,
                    priority=priority
                ),
                routing_key=routing_key
            )

            logger.info(f"Published message to exchange {exchange_name} with routing key {routing_key}")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise

    async def consume(self, queue_name:str, routing_keys:list[str], exchange_name: str, callback: Callable ):
        """Consume messages from a queue."""
        if not self.channel or exchange_name not in self.exchanges:
            logger.error(f"Cannot consume: Exchange {exchange_name} not found")
            return
        try:
            exchange = self.exchanges.get(exchange_name)

            queue = await self.channel.declare_queue(
                queue_name,
                durable=True,
                arguments={"x-max-priority": 10}
            )

            # Bind queue to exchange with routing keys
            for routing_key in routing_keys:
                await queue.bind(exchange, routing_key=routing_key)
            
            # Start consuming
            await queue.consume(callback)

            logger.info(f"Started consuming from {queue_name}")
        except Exception as e:
            logger.error(f"Failed to start consuming: {e}")
            raise

# Global RabbitMQ client instance
rabbitmq_client = RabbitMQClient()