from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from orchestrator import run_sequelx_agent, ChatRequest
from agent_tools import list_rfqs_for_dropdown
from contract_tools import get_all_contracts
from insights_tools import get_dashboard_summary
from invoice_tools import get_all_orders
from supplier_tools import get_all_suppliers

app = FastAPI(title="SequelX Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        response, trace = await run_in_threadpool(run_sequelx_agent, request)
        return {"response": response, "trace": trace}
    except Exception as e:
        return {"response": f"Error: {str(e)}", "trace": []}


@app.get("/api/rfqs")
def get_rfqs():
    try:
        return {"data": list_rfqs_for_dropdown()}
    except Exception as e:
        return {"data": [], "error": str(e)}


@app.get("/api/orders")
def get_orders():
    try:
        return {"data": get_all_orders()}
    except Exception as e:
        return {"data": [], "error": str(e)}


@app.get("/api/contracts")
def get_contracts():
    try:
        return {"data": get_all_contracts()}
    except Exception as e:
        return {"data": [], "error": str(e)}


@app.get("/api/suppliers")
def get_suppliers():
    try:
        return {"data": get_all_suppliers()}
    except Exception as e:
        return {"data": [], "error": str(e)}


@app.get("/api/insights")
def get_insights():
    try:
        return {"data": get_dashboard_summary()}
    except Exception as e:
        return {"data": {}, "error": str(e)}


@app.get("/health")
def health():
    return {"status": "ok"}
