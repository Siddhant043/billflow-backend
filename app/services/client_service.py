from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func, and_, case
from typing import List, Optional

from app.models.invoice import Invoice, InvoiceStatus
from app.models.client import Client
from app.schemas.client import ClientCreate
from app.schemas.client import ClientUpdate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
import json


class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_clients(
        self, 
        user_id:UUID, 
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None
    ) -> List[dict]:
        """List all clients for a user with invoice statistics."""
        # Build base query with aggregates
        query = select(
            Client,
            func.coalesce(func.sum(Invoice.total_amount), 0).label("total_invoiced"),
            func.coalesce(
                func.sum(
                    case(
                        (Invoice.status == InvoiceStatus.OVERDUE, Invoice.total_amount),
                        else_=0
                    )
                ),
                0
            ).label("total_outstanding"),
            func.count(Invoice.id).label("total_number_of_invoices")
        ).outerjoin(
            Invoice, Client.id == Invoice.client_id
        ).where(
            Client.user_id == user_id
        )
        
        if search:
            search_filter = f"%{search}%"
            query = query.where(
                (Client.name.ilike(search_filter)) |
                (Client.email.ilike(search_filter)) |
                (Client.company.ilike(search_filter))
            )
        
        query = query.group_by(Client.id).offset(skip).limit(limit).order_by(Client.name)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        # Transform results to list of dictionaries
        clients = []
        for row in rows:
            client = row[0]  # Client object
            clients.append({
                "id": client.id,
                "user_id": client.user_id,
                "name": client.name,
                "email": client.email,
                "phone_number": client.phone_number,
                "address": client.address,
                "company": client.company,
                "gst_number": client.gst_number,
                "website": client.website,
                "notes": client.notes,
                "created_at": client.created_at,
                "updated_at": client.updated_at,
                "total_invoiced": float(row.total_invoiced),
                "total_outstanding": float(row.total_outstanding),
                "total_number_of_invoices": row.total_number_of_invoices
            })
        
        return clients

    async def get_client(
        self,
        user_id:UUID,
        client_id:UUID
    ) -> Optional[dict]:
        """Get a client by id."""
        cache_key = f"client:{client_id}"
        cached = await redis_client.get(cache_key)

        if cached:
            if cached.get("user_id") == str(user_id):
                return Client(**cached)
        
        # Query database
        result = await self.db.execute(
            select(Client).where(
                and_(
                    Client.id == client_id,
                    Client.user_id == user_id
                )
            )
        )
        client = result.scalar_one_or_none()

        # Cache result
        if client:
            client_dict = {
                "id": str(client.id),
                "user_id": str(client.user_id),
                "name": client.name,
                "email": client.email,
                "phone_number": client.phone_number,
                "address": client.address,
                "company": client.company,
                "website": client.website,
                "notes": client.notes,
                "gst_number": client.gst_number,
                "created_at": client.created_at.isoformat(),
                "updated_at": client.updated_at.isoformat(),
            }
            await redis_client.set_json(cache_key, client_dict, expire=1800)
        
        return client

    
    async def create_client(
        self,
        user_id: UUID,
        client_data: ClientCreate,
    ) -> Client:
        """Create new Client."""
        client = Client(
            user_id=user_id,
            **client_data.model_dump()
        )
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)

        # Invalidate user's client list cache
        await redis_client.invalidate_pattern(f"clients:{user_id}:*")
        return client

    async def update_client(
        self,
        user_id:UUID,
        client_id:UUID,
        client_data: ClientUpdate
    ) -> Client:
        """Update client."""
        client = await self.db.get(Client, client_id)
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found")
        update_data = client_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(client, field, value)
        
        await self.db.commit()
        await self.db.refresh(client)

        # Invalidate cache
        await redis_client.delete(f"client:{client_id}")
        await redis_client.invalidate_pattern(f"clients:{user_id}:*")
        
        return client

    async def delete_client(self, client_id: UUID, user_id: UUID) -> bool:
        """Delete a client."""
        client = await self.get_client(user_id, client_id)
        
        if not client:
            return False
        
        await self.db.delete(client)
        await self.db.commit()
        
        # Invalidate cache
        await redis_client.delete(f"client:{client_id}")
        await redis_client.invalidate_pattern(f"clients:{user_id}:*")
        
        return True

    async def get_client_stats(self, client_id: UUID, user_id: UUID) -> dict:
        """Get client statistics."""
        client = await self.get_client(user_id, client_id)
        
        if not client:
            return None
        
        # Get invoice statistics
        stats_query = select(
            func.count(Invoice.id).label("total_invoices"),
            func.coalesce(func.sum(Invoice.total_amount), 0).label("total_revenue"),
            func.coalesce(
                func.sum(
                    func.case(
                        (Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]), Invoice.total_amount),
                        else_=0
                    )
                ),
                0
            ).label("outstanding_amount")
        ).where(Invoice.client_id == client_id)
        
        result = await self.db.execute(stats_query)
        stats = result.one()
        
        return {
            "total_invoices": stats.total_invoices,
            "total_revenue": float(stats.total_revenue),
            "outstanding_amount": float(stats.outstanding_amount)
        }