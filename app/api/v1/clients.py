from uuid import UUID
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.client import ClientResponse, ClientCreate, ClientUpdate
from typing import List, Optional

from app.core.database import get_db
from app.utils.dependencies import get_current_active_user
from app.models.client import Client
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("/", response_model=List[ClientResponse])
async def list_clients(
    skip: int = Query(0, ge=0),
    limit:int = Query(100, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user:User = Depends(get_current_active_user)
) -> List[ClientResponse]:
    """List all clients for a user."""
    client_service = ClientService(db)
    clients = await client_service.list_clients(current_user.id, skip, limit, search)
    return clients

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Get client by id."""
    client_service = ClientService(db)
    client = await client_service.get_client(user_id=current_user.id, client_id=client_id)
    return client

@router.post("/", response_model=ClientResponse)
async def create_client(
    client_data: ClientCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Create new client."""
    client_service = ClientService(db)
    client = await client_service.create_client(current_user.id, client_data)
    return client

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    client_data: ClientUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> ClientResponse:
    """Update client."""
    client_service = ClientService(db)
    client = await client_service.update_client(current_user.id, client_id, client_data)
    return client

@router.delete("/{client_id}", response_model=bool)
async def delete_client(
    client_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> bool:
    """Delete client."""
    client_service = ClientService(db)
    client = await client_service.delete_client(client_id, current_user.id)
    return client

@router.get("/{client_id}/stats", response_model=dict)
async def get_client_stats(
    client_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get client statistics."""
    client_service = ClientService(db)
    stats = await client_service.get_client_stats(client_id, current_user.id)
    return stats
    
