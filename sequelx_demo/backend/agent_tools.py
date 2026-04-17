"""
SequelX Bid Intelligence — Data Fetcher & Pre-Computation Engine
Fetches real RFQ and bid data from MongoDB, then computes:
  - Total Cost of Ownership (TCO) per vendor
  - Multi-criteria weighted scores using RFQ evaluation criteria
  - Winner prediction with probability
  - Risk flags
All computation happens in Python. The LLM receives pre-computed results to reason over.
"""
from database import get_collection
from bson import ObjectId
import json


def _safe_float(val):
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return 0.0


def _serialize(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


def list_rfqs_for_dropdown() -> list:
    """Return a lightweight list of RFQs for the frontend dropdown."""
    coll = get_collection("rfqs")
    rfqs = coll.find(
        {},
        {"eventId": 1, "eventTitle": 1, "status": 1, "procurementCategory": 1}
    ).sort("created_At", -1).limit(50)

    result = []
    bids_coll = get_collection("vendorbids")
    for r in rfqs:
        eid = r.get("eventId")
        bid_count = bids_coll.count_documents({"eventId": eid})
        result.append({
            "eventId": eid,
            "title": r.get("eventTitle", ""),
            "status": r.get("status", ""),
            "category": r.get("procurementCategory", ""),
            "bidCount": bid_count,
        })
    return result


def fetch_bid_analysis(event_id: str) -> str:
    """
    Full bid intelligence analysis for a given event.
    Returns a structured JSON string the LLM can reason over.
    """
    rfqs_coll = get_collection("rfqs")
    bids_coll = get_collection("vendorbids")

    rfq = rfqs_coll.find_one({"eventId": event_id})
    if not rfq:
        return json.dumps({"error": f"No RFQ found for event {event_id}"})

    bids = list(bids_coll.find({"eventId": event_id}))
    if not bids:
        return json.dumps({"error": f"No bids submitted for event {event_id}", "rfq": _serialize({
            "eventId": event_id,
            "title": rfq.get("eventTitle"),
            "status": rfq.get("status"),
        })})

    # ---- RFQ Summary ----
    criteria = rfq.get("rfqValues", {}).get("evaluationCriteria", {})
    terms = rfq.get("rfqValues", {}).get("terms", {})
    items = rfq.get("rfqValues", {}).get("items", [])
    budget_raw = rfq.get("rfiValues", {}).get("budgetRange", "")

    budget_min, budget_max = None, None
    if budget_raw:
        try:
            parts = budget_raw.replace(",", "").replace("-", " ").split()
            nums = [float(p) for p in parts if p.replace(".", "").isdigit()]
            if len(nums) >= 2:
                budget_min, budget_max = nums[0], nums[1]
            elif len(nums) == 1:
                budget_max = nums[0]
        except:
            pass

    rfq_summary = {
        "eventId": event_id,
        "title": rfq.get("eventTitle"),
        "status": rfq.get("status"),
        "category": rfq.get("procurementCategory"),
        "timeline": rfq.get("timeline"),
        "budgetRange": budget_raw,
        "budgetMin": budget_min,
        "budgetMax": budget_max,
        "currency": rfq.get("rfqValues", {}).get("currency", "USD"),
        "itemCount": len(items),
        "items": [{"description": i.get("description"), "qty": i.get("quantity"), "unit": i.get("unit")} for i in items[:10]],
        "evaluationCriteria": criteria,
        "minimumScore": criteria.get("minimumScore", 0),
        "paymentSchedule": terms.get("paymentSchedule"),
        "warrantyPeriod": terms.get("warrantyPeriod"),
        "supplierQueriesCount": len(rfq.get("supplierQueries", [])),
    }

    # ---- TCO Computation ----
    vendor_analyses = []
    all_base_amounts = [_safe_float(b.get("baseAmount")) for b in bids if _safe_float(b.get("baseAmount")) > 0]
    min_base = min(all_base_amounts) if all_base_amounts else 1

    for bid in bids:
        c = bid.get("commercial", {})
        base = _safe_float(bid.get("baseAmount"))
        freight = _safe_float(c.get("freightCost"))
        insurance = _safe_float(c.get("insuranceCost"))
        packaging = _safe_float(c.get("packagingCost"))
        duties = _safe_float(c.get("importDuties"))
        installation = _safe_float(c.get("installationCost"))
        other = _safe_float(c.get("otherCosts"))
        tco = base + freight + insurance + packaging + duties + installation + other

        # ---- Multi-Criteria Scoring ----
        score = 0
        score_breakdown = {}
        max_possible = sum(v for k, v in criteria.items() if k != "minimumScore" and isinstance(v, (int, float)))

        # Price score (lower is better)
        price_weight = _safe_float(criteria.get("totalPrice", 0))
        if price_weight > 0 and base > 0 and min_base > 0:
            price_score = (min_base / base) * price_weight
            score += price_score
            score_breakdown["price"] = round(price_score, 2)

        # Warranty score (longer is better)
        warranty_weight = _safe_float(criteria.get("warrantyPeriod", 0))
        if warranty_weight > 0:
            warranty_years = _safe_float(c.get("warrantyPeriodYears", 0))
            all_warranties = [_safe_float(b.get("commercial", {}).get("warrantyPeriodYears", 0)) for b in bids]
            max_warranty = max(all_warranties) if all_warranties else 1
            if max_warranty > 0 and warranty_years > 0:
                w_score = (warranty_years / max_warranty) * warranty_weight
                score += w_score
                score_breakdown["warranty"] = round(w_score, 2)

        # Delivery speed score (faster is better)
        timeline_weight = _safe_float(criteria.get("implementationTimeline", 0))
        if timeline_weight > 0:
            lead_days = _safe_float(c.get("deliveryLeadTimeDays", 0))
            all_leads = [_safe_float(b.get("commercial", {}).get("deliveryLeadTimeDays", 0)) for b in bids if _safe_float(b.get("commercial", {}).get("deliveryLeadTimeDays", 0)) > 0]
            min_lead = min(all_leads) if all_leads else 1
            if min_lead > 0 and lead_days > 0:
                t_score = (min_lead / lead_days) * timeline_weight
                score += t_score
                score_breakdown["delivery"] = round(t_score, 2)

        # ---- Risk Flags ----
        risks = []
        if base == 0:
            risks.append("ZERO_BASE_AMOUNT — No pricing submitted")
        if tco == 0:
            risks.append("ZERO_TCO — No cost data available")
        if budget_max and tco > budget_max:
            risks.append(f"OVER_BUDGET — TCO ({tco}) exceeds budget max ({budget_max})")
        if not c.get("currency"):
            risks.append("MISSING_CURRENCY")
        if base > 0 and len(bid.get("items", [])) == 0:
            risks.append("NO_LINE_ITEMS — Pricing not broken down")

        # ---- Budget Compliance ----
        within_budget = True
        if budget_min and budget_max:
            within_budget = budget_min <= tco <= budget_max if tco > 0 else False
        elif budget_max:
            within_budget = tco <= budget_max if tco > 0 else False

        # ---- Win Probability ----
        win_prob = 40  # base
        if within_budget:
            win_prob += 20
        if base > 0 and base == min_base:
            win_prob += 25
        elif base > 0 and min_base > 0:
            ratio = min_base / base
            win_prob += ratio * 15
        if len(risks) == 0:
            win_prob += 15
        else:
            win_prob -= len(risks) * 5
        win_prob = max(5, min(95, win_prob))

        vendor_analyses.append({
            "vendorName": bid.get("vendorName"),
            "status": bid.get("status"),
            "baseAmount": base,
            "totalAmount": _safe_float(bid.get("totalAmount")),
            "tco": {
                "base": base,
                "freight": freight,
                "insurance": insurance,
                "packaging": packaging,
                "importDuties": duties,
                "installation": installation,
                "other": other,
                "total": tco,
            },
            "commercial": {
                "currency": c.get("currency"),
                "paymentTerms": c.get("paymentTerms"),
                "warrantyYears": _safe_float(c.get("warrantyPeriodYears", 0)),
                "deliveryLeadDays": _safe_float(c.get("deliveryLeadTimeDays", 0)),
                "icvPercentage": _safe_float(c.get("icvPercentage", 0)),
                "advancePayment": _safe_float(c.get("advancePaymentPercentage", 0)),
            },
            "scoring": {
                "totalScore": round(score, 2),
                "maxPossible": max_possible,
                "percentage": round((score / max_possible * 100), 1) if max_possible > 0 else 0,
                "breakdown": score_breakdown,
            },
            "budgetCompliance": within_budget,
            "winProbability": round(win_prob, 1),
            "riskFlags": risks,
            "riskLevel": "HIGH" if len(risks) >= 2 else "MEDIUM" if len(risks) == 1 else "LOW",
            "questionnaireAnswers": [
                {"q": a.get("questionText"), "a": a.get("answerText")}
                for a in bid.get("questionnaireAnswers", [])
            ],
            "submittedAt": str(bid.get("submitted_At", "")),
        })

    # Sort by win probability
    vendor_analyses.sort(key=lambda x: x["winProbability"], reverse=True)

    return json.dumps(_serialize({
        "rfq": rfq_summary,
        "bidCount": len(vendor_analyses),
        "vendors": vendor_analyses,
        "recommendation": {
            "winner": vendor_analyses[0]["vendorName"] if vendor_analyses else None,
            "winProbability": vendor_analyses[0]["winProbability"] if vendor_analyses else 0,
            "reason": "Highest combined score from TCO analysis, criteria scoring, and budget compliance",
        },
    }), indent=2, default=str)
