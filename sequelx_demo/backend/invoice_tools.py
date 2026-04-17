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

def get_order_details(order_id: str) -> dict:
    """Fetch order details with all status fields"""
    coll = get_collection("orderdetails")
    try:
        order = coll.find_one({"_id": ObjectId(order_id)})
    except:
        order = coll.find_one({"orderId": order_id})
    
    if not order:
        return {"error": f"Order not found: {order_id}"}
    
    return {
        "orderId": str(order.get("_id")),
        "poStatus": safe_str(order.get("poStatus")),
        "asnStatus": safe_str(order.get("asnStatus")),
        "paymentStatus": safe_str(order.get("paymentStatus")),
        "invoiceStatus": safe_str(order.get("invoiceStatus")),
        "grnStatus": safe_str(order.get("grnStatus")),
        "lineItems": clean_for_json(order.get("lineItems", [])),
        "values": clean_for_json(order.get("values", {}))
    }

def get_all_orders() -> list:
    """Get all orders with status summary"""
    coll = get_collection("orderdetails")
    orders = list(coll.find({}).limit(30))
    
    result = []
    for o in orders:
        result.append({
            "orderId": str(o.get("_id")),
            "poStatus": safe_str(o.get("poStatus")),
            "asnStatus": safe_str(o.get("asnStatus")),
            "paymentStatus": safe_str(o.get("paymentStatus")),
            "invoiceStatus": safe_str(o.get("invoiceStatus")),
            "grnStatus": safe_str(o.get("grnStatus")),
            "lineItemsCount": len(o.get("lineItems", []))
        })
    return result

def get_orders_by_status(status_field: str, status_value: str) -> list:
    """Get orders filtered by specific status"""
    coll = get_collection("orderdetails")
    query = {status_field: status_value}
    orders = list(coll.find(query).limit(20))
    
    result = []
    for o in orders:
        result.append({
            "orderId": str(o.get("_id")),
            "poStatus": safe_str(o.get("poStatus")),
            "asnStatus": safe_str(o.get("asnStatus")),
            "paymentStatus": safe_str(o.get("paymentStatus")),
            "invoiceStatus": safe_str(o.get("invoiceStatus")),
            "grnStatus": safe_str(o.get("grnStatus"))
        })
    return result

def detect_anomalies(order_id: str) -> dict:
    """Detect invoice anomalies by comparing order details"""
    order = get_order_details(order_id)
    if order.get("error"):
        return order
    
    anomalies = []
    line_items = order.get("lineItems", [])
    values = order.get("values", {})
    
    # Handle both dict and already-cleaned string values
    def get_nested_value(obj, *keys):
        """Safely get nested value from dict"""
        if not isinstance(obj, dict):
            return None
        current = obj
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current
    
    # Check for zero quantities or amounts
    for idx, item in enumerate(line_items):
        qty = float(item.get("quantity", 0))
        rate = float(item.get("rate", 0))
        total = float(item.get("totalAmount", 0))
        
        if qty <= 0:
            anomalies.append({
                "type": "ZERO_QUANTITY",
                "item": item.get("description"),
                "severity": "HIGH",
                "message": f"Item has zero or negative quantity"
            })
        
        if rate <= 0:
            anomalies.append({
                "type": "ZERO_RATE",
                "item": item.get("description"),
                "severity": "HIGH",
                "message": f"Item has zero or negative rate"
            })
        
        # Check calculated vs stored amount
        expected_total = qty * rate
        if abs(expected_total - total) > 1:
            anomalies.append({
                "type": "AMOUNT_MISMATCH",
                "item": item.get("description"),
                "severity": "MEDIUM",
                "message": f"Expected: {expected_total}, Found: {total}"
            })
    
    # Check for missing required fields - handle both raw dict and cleaned data
    buyer = get_nested_value(values, "buyerName", "new") or get_nested_value(values, "buyerName")
    vendor = get_nested_value(values, "vendorName", "new") or get_nested_value(values, "vendorName")
    
    if not buyer:
        anomalies.append({
            "type": "MISSING_BUYER",
            "severity": "HIGH",
            "message": "Buyer name is missing"
        })
    if not vendor:
        anomalies.append({
            "type": "MISSING_VENDOR",
            "severity": "HIGH",
            "message": "Vendor name is missing"
        })
    
    anomaly_score = min(len(anomalies) * 20, 100)
    
    return {
        "orderId": order_id,
        "anomalyCount": len(anomalies),
        "anomalyScore": anomaly_score,
        "anomalies": anomalies,
        "status": "CRITICAL" if anomaly_score >= 60 else "WARNING" if anomaly_score >= 30 else "OK"
    }

def calculate_stp_score(order_id: str) -> dict:
    """Calculate Straight-Through Processing likelihood"""
    order = get_order_details(order_id)
    if order.get("error"):
        return order
    
    stp_score = 100
    blockers = []
    
    statuses = {
        "poStatus": order.get("poStatus"),
        "asnStatus": order.get("asnStatus"),
        "paymentStatus": order.get("paymentStatus"),
        "invoiceStatus": order.get("invoiceStatus"),
        "grnStatus": order.get("grnStatus")
    }
    
    for status_name, status_value in statuses.items():
        if status_value in [None, "", "pending", "rejected"]:
            stp_score -= 20
            if status_value in ["pending", "rejected"]:
                blockers.append(f"{status_name}: {status_value}")
    
    line_items = order.get("lineItems", [])
    if not line_items:
        stp_score -= 30
        blockers.append("No line items")
    else:
        for item in line_items:
            if not item.get("description") or not item.get("rate"):
                stp_score -= 10
                blockers.append(f"Incomplete line item")
    
    values = order.get("values", {})

    def get_field_value(obj, field):
        raw = obj.get(field)
        if isinstance(raw, dict):
            return raw.get("new") or raw.get("value") or raw.get("old")
        return raw

    required_fields = ["buyerName", "vendorName", "buyerGSTIN", "vendorGSTIN"]
    for field in required_fields:
        if not get_field_value(values, field):
            stp_score -= 15
            blockers.append(f"Missing {field}")
    
    stp_score = max(0, stp_score)
    
    return {
        "orderId": order_id,
        "stpScore": stp_score,
        "stpLikelihood": "HIGH" if stp_score >= 80 else "MEDIUM" if stp_score >= 50 else "LOW",
        "blockers": blockers,
        "canProceedWithoutApproval": stp_score >= 70
    }

def get_processing_summary() -> dict:
    """Get summary of all order processing statuses"""
    coll = get_collection("orderdetails")
    
    # Count by each status
    status_fields = ["poStatus", "asnStatus", "paymentStatus", "invoiceStatus", "grnStatus"]
    summary = {}
    
    for field in status_fields:
        summary[field] = {}
        for status in ["pending", "approved", "rejected"]:
            count = coll.count_documents({field: status})
            if count > 0:
                summary[field][status] = count
    
    # Calculate overall STP
    total_orders = coll.count_documents({})
    fully_approved = coll.count_documents({
        "poStatus": "approved",
        "asnStatus": "approved", 
        "paymentStatus": "approved",
        "invoiceStatus": "approved",
        "grnStatus": "approved"
    })
    
    stp_rate = (fully_approved / total_orders * 100) if total_orders > 0 else 0
    
    return {
        "totalOrders": total_orders,
        "fullyProcessed": fully_approved,
        "stpRate": round(stp_rate, 1),
        "statusBreakdown": summary
    }

def get_stuck_orders() -> dict:
    """Find orders stuck in pending status"""
    coll = get_collection("orderdetails")
    
    stuck = []
    pending_fields = ["poStatus", "asnStatus", "paymentStatus", "invoiceStatus", "grnStatus"]
    
    for field in pending_fields:
        orders = list(coll.find({field: "pending"}).limit(10))
        for o in orders:
            stuck.append({
                "orderId": str(o.get("_id")),
                "stuckAt": field,
                "allStatuses": {
                    "po": o.get("poStatus"),
                    "asn": o.get("asnStatus"),
                    "payment": o.get("paymentStatus"),
                    "invoice": o.get("invoiceStatus"),
                    "grn": o.get("grnStatus")
                }
            })
    
    return {
        "stuckOrdersCount": len(stuck),
        "stuckOrders": stuck[:20]
    }

def analyze_invoice_full(order_id: str) -> dict:
    """Full invoice analysis with anomalies and STP"""
    order = get_order_details(order_id)
    anomalies = detect_anomalies(order_id)
    stp = calculate_stp_score(order_id)
    
    return {
        "orderDetails": order,
        "anomalies": anomalies,
        "stpAnalysis": stp,
        "recommendation": get_process_recommendation(stp, anomalies)
    }

def get_process_recommendation(stp: dict, anomalies: dict) -> str:
    """Generate recommendation based on STP and anomalies"""
    if stp.get("stpScore", 0) >= 80 and anomalies.get("anomalyCount", 0) == 0:
        return "APPROVE - Can be processed automatically (STP: HIGH, No anomalies)"
    elif stp.get("stpScore", 0) >= 50:
        return "REVIEW - Manual approval recommended (STP: MEDIUM)"
    else:
        return "BLOCK - Requires investigation (STP: LOW or critical anomalies)"
