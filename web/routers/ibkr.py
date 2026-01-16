from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from web.services import ibkr_service
from web.services.ibkr_service import clean_nan

router = APIRouter()


class TradeUpdate(BaseModel):
    delta: Optional[float] = None
    und_price: Optional[float] = None


class ImportRequest(BaseModel):
    query_type: str = "daily"


@router.get("/positions")
async def get_positions(
    sort_by: str = Query("mtm", description="Sort by: mtm, value, symbol, s_qty"),
    ascending: bool = Query(False, description="Sort order")
):
    """Get all positions aggregated by underlying symbol"""
    try:
        return clean_nan(ibkr_service.get_all_positions(sort_by, ascending))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{symbol}")
async def get_position_detail(symbol: str):
    """Get detailed position for a specific symbol"""
    try:
        result = ibkr_service.get_position_detail(symbol.upper())
        if result is None:
            raise HTTPException(status_code=404, detail=f"No trades found for {symbol}")
        return clean_nan(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades")
async def get_all_trades():
    """Get all trades"""
    try:
        df = ibkr_service.get_trades_with_calculations()
        if df.empty:
            return []
        df['dateTime'] = df['dateTime'].astype(str)
        return clean_nan(df.to_dict(orient='records'))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/trades/{trade_id}")
async def update_trade(trade_id: str, update: TradeUpdate):
    """Update trade fields (delta, und_price)"""
    try:
        updates = {}
        if update.delta is not None:
            updates['delta'] = update.delta
        if update.und_price is not None:
            updates['und_price'] = update.und_price

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        success = ibkr_service.update_trade(trade_id, updates)
        if not success:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_trades(request: ImportRequest):
    """Import trades from IBKR Flex Query"""
    try:
        result = ibkr_service.import_trades(request.query_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mtm")
async def update_mtm():
    """Update market prices"""
    try:
        result = ibkr_service.update_mtm_prices()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/daily")
async def get_daily_stats():
    """Get daily PnL statistics"""
    try:
        return clean_nan(ibkr_service.get_daily_stats())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/weekly")
async def get_weekly_stats():
    """Get weekly PnL statistics"""
    try:
        return clean_nan(ibkr_service.get_weekly_stats())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
