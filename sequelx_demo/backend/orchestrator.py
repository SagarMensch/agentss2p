"""
SequelX agent orchestrator.

Each tab maps to a distinct S2P agent with its own system prompt,
reasoning style, and Mongo-backed context builder.
"""
import json
import os
import re
from typing import Dict, List

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

from agent_tools import fetch_bid_analysis
from contract_tools import (
    analyze_contract_risk,
    get_all_contracts,
    get_contract_details,
    get_contract_summary,
    get_obligations_by_contract,
    get_renewal_risks,
    get_upcoming_obligations,
)
from invoice_tools import (
    analyze_invoice_full,
    get_all_orders,
    get_processing_summary,
    get_stuck_orders,
)
from insights_tools import get_dashboard_summary
from supplier_tools import (
    analyze_supplier_full,
    get_all_suppliers,
    get_compliance_overview,
    get_compliance_records,
    get_certificate_verifications,
    get_supplier_details,
    get_supplier_summary,
)

load_dotenv()


def _build_provider_config() -> tuple[dict | None, str]:
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_api_key:
        return (
            {
                "api_key": groq_api_key,
                "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            },
            "Groq",
        )

    cerebras_api_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    if cerebras_api_key:
        return (
            {
                "api_key": cerebras_api_key,
                "base_url": os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
                "model": os.getenv("CEREBRAS_MODEL", "llama-3.3-70b"),
            },
            "Cerebras",
        )

    return None, "none"


PROVIDER_CONFIG, PROVIDER_NAME = _build_provider_config()

BID_SYSTEM_PROMPT = """You are SequelX Bid Intelligence, an executive procurement strategist.

Your job is to convert raw sourcing evidence into a decisive award recommendation.
Write like a senior sourcing leader presenting to the CFO and CPO.

Operating style:
- Lead with the recommendation.
- Compare vendors quantitatively.
- Explain why TCO matters more than base price.
- Tie the scoring back to the RFQ criteria.
- Flag commercial or compliance risks clearly.
- Use markdown tables when they improve readability.

Rules:
- Only use facts from the provided context.
- Do not invent values, vendors, dates, or status changes.
- Keep the answer sharp, commercial, and decision-oriented.

Context:
{context}"""

INVOICE_SYSTEM_PROMPT = """You are SequelX Invoice Intelligence, an AP control tower agent.

Your job is to triage invoice-processing risk faster than Ariba-style workflow screens.
You think like an operations commander: blocker-first, exception-first, action-first.

Operating style:
- Open with the current disposition: approve, review, or block.
- Explain where the workflow is stuck.
- Call out invoice anomalies and STP blockers separately.
- Quantify the STP score and what is preventing straight-through processing.
- End with the exact next action the AP or procurement team should take.
- Use markdown tables when useful.

Rules:
- Only use facts from the provided context.
- Do not invent workflow states or remediation steps that are not supported by the data.
- Keep the tone operational, crisp, and high-urgency when exceptions exist.

Context:
{context}"""

CONTRACT_SYSTEM_PROMPT = """You are SequelX Contract Intelligence, a legal risk desk agent.

Your job is to scan the contract estate for renewal exposure, drafting weakness,
and obligation risk before value leakage happens.
You think like a commercial counsel working alongside procurement leadership.

Operating style:
- Lead with the contract disposition: monitor, review, urgent, or immediate action.
- Explain renewal and lifecycle risk in plain commercial language.
- Call out missing clauses, overdue obligations, and draft-stage weaknesses.
- Show why the risk score is what it is.
- End with the exact next legal or procurement action.
- Use markdown structure when it improves scanability.

Rules:
- Only use facts from the provided context.
- Do not invent clause language or obligations that are not present.
- Keep the answer crisp, risk-oriented, and executive-ready.

Context:
{context}"""

SUPPLIER_SYSTEM_PROMPT = """You are SequelX Supplier DNA, a supplier-fit and trust intelligence agent.

Your job is to decode supplier strength, verification depth, and compliance resilience
before sourcing decisions are made.
You think like a category strategist working with supplier risk and onboarding teams.

Operating style:
- Open with the supplier's trust posture.
- Separate profile strength, compliance posture, and document verification.
- Explain the trust score drivers clearly.
- Highlight what is missing, weak, or unverifiable.
- End with the exact next action for onboarding, sourcing, or risk review.
- Use markdown when it improves readability.

Rules:
- Only use facts from the provided context.
- Do not invent certifications, countries, or verification outcomes.
- Keep the tone analytical, sharp, and supplier-focused.

Context:
{context}"""

INSIGHTS_SYSTEM_PROMPT = """You are SequelX Procurement Insights, an executive procurement market-and-risk cockpit.

Your job is to convert live procurement operating data into portfolio-level judgment.
You think like an investment-style operating committee reviewing spend, sourcing flow,
contract exposure, and supplier-risk concentration in one sitting.

Operating style:
- Lead with the portfolio call: stable, pressured, or urgent.
- Separate spend momentum, pipeline friction, sourcing flow, contract exposure, and supplier risk.
- Highlight concentration, weak throughput, and risk clusters clearly.
- Keep it board-ready and concise.
- End with the top three actions leadership should take next.
- Use markdown tables only when they help scanability.

Rules:
- Only use facts from the provided context.
- Do not invent savings, forecasts, or trends that are not supported by the data.
- Treat missing data as a signal and say so plainly.

Context:
{context}"""


class ChatRequest(BaseModel):
    message: str
    tabId: str
    history: List[Dict[str, str]] = []


def run_sequelx_agent(request: ChatRequest) -> tuple[str, list]:
    handlers = {
        "bid_intelligence": run_bid_agent,
        "invoice_intelligence": run_invoice_agent,
        "contract_intelligence": run_contract_agent,
        "supplier_dna": run_supplier_agent,
        "procurement_insights": run_insights_agent,
    }

    handler = handlers.get(request.tabId)
    if handler is None:
        return "This agent subsystem is not yet active.", []

    return handler(request)


def run_bid_agent(request: ChatRequest) -> tuple[str, list]:
    event_id = resolve_bid_event_id(request)
    if event_id:
        context_data = fetch_bid_analysis(event_id)
    else:
        context_data = json.dumps(
            {
                "instruction": (
                    "No RFQ event is selected. Ask the user to pick an RFQ from the dropdown "
                    "or provide an event ID such as RFQ-E1C8 or AUCTION-1B00."
                )
            }
        )

    fallback_answer = build_bid_local_summary(context_data, event_id)
    return run_llm_flow(
        request=request,
        system_prompt=BID_SYSTEM_PROMPT,
        context_data=context_data,
        fallback_answer=fallback_answer,
        entity_id=event_id,
    )


def run_invoice_agent(request: ChatRequest) -> tuple[str, list]:
    order_id = resolve_order_id(request)

    if order_id:
        raw_analysis = analyze_invoice_full(order_id)
        context_obj = {
            "orderAnalysis": compact_invoice_analysis(raw_analysis),
            "processingSummary": get_processing_summary(),
        }
    else:
        context_obj = {
            "processingSummary": get_processing_summary(),
            "stuckOrders": get_stuck_orders(),
            "sampleOrders": get_all_orders()[:10],
            "instruction": (
                "No order is selected. Use the control-tower summary to answer overview "
                "questions, or ask the user to pick an order for a detailed investigation."
            ),
        }

    context_data = json.dumps(context_obj, indent=2, default=str)
    fallback_answer = build_invoice_local_summary(context_obj, order_id)

    return run_llm_flow(
        request=request,
        system_prompt=INVOICE_SYSTEM_PROMPT,
        context_data=context_data,
        fallback_answer=fallback_answer,
        entity_id=order_id,
    )


def run_contract_agent(request: ChatRequest) -> tuple[str, list]:
    contract_id = resolve_contract_id(request)

    if contract_id:
        raw_details = get_contract_details(contract_id)
        obligations = get_obligations_by_contract(contract_id)
        risk = analyze_contract_risk(contract_id)
        context_obj = {
            "contractAnalysis": compact_contract_analysis(raw_details, obligations, risk),
            "renewalSummary": get_renewal_risks(),
            "contractSummary": get_contract_summary(),
        }
    else:
        context_obj = {
            "contractSummary": get_contract_summary(),
            "renewalSummary": get_renewal_risks(),
            "upcomingObligations": get_upcoming_obligations(),
            "sampleContracts": get_all_contracts()[:10],
            "instruction": (
                "No contract is selected. Use the portfolio summary to answer estate-level questions, "
                "or ask the user to pick a contract for dossier-level risk review."
            ),
        }

    context_data = json.dumps(context_obj, indent=2, default=str)
    fallback_answer = build_contract_local_summary(context_obj, contract_id)

    return run_llm_flow(
        request=request,
        system_prompt=CONTRACT_SYSTEM_PROMPT,
        context_data=context_data,
        fallback_answer=fallback_answer,
        entity_id=contract_id,
    )


def run_supplier_agent(request: ChatRequest) -> tuple[str, list]:
    supplier_id = resolve_supplier_id(request)

    if supplier_id:
        details = get_supplier_details(supplier_id)
        full = analyze_supplier_full(supplier_id)
        context_obj = {
            "supplierAnalysis": compact_supplier_analysis(full, details),
            "supplierSummary": get_supplier_summary(),
            "complianceOverview": get_compliance_overview(),
        }
    else:
        context_obj = {
            "supplierSummary": get_supplier_summary(),
            "complianceOverview": get_compliance_overview(),
            "sampleSuppliers": get_all_suppliers()[:12],
            "instruction": (
                "No supplier is selected. Use the network overview for supplier-base questions, "
                "or ask the user to pick a supplier for a trust and compliance review."
            ),
        }

    context_data = json.dumps(context_obj, indent=2, default=str)
    fallback_answer = build_supplier_local_summary(context_obj, supplier_id)

    return run_llm_flow(
        request=request,
        system_prompt=SUPPLIER_SYSTEM_PROMPT,
        context_data=context_data,
        fallback_answer=fallback_answer,
        entity_id=supplier_id,
    )


def run_insights_agent(request: ChatRequest) -> tuple[str, list]:
    context_obj = compact_insights_summary(get_dashboard_summary())
    context_data = json.dumps(context_obj, indent=2, default=str)
    fallback_answer = build_insights_local_summary(context_obj)

    return run_llm_flow(
        request=request,
        system_prompt=INSIGHTS_SYSTEM_PROMPT,
        context_data=context_data,
        fallback_answer=fallback_answer,
        entity_id=None,
    )


def run_llm_flow(
    request: ChatRequest,
    system_prompt: str,
    context_data: str,
    fallback_answer: str,
    entity_id: str | None,
) -> tuple[str, list]:
    messages = [{"role": "system", "content": system_prompt.format(context=context_data)}]
    for msg in request.history[-8:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": request.message})

    if PROVIDER_CONFIG is None:
        answer = (
            f"{fallback_answer}\n\n"
            "_Note: no LLM provider is configured. Showing Mongo-backed computed analysis only._"
        )
    else:
        try:
            answer = create_chat_completion(PROVIDER_CONFIG, messages, timeout=8)
        except Exception as exc:
            answer = (
                f"{fallback_answer}\n\n"
                f"_Note: {PROVIDER_NAME} reasoning failed ({str(exc)[:150]}). "
                "Showing Mongo-backed computed analysis instead._"
            )

    trace = [
        {
            "source": "SequelX Procurement Database",
            "eventId": entity_id or "overview",
            "dataPreview": context_data[:300] + ("..." if len(context_data) > 300 else ""),
        }
    ]
    return answer, trace


def create_chat_completion(provider_config: dict, messages: list[dict], timeout: int) -> str:
    response = requests.post(
        f"{provider_config['base_url'].rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {provider_config['api_key']}",
            "Content-Type": "application/json",
        },
        json={
            "model": provider_config["model"],
            "messages": messages,
            "temperature": 0.15,
            "max_tokens": 900,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["choices"][0]["message"]["content"]


def resolve_bid_event_id(request: ChatRequest) -> str | None:
    pattern = r"\b([A-Z]*-?[A-F0-9]{3,6})\b"

    match = re.findall(pattern, request.message, re.IGNORECASE)
    if match:
        return match[-1].upper()

    for message in reversed(request.history):
        prior = re.findall(pattern, message.get("content", ""), re.IGNORECASE)
        if prior:
            return prior[-1].upper()

    return None


def resolve_order_id(request: ChatRequest) -> str | None:
    pattern = r"\b[a-fA-F0-9]{24}\b"

    match = re.findall(pattern, request.message)
    if match:
        return match[-1]

    for message in reversed(request.history):
        prior = re.findall(pattern, message.get("content", ""))
        if prior:
            return prior[-1]

    return None


def resolve_contract_id(request: ChatRequest) -> str | None:
    object_id_pattern = r"\b[a-fA-F0-9]{24}\b"
    document_pattern = r"\bDI-\d{8,}\b"

    for pattern in [document_pattern, object_id_pattern]:
        match = re.findall(pattern, request.message, re.IGNORECASE)
        if match:
            return match[-1]

    for message in reversed(request.history):
        for pattern in [document_pattern, object_id_pattern]:
            prior = re.findall(pattern, message.get("content", ""), re.IGNORECASE)
            if prior:
                return prior[-1]

    return None


def resolve_supplier_id(request: ChatRequest) -> str | None:
    pattern = r"\b[a-fA-F0-9]{24}\b"
    match = re.findall(pattern, request.message)
    if match:
        return match[-1]

    for message in reversed(request.history):
        prior = re.findall(pattern, message.get("content", ""))
        if prior:
            return prior[-1]

    return None


def build_bid_local_summary(context_data: str, event_id: str | None) -> str:
    try:
        data = json.loads(context_data)
    except json.JSONDecodeError:
        return "Bid analysis data could not be parsed."

    if "instruction" in data:
        return data["instruction"]

    if "error" in data:
        return data["error"]

    recommendation = data.get("recommendation", {})
    vendors = data.get("vendors", [])
    rfq = data.get("rfq", {})

    lines = [
        f"Recommendation: {recommendation.get('winner', 'No clear winner')} for event {event_id or rfq.get('eventId', 'unknown')}.",
        recommendation.get("reason", ""),
        f"RFQ: {rfq.get('title', 'Untitled')} | Category: {rfq.get('category', 'N/A')} | Status: {rfq.get('status', 'N/A')}",
        "",
        "Vendor comparison:",
    ]

    for index, vendor in enumerate(vendors[:5], start=1):
        vendor_label = vendor.get("vendorName") or f"Bid {index}"
        lines.append(
            f"- {vendor_label}: TCO {vendor.get('tco', {}).get('total', 0)}, "
            f"score {vendor.get('scoring', {}).get('percentage', 0)}%, "
            f"win probability {vendor.get('winProbability', 0)}%, "
            f"risk {vendor.get('riskLevel', 'N/A')}"
        )

    return "\n".join(line for line in lines if line is not None)


def build_invoice_local_summary(context_obj: dict, order_id: str | None) -> str:
    if order_id and "orderAnalysis" in context_obj:
        analysis = context_obj["orderAnalysis"]
        order = analysis.get("orderDetails", {})
        anomalies = analysis.get("anomalies", {})
        stp = analysis.get("stpAnalysis", {})

        lines = [
            f"Invoice disposition for order {order_id}: {analysis.get('recommendation', 'REVIEW')}",
            (
                f"Workflow states: PO {order.get('poStatus', 'n/a')}, ASN {order.get('asnStatus', 'n/a')}, "
                f"Invoice {order.get('invoiceStatus', 'n/a')}, GRN {order.get('grnStatus', 'n/a')}, "
                f"Payment {order.get('paymentStatus', 'n/a')}"
            ),
            (
                f"STP score: {stp.get('stpScore', 0)} "
                f"({stp.get('stpLikelihood', 'LOW')}) | "
                f"Anomalies: {anomalies.get('anomalyCount', 0)} "
                f"({anomalies.get('status', 'UNKNOWN')})"
            ),
        ]

        blockers = stp.get("blockers", [])
        if blockers:
            lines.append("Top blockers: " + ", ".join(blockers[:5]))

        anomaly_list = anomalies.get("anomalies", [])
        if anomaly_list:
            preview = [a.get("type", "UNKNOWN") for a in anomaly_list[:5]]
            lines.append("Key anomalies: " + ", ".join(preview))

        return "\n".join(lines)

    summary = context_obj.get("processingSummary", {})
    stuck = context_obj.get("stuckOrders", {})

    return (
        "Invoice control tower overview:\n"
        f"- Total orders: {summary.get('totalOrders', 0)}\n"
        f"- Fully processed: {summary.get('fullyProcessed', 0)}\n"
        f"- STP rate: {summary.get('stpRate', 0)}%\n"
        f"- Stuck orders surfaced: {stuck.get('stuckOrdersCount', 0)}\n"
        "Ask for a specific order to investigate anomaly and workflow risk in detail."
    )


def build_contract_local_summary(context_obj: dict, contract_id: str | None) -> str:
    if contract_id and "contractAnalysis" in context_obj:
        analysis = context_obj["contractAnalysis"]
        details = analysis.get("details", {})
        risk = analysis.get("risk", {})
        obligations = analysis.get("obligations", [])

        lines = [
            f"Contract disposition for {contract_id}: {risk.get('recommendation', 'REVIEW')}",
            (
                f"Profile: {details.get('contractType', 'Unknown type')} | "
                f"Status {details.get('status', 'Unknown')} | "
                f"Value {details.get('contractValue', 'n/a')} {details.get('currency', '')}"
            ),
            (
                f"Risk score: {risk.get('riskScore', 0)} ({risk.get('riskLevel', 'LOW')}) | "
                f"Clauses: {risk.get('clausesCount', 0)} | "
                f"Obligations: {risk.get('obligationsCount', 0)}"
            ),
        ]

        risk_list = risk.get("risks", [])
        if risk_list:
            lines.append("Top risks: " + ", ".join(r.get("type", "UNKNOWN") for r in risk_list[:5]))

        if obligations:
            lines.append("Upcoming / overdue obligations: " + str(len(obligations)))

        return "\n".join(lines)

    summary = context_obj.get("contractSummary", {})
    renewals = context_obj.get("renewalSummary", {})
    return (
        "Contract estate overview:\n"
        f"- Total contracts: {summary.get('totalContracts', 0)}\n"
        f"- Expiring in 30 days: {summary.get('expiringIn30Days', 0)}\n"
        f"- Expiring in 60-day watchlist: {renewals.get('totalExpiring', 0)}\n"
        "Pick a contract to run a dossier-level risk review."
    )


def build_supplier_local_summary(context_obj: dict, supplier_id: str | None) -> str:
    if supplier_id and "supplierAnalysis" in context_obj:
        analysis = context_obj["supplierAnalysis"]
        supplier = analysis.get("supplier", {})
        trust = analysis.get("trustAnalysis", {})
        summary = analysis.get("summary", {})

        lines = [
            f"Supplier posture for {supplier.get('organisationName', supplier_id)}: {trust.get('trustLevel', 'POOR')}",
            (
                f"Profile: status {supplier.get('status', 'unknown')} | "
                f"type {supplier.get('organisationType', 'Unknown')} | "
                f"location {supplier.get('city', 'n/a')}, {supplier.get('country', 'n/a')}"
            ),
            (
                f"Trust score: {trust.get('trustScore', 0)}/{trust.get('maxScore', 100)} | "
                f"Compliance records: {summary.get('complianceCount', 0)} | "
                f"Certificates: {summary.get('certificateCount', 0)}"
            ),
        ]

        factors = trust.get("factors", [])
        if factors:
            lines.append("Key factors: " + ", ".join(f.get("factor", "UNKNOWN") for f in factors[:5]))

        return "\n".join(lines)

    supplier_summary = context_obj.get("supplierSummary", {})
    compliance = context_obj.get("complianceOverview", {})
    return (
        "Supplier network overview:\n"
        f"- Total suppliers: {supplier_summary.get('totalSuppliers', 0)}\n"
        f"- Compliance records: {compliance.get('totalRecords', 0)}\n"
        "Pick a supplier to open a trust and compliance profile."
    )


def compact_invoice_analysis(analysis: dict) -> dict:
    order = analysis.get("orderDetails", {})
    values = order.get("values", {}) if isinstance(order.get("values"), dict) else {}
    line_items = order.get("lineItems", []) if isinstance(order.get("lineItems"), list) else []
    anomalies = analysis.get("anomalies", {})
    stp = analysis.get("stpAnalysis", {})

    return {
        "orderDetails": {
            "orderId": order.get("orderId"),
            "poStatus": order.get("poStatus"),
            "asnStatus": order.get("asnStatus"),
            "paymentStatus": order.get("paymentStatus"),
            "invoiceStatus": order.get("invoiceStatus"),
            "grnStatus": order.get("grnStatus"),
            "lineItemsCount": len(line_items),
            "sampleLineItems": [
                {
                    "description": item.get("description"),
                    "quantity": item.get("quantity"),
                    "rate": item.get("rate"),
                    "totalAmount": item.get("totalAmount"),
                }
                for item in line_items[:5]
            ],
            "values": {
                "invoiceNo": values.get("invoiceNo"),
                "invoiceDate": values.get("invoiceDate"),
                "purchaseOrderNo": values.get("purchaseOrderNo"),
                "buyerName": values.get("buyerName"),
                "vendorName": values.get("vendorName"),
                "buyerGSTIN": values.get("buyerGSTIN"),
                "vendorGSTIN": values.get("vendorGSTIN"),
                "netPayableAmount": values.get("netPayableAmount"),
            },
        },
        "anomalies": {
            "anomalyCount": anomalies.get("anomalyCount", 0),
            "anomalyScore": anomalies.get("anomalyScore", 0),
            "status": anomalies.get("status"),
            "anomalies": anomalies.get("anomalies", [])[:10],
        },
        "stpAnalysis": {
            "stpScore": stp.get("stpScore", 0),
            "stpLikelihood": stp.get("stpLikelihood"),
            "blockers": stp.get("blockers", [])[:10],
            "canProceedWithoutApproval": stp.get("canProceedWithoutApproval"),
        },
        "recommendation": analysis.get("recommendation"),
    }


def compact_contract_analysis(details: dict, obligations: list, risk: dict) -> dict:
    compact_details = {
        "contractId": details.get("contractId"),
        "documentId": details.get("documentId"),
        "status": details.get("status"),
        "contractType": details.get("contractType"),
        "contractValue": details.get("contractValue"),
        "currency": details.get("currency"),
        "startDate": details.get("startDate"),
        "endDate": details.get("endDate"),
        "clausesSample": details.get("clauses", [])[:5],
    }

    return {
        "details": compact_details,
        "risk": risk,
        "obligations": obligations[:10],
    }


def compact_supplier_analysis(full: dict, details: dict) -> dict:
    return {
        "supplier": {
            "orgId": details.get("orgId"),
            "organisationName": details.get("organisationName"),
            "organisationType": details.get("organisationType"),
            "status": details.get("status"),
            "country": details.get("country"),
            "city": details.get("city"),
            "website": details.get("website"),
            "taxId": details.get("taxId"),
            "createdAt": details.get("createdAt"),
        },
        "trustAnalysis": full.get("trustAnalysis", {}),
        "summary": full.get("summary", {}),
        "complianceRecords": full.get("complianceRecords", [])[:10],
        "certificateRecords": full.get("certificateRecords", [])[:10],
    }


def compact_insights_summary(summary: dict) -> dict:
    spend = summary.get("spendAnalysis", {})
    pipeline = summary.get("pipelineStatus", {})
    rfq = summary.get("rfqPerformance", {})
    contracts = summary.get("contractHealth", {})
    compliance = summary.get("complianceGaps", {})

    return {
        "kpis": summary.get("kpis", {}),
        "spend": {
            "totalSpend": spend.get("totalSpend", 0),
            "totalOrders": spend.get("totalOrders", 0),
            "avgOrderValue": spend.get("avgOrderValue", 0),
            "topCategories": spend.get("spendByCategory", [])[:5],
            "topSuppliers": spend.get("topSuppliers", [])[:5],
        },
        "pipeline": {
            "totalOrders": pipeline.get("totalOrders", 0),
            "completedOrders": pipeline.get("completedOrders", 0),
            "completionRate": pipeline.get("completionRate", 0),
            "statusBreakdown": pipeline.get("statusBreakdown", {}),
        },
        "sourcing": {
            "totalRfqs": rfq.get("totalRfqs", 0),
            "totalBids": rfq.get("totalBids", 0),
            "avgBidsPerRfq": rfq.get("avgBidsPerRfq", 0),
            "topCategories": rfq.get("topCategories", [])[:5],
            "rfqStatusBreakdown": rfq.get("rfqStatusBreakdown", {}),
        },
        "contracts": {
            "totalContracts": contracts.get("totalContracts", 0),
            "activeContracts": contracts.get("activeContracts", 0),
            "expiredContracts": contracts.get("expiredContracts", 0),
            "expiringIn30Days": contracts.get("expiringIn30Days", 0),
            "overdueObligations": contracts.get("overdueObligations", 0),
        },
        "suppliers": {
            "totalSuppliers": compliance.get("totalSuppliers", 0),
            "suppliersWithGaps": compliance.get("suppliersWithGaps", 0),
            "criticalGaps": compliance.get("criticalGaps", 0),
            "moderateGaps": compliance.get("moderateGaps", 0),
            "gapDetails": compliance.get("gapDetails", [])[:5],
        },
    }


def build_insights_local_summary(context_obj: dict) -> str:
    spend = context_obj.get("spend", {})
    pipeline = context_obj.get("pipeline", {})
    sourcing = context_obj.get("sourcing", {})
    contracts = context_obj.get("contracts", {})
    suppliers = context_obj.get("suppliers", {})

    top_categories = spend.get("topCategories", [])
    top_suppliers = spend.get("topSuppliers", [])

    lines = [
        "Portfolio call: pressured.",
        (
            f"Spend coverage: total spend {spend.get('totalSpend', 0)} across "
            f"{spend.get('totalOrders', 0)} orders, average order value {round(spend.get('avgOrderValue', 0), 2)}."
        ),
        (
            f"Pipeline: {pipeline.get('completedOrders', 0)}/{pipeline.get('totalOrders', 0)} completed "
            f"({round(pipeline.get('completionRate', 0), 2)}% completion)."
        ),
        (
            f"Sourcing flow: {sourcing.get('totalRfqs', 0)} RFQs, {sourcing.get('totalBids', 0)} bids, "
            f"{round(sourcing.get('avgBidsPerRfq', 0), 2)} bids per RFQ."
        ),
        (
            f"Contract exposure: {contracts.get('totalContracts', 0)} contracts, "
            f"{contracts.get('expiringIn30Days', 0)} expiring in 30 days, "
            f"{contracts.get('overdueObligations', 0)} overdue obligations."
        ),
        (
            f"Supplier risk: {suppliers.get('suppliersWithGaps', 0)} suppliers with gaps, "
            f"{suppliers.get('criticalGaps', 0)} critical."
        ),
    ]

    if top_categories:
        cat_preview = ", ".join(
            f"{item.get('category', 'Unknown')} ({item.get('amount', 0)})"
            for item in top_categories[:3]
        )
        lines.append(f"Top categories: {cat_preview}.")

    if top_suppliers:
        supplier_preview = ", ".join(
            f"{item.get('supplier', 'Unknown')} ({item.get('spend', 0)})"
            for item in top_suppliers[:3]
        )
        lines.append(f"Top suppliers: {supplier_preview}.")

    lines.append(
        "Leadership actions: fix stalled invoice flow, raise sourcing competition in low-bid events, and clean supplier compliance gaps."
    )
    return "\n".join(lines)
