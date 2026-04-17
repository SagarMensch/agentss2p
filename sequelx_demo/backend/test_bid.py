from agent_tools import fetch_bid_analysis
import json

data = json.loads(fetch_bid_analysis("RFQ-E1C8"))
print("RFQ:", data["rfq"]["title"], "-", data["rfq"]["status"])
print("Bids:", data["bidCount"])
for v in data["vendors"]:
    print(f"  {v['vendorName']}: base={v['baseAmount']}, TCO={v['tco']['total']}, score={v['scoring']['percentage']}%, win={v['winProbability']}%")
    if v["riskFlags"]:
        print(f"    Risks: {v['riskFlags']}")
print("Recommended Winner:", data["recommendation"]["winner"])
