from database import get_collection
import json
from bson import ObjectId
from collections import Counter

class Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId): return str(o)
        return super().default(o)

rfqs = get_collection('rfqs')
bids = get_collection('vendorbids')

print("RFQ statuses:", rfqs.distinct('status'))
print("Categories:", rfqs.distinct('procurementCategory'))
print()

# Bids with real amounts
count_with_amount = bids.count_documents({"baseAmount": {"$gt": 0}})
print(f"Bids with baseAmount > 0: {count_with_amount}")

bids_with_amount = list(bids.find({"baseAmount": {"$gt": 0}}).limit(3))
for b in bids_with_amount:
    print(json.dumps({
        'eventId': b.get('eventId'),
        'vendorName': b.get('vendorName'),
        'baseAmount': b.get('baseAmount'),
        'totalAmount': b.get('totalAmount'),
        'commercial': b.get('commercial'),
        'status': b.get('status'),
    }, indent=2, cls=Encoder, default=str))
    print('---')

# Events with multiple bids
all_bids = list(bids.find({}, {'eventId': 1}))
event_counts = Counter(b['eventId'] for b in all_bids)
multi = {k:v for k,v in event_counts.items() if v > 1}
print(f"Events with multiple bids: {multi}")
