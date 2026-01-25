from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.redis import redis_client
from app.core.rabbitmq import rabbitmq_client
from app.api.v1 import auth, users, clients, invoices, payments, analytics

# Configure logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting up application...")
    try:
        # Connect to Redis
        await redis_client.connect()
        logger.info("Connected to Redis")
        
        # Connect to RabbitMQ
        await rabbitmq_client.connect()
        logger.info("Connected to RabbitMQ")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    
    yield

    # Shutdown
    logger.info("Shutting down application...")
    
    try:
        await redis_client.disconnect()
        logger.info("Disconnected from Redis")
        
        await rabbitmq_client.disconnect()
        logger.info("Disconnected from RabbitMQ")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(clients.router, prefix=settings.API_V1_PREFIX)
app.include_router(invoices.router, prefix=settings.API_V1_PREFIX)
app.include_router(payments.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Invoice Management API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "redis": await redis_client.redis.ping() if redis_client.redis else False,
        "rabbitmq": rabbitmq_client.connection is not None and not rabbitmq_client.connection.is_closed
    }