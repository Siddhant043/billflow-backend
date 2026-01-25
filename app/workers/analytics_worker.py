import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, case
from decimal import Decimal

from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.models.user import User
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment

logger = logging.getLogger(__name__)


class AnalyticsWorker:
    def __init__(self):
        self.update_interval = 1800  # Update every 30 minutes
    
    async def update_user_metrics(self, user_id: str):
        """Calculate and cache metrics for a user."""
        try:
            async with AsyncSessionLocal() as db:
                # Get invoice statistics
                invoice_stats = await db.execute(
                    select(
                        func.count(Invoice.id).label("total_invoices"),
                        func.coalesce(func.sum(Invoice.total_amount), 0).label("total_revenue"),
                        func.sum(
                            case((Invoice.status == InvoiceStatus.PAID, 1), else_=0)
                        ).label("paid_invoices"),
                        func.sum(
                            case((Invoice.status == InvoiceStatus.SENT, 1), else_=0)
                        ).label("pending_invoices"),
                        func.sum(
                            case((Invoice.status == InvoiceStatus.OVERDUE, 1), else_=0)
                        ).label("overdue_invoices"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]), 
                                     Invoice.total_amount),
                                    else_=0
                                )
                            ),
                            0
                        ).label("outstanding_amount")
                    ).where(Invoice.user_id == user_id)
                )
                
                stats = invoice_stats.one()
                
                # Get monthly revenue (last 12 months)
                twelve_months_ago = datetime.now() - timedelta(days=365)
                monthly_revenue = await db.execute(
                    select(
                        func.date_trunc('month', Invoice.issue_date).label('month'),
                        func.sum(Invoice.total_amount).label('revenue')
                    )
                    .where(
                        and_(
                            Invoice.user_id == user_id,
                            Invoice.status == InvoiceStatus.PAID,
                            Invoice.issue_date >= twelve_months_ago
                        )
                    )
                    .group_by(func.date_trunc('month', Invoice.issue_date))
                    .order_by(func.date_trunc('month', Invoice.issue_date))
)
            monthly_data = []
            for row in monthly_revenue:
                monthly_data.append({
                    "month": row.month.strftime("%Y-%m"),
                    "revenue": float(row.revenue or 0)
                })
            
            # Get average payment time
            avg_payment_time = await db.execute(
                select(
                    func.avg(
                        func.extract('epoch', Invoice.paid_at) - 
                        func.extract('epoch', Invoice.sent_at)
                    ) / 86400  # Convert to days
                ).where(
                    and_(
                        Invoice.user_id == user_id,
                        Invoice.status == InvoiceStatus.PAID,
                        Invoice.sent_at.isnot(None),
                        Invoice.paid_at.isnot(None)
                    )
                )
            )
            
            avg_days = avg_payment_time.scalar() or 0
            
            # Compile metrics
            metrics = {
                "total_invoices": stats.total_invoices or 0,
                "total_revenue": float(stats.total_revenue or 0),
                "paid_invoices": stats.paid_invoices or 0,
                "pending_invoices": stats.pending_invoices or 0,
                "overdue_invoices": stats.overdue_invoices or 0,
                "outstanding_amount": float(stats.outstanding_amount or 0),
                "average_payment_days": round(float(avg_days), 1),
                "monthly_revenue": monthly_data,
                "last_updated": datetime.now().isoformat()
            }
            
            # Cache metrics
            await redis_client.set_json(
                f"analytics:{user_id}",
                metrics,
                expire=3600  # 1 hour
            )
            
            logger.info(f"Updated analytics for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating metrics for user {user_id}: {e}")

    async def update_all_metrics(self):
        """Update metrics for all active users."""
        try:
            async with AsyncSessionLocal() as db:
                # Get all active users
                result = await db.execute(
                    select(User.id).where(User.is_active == True)
                )
            
                user_ids = [str(row[0]) for row in result]
            
                logger.info(f"Updating analytics for {len(user_ids)} users")
            
                # Update metrics for each user
                for user_id in user_ids:
                    await self.update_user_metrics(user_id)
                    await asyncio.sleep(0.1)  # Small delay to avoid overwhelming DB
            
                logger.info("Completed analytics update for all users")
            
        except Exception as e:
            logger.error(f"Error updating all metrics: {e}")

    async def start(self):
        """Start the analytics worker."""
        logger.info("Starting analytics worker...")
    
        # Connect to Redis
        await redis_client.connect()
    
        # Run initial update
        await self.update_all_metrics()
    
        while True:
            try:
                await asyncio.sleep(self.update_interval)
                await self.update_all_metrics()
            
            except Exception as e:
                logger.error(f"Analytics worker error: {e}")
                await asyncio.sleep(60)
            
async def main():
    """Main function to run the analytics worker."""
    worker = AnalyticsWorker()
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())