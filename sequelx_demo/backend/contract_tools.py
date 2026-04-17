from database import get_collection
from bson import ObjectId
from datetime import datetime, timedelta
import json
import re

def safe_str(value):
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

def get_all_contracts() -> list:
    """Get all contracts with summary"""
    coll = get_collection("contracts")
    contracts = list(coll.find({}).limit(30))
    
    result = []
    for c in contracts:
        result.append({
            "contractId": str(c.get("_id")),
            "documentId": safe_str(c.get("documentId")),
            "status": safe_str(c.get("status")),
            "contractType": safe_str(c.get("values", {}).get("contractType")),
            "contractValue": safe_str(c.get("values", {}).get("contractValue")),
            "currency": safe_str(c.get("values", {}).get("currency")),
            "startDate": safe_str(c.get("values", {}).get("startDate")),
            "endDate": safe_str(c.get("values", {}).get("endDate")),
            "clausesCount": len(c.get("clause", []))
        })
    return result

def get_contract_details(contract_id: str) -> dict:
    """Get full contract details"""
    coll = get_collection("contracts")
    try:
        contract = coll.find_one({"_id": ObjectId(contract_id)})
    except:
        contract = coll.find_one({"documentId": contract_id})
    
    if not contract:
        return {"error": f"Contract not found: {contract_id}"}
    
    return {
        "contractId": str(contract.get("_id")),
        "documentId": safe_str(contract.get("documentId")),
        "status": safe_str(contract.get("status")),
        "contractType": safe_str(contract.get("values", {}).get("contractType")),
        "contractValue": safe_str(contract.get("values", {}).get("contractValue")),
        "currency": safe_str(contract.get("values", {}).get("currency")),
        "startDate": safe_str(contract.get("values", {}).get("startDate")),
        "endDate": safe_str(contract.get("values", {}).get("endDate")),
        "clauses": clean_for_json(contract.get("clause", []))
    }

def get_obligations_by_contract(contract_id: str) -> list:
    """Get obligations for a specific contract"""
    obl_coll = get_collection("obligations")
    
    try:
        obligations = list(obl_coll.find({"contractid": ObjectId(contract_id)}))
    except:
        obligations = list(obl_coll.find({"contractid": contract_id}))
    
    result = []
    for o in obligations:
        result.append({
            "clauseTitle": safe_str(o.get("clause_title")),
            "type": safe_str(o.get("type")),
            "dueDate": safe_str(o.get("dueDate")),
            "isMilestone": o.get("isMilestone"),
            "responsible": o.get("responsible", [])
        })
    return result

def get_upcoming_obligations(days: int = 30) -> dict:
    """Get obligations due within specified days"""
    obl_coll = get_collection("obligations")
    
    now = datetime.now()
    future = now + timedelta(days=days)
    
    obligations = list(obl_coll.find({
        "dueDate": {
            "$gte": now.isoformat(),
            "$lte": future.isoformat()
        }
    }))
    
    result = []
    for o in obligations:
        result.append({
            "contractId": str(o.get("contractid")),
            "clauseTitle": safe_str(o.get("clause_title")),
            "type": safe_str(o.get("type")),
            "dueDate": safe_str(o.get("dueDate")),
            "isMilestone": o.get("isMilestone")
        })
    
    return {
        "totalObligations": len(result),
        "obligations": result
    }

def get_contract_summary() -> dict:
    """Get summary of all contracts"""
    coll = get_collection("contracts")
    
    total = coll.count_documents({})
    
    # Status breakdown
    status_counts = {}
    for status in ["Active", "Expired", "Pending Draft", "Send for Review", "draft"]:
        count = coll.count_documents({"status": status})
        if count > 0:
            status_counts[status] = count
    
    # Type breakdown
    type_counts = {}
    contracts = list(coll.find({}))
    for c in contracts:
        ct = c.get("values", {}).get("contractType", "Unknown")
        type_counts[ct] = type_counts.get(ct, 0) + 1
    
    # Check for expiring soon
    now = datetime.now()
    thirty_days = now + timedelta(days=30)
    expiring = coll.count_documents({
        "values.endDate": {
            "$gte": now.isoformat(),
            "$lte": thirty_days.isoformat()
        },
        "status": {"$ne": "expired"}
    })
    
    return {
        "totalContracts": total,
        "byStatus": status_counts,
        "byType": type_counts,
        "expiringIn30Days": expiring
    }

def analyze_contract_risk(contract_id: str) -> dict:
    """Analyze contract for risks"""
    contract = get_contract_details(contract_id)
    if contract.get("error"):
        return contract
    
    obligations = get_obligations_by_contract(contract_id)
    
    # Calculate risk factors
    risk_score = 0
    risks = []
    
    # Check status
    status = contract.get("status", "").lower()
    if status == "expired":
        risk_score += 50
        risks.append({"type": "EXPIRED", "severity": "CRITICAL", "message": "Contract has expired"})
    elif status == "pending draft":
        risk_score += 30
        risks.append({"type": "DRAFT", "severity": "MEDIUM", "message": "Contract is still in draft"})
    
    # Check end date
    end_date_str = contract.get("endDate")
    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            days_left = (end_date - datetime.now()).days
            if days_left < 0:
                risk_score += 40
                risks.append({"type": "EXPIRED", "severity": "CRITICAL", "message": f"Expired {abs(days_left)} days ago"})
            elif days_left < 30:
                risk_score += 30
                risks.append({"type": "EXPIRING", "severity": "HIGH", "message": f"Expires in {days_left} days"})
            elif days_left < 90:
                risk_score += 15
                risks.append({"type": "RENEWAL", "severity": "MEDIUM", "message": f"Expires in {days_left} days - plan renewal"})
        except:
            pass
    
    # Check for missing clauses
    clauses = contract.get("clauses", [])
    if len(clauses) == 0:
        risk_score += 20
        risks.append({"type": "NO_CLAUSES", "severity": "MEDIUM", "message": "No clauses defined"})
    
    # Check obligations
    overdue = [o for o in obligations if o.get("dueDate") and datetime.fromisoformat(o.get("dueDate").replace("Z", "+00:00")) < datetime.now()]
    if overdue:
        risk_score += 25
        risks.append({"type": "OVERDUE_OBLIGATIONS", "severity": "HIGH", "message": f"{len(overdue)} overdue obligations"})
    
    # Determine risk level
    if risk_score >= 50:
        risk_level = "CRITICAL"
    elif risk_score >= 30:
        risk_level = "HIGH"
    elif risk_score >= 15:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    
    return {
        "contractId": contract_id,
        "documentId": contract.get("documentId"),
        "riskScore": min(risk_score, 100),
        "riskLevel": risk_level,
        "risks": risks,
        "obligationsCount": len(obligations),
        "clausesCount": len(clauses),
        "recommendation": get_risk_recommendation(risk_level, risks)
    }

def get_risk_recommendation(risk_level: str, risks: list) -> str:
    """Generate recommendation based on risk"""
    if risk_level == "CRITICAL":
        return "IMMEDIATE ACTION REQUIRED - Review and renew/terminate contract"
    elif risk_level == "HIGH":
        return "URGENT - Schedule contract review meeting"
    elif risk_level == "MEDIUM":
        return "PLAN REVIEW - Add to quarterly review queue"
    else:
        return "MONITOR - Continue regular monitoring"

def get_renewal_risks() -> dict:
    """Get contracts expiring in next 60 days"""
    coll = get_collection("contracts")
    
    now = datetime.now()
    sixty_days = now + timedelta(days=60)
    
    contracts = list(coll.find({
        "values.endDate": {
            "$gte": now.isoformat(),
            "$lte": sixty_days.isoformat()
        },
        "status": {"$ne": "expired"}
    }))
    
    renewal_list = []
    for c in contracts:
        end_date_str = c.get("values", {}).get("endDate")
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                days_left = (end_date - datetime.now()).days
                
                renewal_list.append({
                    "contractId": str(c.get("_id")),
                    "documentId": safe_str(c.get("documentId")),
                    "contractType": safe_str(c.get("values", {}).get("contractType")),
                    "contractValue": safe_str(c.get("values", {}).get("contractValue")),
                    "endDate": safe_str(end_date_str),
                    "daysUntilExpiry": days_left,
                    "renewalPriority": "URGENT" if days_left <= 14 else "HIGH" if days_left <= 30 else "MEDIUM"
                })
            except:
                pass
    
    renewal_list.sort(key=lambda x: x["daysUntilExpiry"])
    
    return {
        "totalExpiring": len(renewal_list),
        "urgentCount": len([r for r in renewal_list if r["renewalPriority"] == "URGENT"]),
        "highCount": len([r for r in renewal_list if r["renewalPriority"] == "HIGH"]),
        "contracts": renewal_list[:20]
    }
