#!/usr/bin/env python
"""
Script to run all background workers.
"""
import asyncio
import logging
import sys
from multiprocessing import Process

from app.workers.email_worker import EmailWorker
from app.workers.payment_worker import PaymentWorker
from app.workers.analytics_worker import AnalyticsWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_email_worker():
    """Run the email worker."""
    try:
        worker = EmailWorker()
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Email worker stopped")
    except Exception as e:
        logger.error(f"Email worker crashed: {e}")
        sys.exit(1)


def run_payment_worker():
    """Run the payment worker."""
    try:
        worker = PaymentWorker()
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Payment worker stopped")
    except Exception as e:
        logger.error(f"Payment worker crashed: {e}")
        sys.exit(1)


def run_analytics_worker():
    """Run the analytics worker."""
    try:
        worker = AnalyticsWorker()
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Analytics worker stopped")
    except Exception as e:
        logger.error(f"Analytics worker crashed: {e}")
        sys.exit(1)


def main():
    """Start all workers."""
    logger.info("Starting all workers...")
    
    # Create processes for each worker
    workers = [
        Process(target=run_email_worker, name="EmailWorker"),
        Process(target=run_payment_worker, name="PaymentWorker"),
        Process(target=run_analytics_worker, name="AnalyticsWorker"),
    ]
    
    # Start all workers
    for worker in workers:
        worker.start()
        logger.info(f"Started {worker.name}")
    
    try:
        # Wait for all workers
        for worker in workers:
            worker.join()
    except KeyboardInterrupt:
        logger.info("Shutting down workers...")
        for worker in workers:
            worker.terminate()
            worker.join()
        logger.info("All workers stopped")


if __name__ == "__main__":
    main()