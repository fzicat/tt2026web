from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from web.services import fbn_service
from web.services.fbn_service import clean_nan

router = APIRouter()


class EntryCreate(BaseModel):
    date: str
    account: str
    portfolio: str
    currency: str
    investment: float = 0.0
    deposit: float = 0.0
    interest: float = 0.0
    dividend: float = 0.0
    distribution: float = 0.0
    tax: float = 0.0
    fee: float = 0.0
    other: float = 0.0
    cash: float = 0.0
    asset: float = 0.0
    rate: float = 1.0


@router.get("/accounts")
async def get_accounts():
    """Get list of all accounts"""
    return fbn_service.get_accounts()


@router.get("/stats/monthly")
async def get_monthly_stats():
    """Get monthly aggregated stats"""
    try:
        return clean_nan(fbn_service.get_monthly_stats())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/yearly")
async def get_yearly_stats():
    """Get yearly aggregated stats"""
    try:
        return clean_nan(fbn_service.get_yearly_stats())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/matrix/monthly")
async def get_monthly_matrix():
    """Get monthly assets matrix (dates x accounts)"""
    try:
        return clean_nan(fbn_service.get_monthly_matrix())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/matrix/yearly")
async def get_yearly_matrix():
    """Get yearly assets matrix (years x accounts)"""
    try:
        return clean_nan(fbn_service.get_yearly_matrix())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entry/{date}/{account}")
async def get_entry(date: str, account: str):
    """Get a specific entry by date and account"""
    try:
        entry = fbn_service.get_entry(date, account)
        if entry is None:
            return None
        return clean_nan(entry)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entry")
async def save_entry(entry: EntryCreate):
    """Save an account entry (upsert)"""
    try:
        entry_dict = entry.model_dump()
        fbn_service.save_entry(entry_dict)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
