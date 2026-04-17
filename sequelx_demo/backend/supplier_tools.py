from database import get_collection
from bson import ObjectId
from datetime import datetime
import json

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


def supplier_display_name(supplier: dict) -> str:
    return (
        safe_str(supplier.get("organisationName"))
        or safe_str(supplier.get("organisationType"))
        or f"Supplier-{str(supplier.get('_id'))[:8]}"
    )

def get_all_suppliers() -> list:
    """Get all suppliers from organisations collection"""
    coll = get_collection("organisations")
    suppliers = list(coll.find({}).limit(50))
    
    result = []
    for s in suppliers:
        result.append({
            "orgId": str(s.get("_id")),
            "organisationName": supplier_display_name(s),
            "organisationType": safe_str(s.get("organisationType")) or "Unknown",
            "status": safe_str(s.get("status")) or "unknown",
            "createdAt": safe_str(s.get("createdAt")),
            "country": safe_str(s.get("country")),
            "city": safe_str(s.get("city"))
        })
    return result

def get_supplier_details(org_id: str) -> dict:
    """Get detailed supplier information"""
    coll = get_collection("organisations")
    
    try:
        supplier = coll.find_one({"_id": ObjectId(org_id)})
    except:
        supplier = coll.find_one({"organisationName": {"$regex": org_id, "$options": "i"}})
    
    if not supplier:
        return {"error": f"Supplier not found: {org_id}"}
    
    return {
        "orgId": str(supplier.get("_id")),
        "organisationName": supplier_display_name(supplier),
        "organisationType": safe_str(supplier.get("organisationType")) or "Unknown",
        "status": safe_str(supplier.get("status")) or "unknown",
        "country": safe_str(supplier.get("country")),
        "city": safe_str(supplier.get("city")),
        "contactEmail": safe_str(supplier.get("contactEmail")),
        "contactPhone": safe_str(supplier.get("contactPhone")),
        "website": safe_str(supplier.get("website")),
        "taxId": safe_str(supplier.get("taxId")),
        "createdAt": safe_str(supplier.get("createdAt"))
    }

def get_compliance_records(org_id: str) -> list:
    """Get compliance records for a supplier"""
    coll = get_collection("compliances")
    
    try:
        records = list(coll.find({"organisationid": ObjectId(org_id)}))
    except:
        records = list(coll.find({"organisationid": org_id}))
    
    result = []
    for c in records:
        result.append({
            "complianceId": str(c.get("_id")),
            "complianceType": safe_str(c.get("complianceType")),
            "status": safe_str(c.get("status")),
            "expiryDate": safe_str(c.get("expiryDate")),
            "issueDate": safe_str(c.get("issueDate")),
            "documentNumber": safe_str(c.get("documentNumber"))
        })
    return result

def get_certificate_verifications(org_id: str) -> list:
    """Get certificate verifications for a supplier"""
    coll = get_collection("certificateverifications")
    
    try:
        records = list(coll.find({"organisationid": ObjectId(org_id)}))
    except:
        records = list(coll.find({"organisationid": org_id}))
    
    result = []
    for c in records:
        result.append({
            "certificateId": str(c.get("_id")),
            "certificateType": safe_str(c.get("certificateType")),
            "verificationStatus": safe_str(c.get("verificationStatus")),
            "verifiedAt": safe_str(c.get("verifiedAt")),
            "validUntil": safe_str(c.get("validUntil"))
        })
    return result

def calculate_trust_score(org_id: str) -> dict:
    """Calculate trust score for a supplier"""
    supplier = get_supplier_details(org_id)
    if supplier.get("error"):
        return supplier
    
    score = 0
    max_score = 100
    factors = []
    
    status_score = 0
    status = (supplier.get("status") or "").lower()
    if status == "active":
        status_score = 25
        factors.append({"factor": "ACTIVE_STATUS", "score": 25, "positive": True})
    elif status == "pending":
        status_score = 10
        factors.append({"factor": "PENDING_STATUS", "score": 10, "positive": True, "note": "Under review"})
    else:
        factors.append({"factor": "STATUS", "score": 0, "positive": False, "note": f"Status: {status}"})
    
    score += status_score
    
    compliances = get_compliance_records(org_id)
    if len(compliances) > 0:
        valid_compliances = [c for c in compliances if c.get("status") in ["Active", "Valid", "approved"]]
        compliance_ratio = len(valid_compliances) / len(compliances)
        compliance_score = int(25 * compliance_ratio)
        score += compliance_score
        factors.append({
            "factor": "COMPLIANCE",
            "score": compliance_score,
            "positive": compliance_score >= 15,
            "note": f"{len(valid_compliances)}/{len(compliances)} compliant"
        })
    else:
        factors.append({"factor": "COMPLIANCE", "score": 0, "positive": False, "note": "No compliance records"})
    
    certs = get_certificate_verifications(org_id)
    if len(certs) > 0:
        valid_certs = [c for c in certs if c.get("verificationStatus") in ["Verified", "Valid", "approved"]]
        cert_ratio = len(valid_certs) / len(certs)
        cert_score = int(25 * cert_ratio)
        score += cert_score
        factors.append({
            "factor": "CERTIFICATION",
            "score": cert_score,
            "positive": cert_score >= 15,
            "note": f"{len(valid_certs)}/{len(certs)} verified"
        })
    else:
        factors.append({"factor": "CERTIFICATION", "score": 0, "positive": False, "note": "No certificates"})
    
    if supplier.get("country") and supplier.get("city"):
        score += 15
        factors.append({"factor": "PROFILE_COMPLETE", "score": 15, "positive": True})
    else:
        factors.append({"factor": "PROFILE_COMPLETE", "score": 0, "positive": False, "note": "Incomplete profile"})
    
    if supplier.get("taxId") or supplier.get("website"):
        score += 10
        factors.append({"factor": "VERIFICATION_DOCS", "score": 10, "positive": True})
    else:
        factors.append({"factor": "VERIFICATION_DOCS", "score": 0, "positive": False, "note": "Limited verification"})
    
    trust_level = "EXCELLENT" if score >= 85 else "GOOD" if score >= 65 else "FAIR" if score >= 45 else "POOR"
    
    return {
        "orgId": org_id,
        "organisationName": supplier.get("organisationName"),
        "trustScore": score,
        "trustLevel": trust_level,
        "maxScore": max_score,
        "factors": factors,
        "complianceCount": len(compliances),
        "certificateCount": len(certs)
    }

def get_supplier_summary() -> dict:
    """Get summary of all suppliers"""
    coll = get_collection("organisations")
    
    total = coll.count_documents({})
    
    status_counts = {}
    for status in ["Active", "Pending", "Inactive", "Blocked", "approved"]:
        count = coll.count_documents({"status": status})
        if count > 0:
            status_counts[status] = count
    
    type_counts = {}
    suppliers = list(coll.find({}))
    for s in suppliers:
        t = s.get("organisationType", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    return {
        "totalSuppliers": total,
        "byStatus": status_counts,
        "byType": type_counts
    }

def get_compliance_overview() -> dict:
    """Get compliance overview for all suppliers"""
    comp_coll = get_collection("compliances")
    
    total = comp_coll.count_documents({})
    
    status_counts = {}
    for status in ["Active", "Expired", "Pending", "Valid", "approved"]:
        count = comp_coll.count_documents({"status": status})
        if count > 0:
            status_counts[status] = count
    
    type_counts = {}
    comps = list(comp_coll.find({}))
    for c in comps:
        t = c.get("complianceType", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    return {
        "totalRecords": total,
        "byStatus": status_counts,
        "byType": type_counts
    }

def analyze_supplier_full(org_id: str) -> dict:
    """Full supplier DNA analysis"""
    supplier = get_supplier_details(org_id)
    if supplier.get("error"):
        return supplier
    
    trust = calculate_trust_score(org_id)
    compliances = get_compliance_records(org_id)
    certificates = get_certificate_verifications(org_id)
    
    return {
        "supplier": supplier,
        "trustAnalysis": trust,
        "complianceRecords": compliances,
        "certificateRecords": certificates,
        "summary": {
            "trustScore": trust.get("trustScore"),
            "trustLevel": trust.get("trustLevel"),
            "complianceCount": len(compliances),
            "certificateCount": len(certificates),
            "verificationComplete": trust.get("trustLevel") in ["EXCELLENT", "GOOD"]
        }
    }
