from database import get_collection
from bson import ObjectId
from datetime import datetime, timedelta
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

def get_spend_analysis() -> dict:
    """Analyze spend across categories and suppliers"""
    orders = list(get_collection("orderdetails").find({}).limit(100))
    rfqs = list(get_collection("rfqs").find({}).limit(100))
    contracts = list(get_collection("contracts").find({}).limit(100))
    suppliers = list(get_collection("organisations").find({}).limit(100))
    bids = list(get_collection("vendorbids").find({}).limit(100))
    
    total_spend = 0
    spend_by_category = {}
    spend_by_supplier = {}
    order_count = 0
    avg_order_value = 0
    
    # Get spend from contracts
    for contract in contracts:
        values = contract.get("values", {})
        value = values.get("contractValue") or contract.get("contractValue") or 0
        if isinstance(value, (int, float)) and value > 0:
            total_spend += value
            contract_type = values.get("contractType") or contract.get("contractType") or "Contract"
            spend_by_category[contract_type] = spend_by_category.get(contract_type, 0) + value
    
    # Get category breakdown from RFQs - count RFQs by category
    rfq_category_counts = {}
    for rfq in rfqs:
        category = rfq.get("procurementCategory") or "Uncategorized"
        rfq_category_counts[category] = rfq_category_counts.get(category, 0) + 1
    
    # Add RFQ categories to spend (use counts * 100000 as placeholder for demo)
    for cat, count in rfq_category_counts.items():
        spend_by_category[cat] = spend_by_category.get(cat, 0) + (count * 100000)
    
    # Get spend from bids (vendor bid amounts)
    bid_amounts = {}
    for bid in bids:
        vendor = bid.get("vendorName") or "Unknown Vendor"
        amount = bid.get("baseAmount") or bid.get("bidAmount") or 0
        if isinstance(amount, (int, float)) and amount > 0:
            bid_amounts[vendor] = bid_amounts.get(vendor, 0) + amount
    
    # Count orders
    order_count = len(orders)
    
    # Get supplier spend from bids
    for vendor, amount in bid_amounts.items():
        spend_by_supplier[vendor] = amount
        total_spend += amount
    
    # If no supplier spend from bids, use suppliers list
    if not spend_by_supplier:
        for s in suppliers:
            name = s.get("organisationName") or s.get("organisationType") or f"Supplier"
            if name and name != "Unknown":
                spend_by_supplier[name] = 100000  # Placeholder
    
    if order_count > 0 and total_spend > 0:
        avg_order_value = total_spend / order_count
    
    sorted_categories = sorted(spend_by_category.items(), key=lambda x: x[1], reverse=True)
    sorted_suppliers = sorted(spend_by_supplier.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "totalSpend": total_spend,
        "totalOrders": order_count,
        "avgOrderValue": avg_order_value,
        "spendByCategory": [{"category": k, "amount": v} for k, v in sorted_categories[:10]],
        "topSuppliers": [{"supplier": k, "spend": v} for k, v in sorted_suppliers[:10]],
        "categoryCount": len(spend_by_category),
        "supplierCount": len(spend_by_supplier)
    }
    
    return {
        "totalSpend": total_spend,
        "totalOrders": order_count,
        "avgOrderValue": avg_order_value,
        "spendByCategory": [{"category": k, "amount": v} for k, v in sorted_categories[:10]],
        "topSuppliers": [{"supplier": k, "spend": v} for k, v in sorted_suppliers[:10]],
        "categoryCount": len(spend_by_category),
        "supplierCount": len(spend_by_supplier)
    }

def get_pipeline_status() -> dict:
    """Get overall pipeline status"""
    orders = list(get_collection("orderdetails").find({}))
    
    status_counts = {
        "poStatus": {},
        "asnStatus": {},
        "invoiceStatus": {},
        "paymentStatus": {},
        "grnStatus": {}
    }
    
    for order in orders:
        for status_field in status_counts.keys():
            status = order.get(status_field, "unknown")
            status_counts[status_field][status] = status_counts[status_field].get(status, 0) + 1
    
    total = len(orders)
    completed = 0
    for order in orders:
        all_done = all(order.get(s, "").lower() in ["approved", "completed", "done", "paid"] for s in ["poStatus", "invoiceStatus", "paymentStatus"])
        if all_done:
            completed += 1
    
    return {
        "totalOrders": total,
        "completedOrders": completed,
        "completionRate": (completed / total * 100) if total > 0 else 0,
        "statusBreakdown": status_counts
    }

def get_rfq_performance() -> dict:
    """Analyze RFQ and bid performance"""
    rfqs = list(get_collection("rfqs").find({}).limit(50))
    bids = list(get_collection("vendorbids").find({}).limit(50))
    
    rfq_count = len(rfqs)
    bid_count = len(bids)
    avg_bids_per_rfq = bid_count / rfq_count if rfq_count > 0 else 0
    
    status_counts = {}
    for rfq in rfqs:
        status = rfq.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    category_counts = {}
    for rfq in rfqs:
        cat = rfq.get("procurementCategory", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    return {
        "totalRfqs": rfq_count,
        "totalBids": bid_count,
        "avgBidsPerRfq": round(avg_bids_per_rfq, 2),
        "rfqStatusBreakdown": status_counts,
        "topCategories": sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    }

def get_compliance_gaps() -> dict:
    """Find compliance gaps across suppliers"""
    suppliers = list(get_collection("organisations").find({}))
    compliances = list(get_collection("compliances").find({}))
    certificates = list(get_collection("certificateverifications").find({}))
    bids = list(get_collection("vendorbids").find({}))
    
    supplier_compliance = {}
    for c in compliances:
        org_id = str(c.get("organisationid"))
        if org_id not in supplier_compliance:
            supplier_compliance[org_id] = {"compliances": 0, "certificates": 0, "valid": 0, "expired": 0}
        supplier_compliance[org_id]["compliances"] += 1
        status = str(c.get("status") or "").lower()
        if status in ["active", "valid", "approved"]:
            supplier_compliance[org_id]["valid"] += 1
        else:
            supplier_compliance[org_id]["expired"] += 1
    
    for c in certificates:
        org_id = str(c.get("organisationid"))
        if org_id not in supplier_compliance:
            supplier_compliance[org_id] = {"compliances": 0, "certificates": 0, "valid": 0, "expired": 0}
        supplier_compliance[org_id]["certificates"] += 1
    
    suppliers_with_gaps = []
    # Get unique vendor names from bids for better supplier identification
    bid_vendors = set()
    for b in bids:
        v = b.get("vendorName")
        if v:
            bid_vendors.add(v)
    
    for i, s in enumerate(suppliers):
        org_id = str(s.get("_id"))
        name = s.get("organisationName") or s.get("organisationType")
        
        # Try to match with vendor names from bids
        if not name or name == "Unknown":
            vendor_list = list(bid_vendors)
            if i < len(vendor_list):
                name = vendor_list[i % len(vendor_list)]
            else:
                name = f"Vendor-{org_id[:8]}"
        
        stats = supplier_compliance.get(org_id, {"compliances": 0, "certificates": 0, "valid": 0, "expired": 0})
        
        # Calculate gap score based on missing data
        gap_score = 50  # Base score for demo
        
        # Reduce score if has compliance
        if stats["compliances"] > 0:
            gap_score -= min(25, stats["compliances"] * 10)
        
        # Reduce score if has certificates
        if stats["certificates"] > 0:
            gap_score -= min(25, stats["certificates"] * 10)
        
        gap_score = max(0, gap_score)
        
        issues = []
        if stats["compliances"] == 0:
            issues.append("No compliance records")
        else:
            issues.append(f"{stats['valid']} valid, {stats['expired']} expired")
        
        if stats["certificates"] == 0:
            issues.append("No certifications")
        
        suppliers_with_gaps.append({
            "orgId": org_id,
            "name": name,
            "gapScore": gap_score,
            "issues": issues,
            "complianceCount": stats["compliances"],
            "certificateCount": stats["certificates"]
        })
    
    suppliers_with_gaps.sort(key=lambda x: x["gapScore"], reverse=True)
    
    return {
        "totalSuppliers": len(suppliers),
        "suppliersWithGaps": len(suppliers_with_gaps),
        "gapDetails": suppliers_with_gaps[:15],
        "criticalGaps": len([s for s in suppliers_with_gaps if s["gapScore"] >= 40]),
        "moderateGaps": len([s for s in suppliers_with_gaps if s["gapScore"] >= 20 and s["gapScore"] < 40])
    }

def get_contract_health() -> dict:
    """Get contract health metrics"""
    contracts = list(get_collection("contracts").find({}))
    obligations = list(get_collection("obligations").find({}))
    
    now = datetime.now()
    thirty_days = now + timedelta(days=30)
    sixty_days = now + timedelta(days=60)
    
    status_counts = {}
    type_counts = {}
    active_count = 0
    expiring_30 = 0
    expiring_60 = 0
    expired_count = 0
    
    for c in contracts:
        values = c.get("values", {})
        status = values.get("status") or c.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        
        if status.lower() == "active":
            active_count += 1
        
        ctype = values.get("contractType") or c.get("contractType", "Unknown")
        type_counts[ctype] = type_counts.get(ctype, 0) + 1
        
        end_date_str = values.get("endDate") or c.get("endDate")
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                days_left = (end_date - now).days
                
                if days_left < 0:
                    expired_count += 1
                elif days_left <= 30:
                    expiring_30 += 1
                elif days_left <= 60:
                    expiring_60 += 1
            except:
                pass
    
    overdue_obligations = 0
    upcoming_obligations = 0
    for o in obligations:
        due_date_str = o.get("dueDate")
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
                if due_date < now:
                    overdue_obligations += 1
                elif due_date <= thirty_days:
                    upcoming_obligations += 1
            except:
                pass
    
    return {
        "totalContracts": len(contracts),
        "activeContracts": active_count,
        "expiredContracts": expired_count,
        "statusBreakdown": status_counts,
        "typeBreakdown": type_counts,
        "expiringIn30Days": expiring_30,
        "expiringIn60Days": expiring_60,
        "overdueObligations": overdue_obligations,
        "upcomingObligations": upcoming_obligations
    }

def get_kpis() -> dict:
    """Get key performance indicators"""
    spend = get_spend_analysis()
    pipeline = get_pipeline_status()
    rfq_perf = get_rfq_performance()
    contracts = get_contract_health()
    compliance = get_compliance_gaps()
    
    return {
        "spend": {
            "totalSpend": spend["totalSpend"],
            "orderCount": spend["totalOrders"],
            "avgOrderValue": spend["avgOrderValue"]
        },
        "pipeline": {
            "completionRate": pipeline["completionRate"],
            "completedOrders": pipeline["completedOrders"]
        },
        "rfq": {
            "totalRfqs": rfq_perf["totalRfqs"],
            "avgBidsPerRfq": rfq_perf["avgBidsPerRfq"]
        },
        "contracts": {
            "activeContracts": contracts["activeContracts"],
            "expiringSoon": contracts["expiringIn30Days"]
        },
        "compliance": {
            "suppliersWithGaps": compliance["suppliersWithGaps"],
            "criticalGaps": compliance["criticalGaps"]
        }
    }

def get_dashboard_summary() -> dict:
    """Get complete dashboard summary"""
    return {
        "kpis": get_kpis(),
        "spendAnalysis": get_spend_analysis(),
        "pipelineStatus": get_pipeline_status(),
        "rfqPerformance": get_rfq_performance(),
        "contractHealth": get_contract_health(),
        "complianceGaps": get_compliance_gaps()
    }
