import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from bid_tools import (
    get_rfq_details,
    get_submitted_bids,
    calculate_tco,
    score_bids_against_criteria,
    predict_winner,
    list_all_rfqs,
    analyze_full_bid
)

app = FastAPI(title="SequelX Bid Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BidQuery(BaseModel):
    action: str
    event_id: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok", "service": "SequelX Bid Intelligence"}

@app.get("/api/rfqs")
def get_rfqs():
    """Get all RFQs"""
    try:
        rfqs = list_all_rfqs()
        return {"success": True, "data": rfqs}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/bid")
def handle_bid_query(query: BidQuery):
    """Handle bid intelligence queries"""
    
    action = query.action.lower()
    event_id = query.event_id
    
    try:
        if action == "get_rfq":
            if not event_id:
                raise HTTPException(status_code=400, detail="event_id required")
            result = get_rfq_details(event_id)
            return {"success": True, "data": result}
        
        elif action == "get_bids":
            if not event_id:
                raise HTTPException(status_code=400, detail="event_id required")
            result = get_submitted_bids(event_id)
            return {"success": True, "data": result}
        
        elif action == "calculate_tco":
            if not event_id:
                raise HTTPException(status_code=400, detail="event_id required")
            result = calculate_tco(event_id)
            return {"success": True, "data": result}
        
        elif action == "score_bids":
            if not event_id:
                raise HTTPException(status_code=400, detail="event_id required")
            result = score_bids_against_criteria(event_id)
            return {"success": True, "data": result}
        
        elif action == "predict_winner":
            if not event_id:
                raise HTTPException(status_code=400, detail="event_id required")
            result = predict_winner(event_id)
            return {"success": True, "data": result}
        
        elif action == "analyze":
            if not event_id:
                raise HTTPException(status_code=400, detail="event_id required")
            result = analyze_full_bid(event_id)
            return {"success": True, "data": result}
        
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}. Use: get_rfq, get_bids, calculate_tco, score_bids, predict_winner, analyze")
    
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bid_api:app", host="127.0.0.1", port=8001, reload=False)
