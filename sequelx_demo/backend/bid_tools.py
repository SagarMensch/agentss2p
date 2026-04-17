from database import get_collection
from bson import ObjectId
from datetime import datetime, timedelta
import json
import re

def safe_str(value):
    """Convert any value to string safely"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (int, float)):
        return value
    return str(value)

def clean_for_json(obj):
    """Recursively clean any object for JSON serialization"""
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, str):
        return obj
    return str(obj)

def get_rfq_details(event_id: str) -> dict:
    """Fetch the RFQ details from VaOM_CLM_DEV rfqs collection using the given eventId."""
    coll = get_collection("rfqs")
    rfq = coll.find_one({"eventId": event_id})
    if not rfq:
        return {"error": f"No RFQ found for event ID: {event_id}"}
    
    return {
        "eventId": safe_str(rfq.get("eventId")),
        "status": safe_str(rfq.get("status")),
        "eventTitle": safe_str(rfq.get("eventTitle")),
        "description": safe_str(rfq.get("description")),
        "procurementCategory": safe_str(rfq.get("procurementCategory")),
        "deadline": safe_str(rfq.get("deadline")),
        "budgetRange": safe_str(rfq.get("rfiValues", {}).get("budgetRange")),
        "evaluationCriteria": clean_for_json(rfq.get("rfqValues", {}).get("evaluationCriteria", {})),
        "items": clean_for_json(rfq.get("rfqValues", {}).get("items", []))
    }

def get_submitted_bids(event_id: str) -> list:
    """Fetch all vendor bids submitted for a specific eventId."""
    coll = get_collection("vendorbids")
    bids = list(coll.find({"eventId": event_id}))
    
    if not bids:
        return []
    
    bid_summaries = []
    for bid in bids:
        commercial = bid.get("commercial", {})
        bid_summaries.append({
            "vendorName": safe_str(bid.get("vendorName")),
            "status": safe_str(bid.get("status")),
            "baseAmount": safe_str(bid.get("baseAmount")),
            "totalAmount": safe_str(bid.get("totalAmount")),
            "currency": safe_str(commercial.get("currency")),
            "freightCost": safe_str(commercial.get("freightCost")),
            "insuranceCost": safe_str(commercial.get("insuranceCost")),
            "installationCost": safe_str(commercial.get("installationCost")),
            "importDuties": safe_str(commercial.get("importDuties")),
            "packagingCost": safe_str(commercial.get("packagingCost")),
            "submittedAt": safe_str(bid.get("submitted_At"))
        })
    return bid_summaries

def calculate_tco(event_id: str) -> dict:
    """Calculate Total Cost of Ownership for all bids."""
    bids_coll = get_collection("vendorbids")
    rfq_coll = get_collection("rfqs")
    
    rfq = rfq_coll.find_one({"eventId": event_id})
    if not rfq:
        return {"error": f"No RFQ found for event ID: {event_id}"}
    
    bids = list(bids_coll.find({"eventId": event_id}))
    if not bids:
        return {"error": f"No bids found for event ID: {event_id}"}
    
    tco_analysis = []
    for bid in bids:
        commercial = bid.get("commercial", {})
        
        try:
            base = float(bid.get("baseAmount", 0)) if bid.get("baseAmount") else 0
        except:
            base = 0
        
        try:
            freight = float(commercial.get("freightCost", 0)) if commercial.get("freightCost") else 0
        except:
            freight = 0
        try:
            insurance = float(commercial.get("insuranceCost", 0)) if commercial.get("insuranceCost") else 0
        except:
            insurance = 0
        try:
            installation = float(commercial.get("installationCost", 0)) if commercial.get("installationCost") else 0
        except:
            installation = 0
        try:
            import_duties = float(commercial.get("importDuties", 0)) if commercial.get("importDuties") else 0
        except:
            import_duties = 0
        try:
            packaging = float(commercial.get("packagingCost", 0)) if commercial.get("packagingCost") else 0
        except:
            packaging = 0
        try:
            other_costs = float(commercial.get("otherCosts", 0)) if commercial.get("otherCosts") else 0
        except:
            other_costs = 0
        
        tco = base + freight + insurance + installation + import_duties + packaging + other_costs
        
        tco_analysis.append({
            "vendorName": safe_str(bid.get("vendorName")),
            "baseAmount": base,
            "freightCost": freight,
            "insuranceCost": insurance,
            "installationCost": installation,
            "importDuties": import_duties,
            "packagingCost": packaging,
            "otherCosts": other_costs,
            "totalCostOfOwnership": tco,
            "currency": safe_str(commercial.get("currency")) or "USD"
        })
    
    tco_analysis.sort(key=lambda x: x["totalCostOfOwnership"], reverse=False)
    
    return {
        "rfqTitle": safe_str(rfq.get("eventTitle")),
        "category": safe_str(rfq.get("procurementCategory")),
        "budgetRange": safe_str(rfq.get("rfiValues", {}).get("budgetRange")),
        "tcoAnalysis": tco_analysis,
        "lowestTCO": tco_analysis[0] if tco_analysis else None
    }

def score_bids_against_criteria(event_id: str) -> dict:
    """Score all bids against the RFQ evaluation criteria."""
    rfq_coll = get_collection("rfqs")
    bids_coll = get_collection("vendorbids")
    
    rfq = rfq_coll.find_one({"eventId": event_id})
    if not rfq:
        return {"error": f"No RFQ found for event ID: {event_id}"}
    
    criteria = rfq.get("rfqValues", {}).get("evaluationCriteria", {})
    if not criteria:
        return {"error": "No evaluation criteria found for this RFQ."}
    
    bids = list(bids_coll.find({"eventId": event_id}))
    if not bids:
        return {"error": f"No bids found for event ID: {event_id}"}
    
    scored_bids = []
    for bid in bids:
        total_score = 0
        try:
            base_amount = float(bid.get("baseAmount", 0)) if bid.get("baseAmount") else 0
        except:
            base_amount = 0
        
        if criteria.get("totalPrice", 0) > 0 and base_amount > 0:
            all_amounts = []
            for b in bids:
                try:
                    all_amounts.append(float(b.get("baseAmount", 0)) or 0)
                except:
                    all_amounts.append(0)
            min_price = min([a for a in all_amounts if a > 0]) if all_amounts else 1
            price_score = (min_price / base_amount) * criteria.get("totalPrice", 0)
            total_score += price_score
        
        scored_bids.append({
            "vendorName": safe_str(bid.get("vendorName")),
            "status": safe_str(bid.get("status")),
            "baseAmount": base_amount,
            "calculatedScore": round(total_score, 2),
            "maxPossibleScore": sum(criteria.values())
        })
    
    scored_bids.sort(key=lambda x: x["calculatedScore"], reverse=True)
    
    return {
        "evaluationCriteria": criteria,
        "scoredBids": scored_bids,
        "recommendedWinner": scored_bids[0] if scored_bids else None
    }

def predict_winner(event_id: str) -> dict:
    """Predict which vendor will win based on TCO and criteria."""
    bids_coll = get_collection("vendorbids")
    rfq_coll = get_collection("rfqs")
    
    rfq = rfq_coll.find_one({"eventId": event_id})
    if not rfq:
        return {"error": f"No RFQ found for event ID: {event_id}"}
    
    bids = list(bids_coll.find({"eventId": event_id}))
    if not bids:
        return {"error": f"No bids found for event ID: {event_id}"}
    
    budget_range = safe_str(rfq.get("rfiValues", {}).get("budgetRange"))
    
    predictions = []
    for bid in bids:
        commercial = bid.get("commercial", {})
        
        try:
            base = float(bid.get("baseAmount", 0)) if bid.get("baseAmount") else 0
        except:
            base = 0
        
        try:
            freight = float(commercial.get("freightCost", 0)) if commercial.get("freightCost") else 0
        except:
            freight = 0
        try:
            installation = float(commercial.get("installationCost", 0)) if commercial.get("installationCost") else 0
        except:
            installation = 0
        
        tco = base + freight + installation
        
        within_budget = True
        if budget_range:
            try:
                range_parts = re.sub(r'[^0-9\s]', '', str(budget_range)).split()
                if len(range_parts) >= 2:
                    min_budget = float(range_parts[0])
                    max_budget = float(range_parts[-1])
                    within_budget = min_budget <= tco <= max_budget
            except:
                pass
        
        win_probability = 50
        if within_budget:
            win_probability += 25
        
        all_amounts = []
        for b in bids:
            try:
                all_amounts.append(float(b.get("baseAmount", 0)) or 0)
            except:
                all_amounts.append(0)
        
        if base > 0 and all_amounts:
            min_price = min(all_amounts)
            if base == min_price:
                win_probability += 25
        
        predictions.append({
            "vendorName": safe_str(bid.get("vendorName")),
            "baseAmount": base,
            "totalCostOfOwnership": tco,
            "withinBudget": within_budget,
            "winProbability": min(win_probability, 100)
        })
    
    predictions.sort(key=lambda x: x["winProbability"], reverse=True)
    
    return {
        "eventId": event_id,
        "rfqTitle": safe_str(rfq.get("eventTitle")),
        "budgetRange": budget_range,
        "predictions": predictions,
        "predictedWinner": predictions[0] if predictions else None
    }

def list_all_rfqs() -> list:
    """List all RFQs in the system."""
    coll = get_collection("rfqs")
    rfqs = list(coll.find({}).sort("created_At", -1).limit(20))
    
    result = []
    for r in rfqs:
        result.append({
            "eventId": safe_str(r.get("eventId")),
            "status": safe_str(r.get("status")),
            "eventTitle": safe_str(r.get("eventTitle")),
            "procurementCategory": safe_str(r.get("procurementCategory")),
            "deadline": safe_str(r.get("deadline"))
        })
    return result

def analyze_full_bid(event_id: str) -> dict:
    """Complete bid analysis with all calculations."""
    rfq = get_rfq_details(event_id)
    bids = get_submitted_bids(event_id)
    tco = calculate_tco(event_id)
    scores = score_bids_against_criteria(event_id)
    prediction = predict_winner(event_id)
    
    return {
        "rfq": rfq,
        "bids": bids,
        "tcoAnalysis": tco,
        "scoring": scores,
        "prediction": prediction,
        "summary": {
            "totalBids": len(bids),
            "recommendedWinner": prediction.get("predictedWinner", {}).get("vendorName") if prediction.get("predictedWinner") else "No winner",
            "winProbability": prediction.get("predictedWinner", {}).get("winProbability", 0) if prediction.get("predictedWinner") else 0
        }
    }
