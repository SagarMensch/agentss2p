# SEQUELX Bid Intelligence Engine
## Technical Documentation & Demo Guide

---

# 1. PRODUCT OVERVIEW

**SEQUELX Bid Intelligence** is an AI-powered procurement analytics engine that automatically analyzes vendor bids, calculates Total Cost of Ownership (TCO), scores bids against evaluation criteria, and predicts winners using probabilistic modeling.

---

# 2. AI/ML LOGIC EXPLANATION

## 2.1 Total Cost of Ownership (TCO) Analysis

**What it does:** Calculates the TRUE cost of each vendor bid beyond just the base price.

**AI/ML Logic:**
```
TCO = Base Price + Freight + Insurance + Installation + Import Duties + Packaging + Other Costs
```

**Why it's AI:** The system intelligently pulls ALL cost components from the database and performs weighted aggregation that procurement teams normally do manually in Excel.

---

## 2.2 Bid Scoring Against Evaluation Criteria

**What it does:** Scores each vendor bid based on the RFQ's predefined evaluation criteria weights.

**AI/ML Logic:**
```
Price Score = (Lowest Base Price / Vendor's Base Price) × Price Weight

Example:
- If lowest price = 1000 and vendor price = 2000
- Price weight in RFQ = 40 points
- Vendor Score = (1000/2000) × 40 = 20 points
```

**Why it's AI:** The system parses the RFQ's evaluation criteria (stored as JSON in MongoDB) and applies weighted scoring - this is essentially a **Multi-Criteria Decision Making (MCDM)** algorithm.

---

## 2.3 Winner Prediction (Probabilistic Modeling)

**What it does:** Predicts which vendor will win based on multiple factors.

**AI/ML Logic:**
```
Win Probability = Base (50%) + Budget Factor (25%) + Price Factor (25%)

Where:
- Budget Factor = 25% if vendor's TCO is within budget range
- Price Factor = 25% if vendor has the lowest base price
- Otherwise = 0% for each factor
```

**Example Calculation:**
| Vendor | TCO | Within Budget? | Lowest Price? | Win Prob |
|--------|-----|----------------|---------------|----------|
| Vendor A | 5000 | YES | YES | 50+25+25 = 100% |
| Vendor B | 5500 | YES | NO | 50+25+0 = 75% |
| Vendor C | 6000 | NO | NO | 50+0+0 = 50% |

**Why it's AI:** This is **probabilistic modeling** - the same approach used in predictive analytics. It assigns weights to different factors and calculates a probability score.

---

# 3. TECHNICAL ARCHITECTURE

## 3.1 Data Flow

```
User selects RFQ
       ↓
Frontend sends event_id to Backend API
       ↓
Backend fetches from MongoDB:
  - RFQ details (criteria, budget, items)
  - Vendor Bids (base amount, commercial details)
       ↓
Backend calculates:
  - TCO for each vendor
  - Scores against criteria weights
  - Win probability
       ↓
Frontend displays results in dark-themed UI
```

## 3.2 Technology Stack

| Layer | Technology |
|-------|-------------|
| Frontend | Next.js 16 + React 19 + TypeScript |
| Backend | FastAPI (Python) |
| Database | MongoDB Atlas |
| AI/ML | Algorithmic (TCO, Weighted Scoring, Probability) |

---

# 4. MONGODB DATA STRUCTURE

## 4.1 RFQ Collection
```json
{
  "eventId": "RFQ-E3AC",
  "eventTitle": "Testinf For Draft2",
  "procurementCategory": "IT Software",
  "rfiValues": {
    "budgetRange": "5000000-6000000"
  },
  "rfqValues": {
    "evaluationCriteria": {
      "totalPrice": 40,
      "paymentTerms": 10,
      "warrantyPeriod": 6,
      "technicalCompliance": 0,
      "experienceReferences": 0,
      "implementationTimeline": 0,
      "afterSalesSupport": 0,
      "trainingProvision": 0,
      "sustainabilityPractices": 0,
      "minimumScore": 0
    }
  }
}
```

## 4.2 Vendor Bids Collection
```json
{
  "eventId": "RFQ-E3AC",
  "vendorName": "Demovendor",
  "baseAmount": 5313600,
  "commercial": {
    "currency": "INR",
    "freightCost": 0,
    "insuranceCost": 0,
    "installationCost": 34,
    "importDuties": 0,
    "packagingCost": 0
  },
  "status": "SUBMITTED"
}
```

---

# 5. API ENDPOINTS

## 5.1 Get All RFQs
```
GET http://localhost:8000/api/rfqs
```

## 5.2 Analyze Bid (Full Analysis)
```
POST http://localhost:8000/api/bid
Body: {
  "action": "analyze",
  "event_id": "RFQ-E3AC"
}
```

**Response includes:**
- RFQ Details
- Submitted Bids
- TCO Analysis
- Evaluation Scoring
- Winner Prediction

---

# 6. HOW TO DEMO

## 6.1 Step-by-Step Demo Flow

1. **Open the application** - Navigate to http://localhost:3000
2. **Click "Bid Intelligence"** tab in the sidebar
3. **Select an RFQ** from the dropdown (or enter manually)
4. **Click "ANALYZE"** button

## 6.2 What to Show During Demo

### Slide 1: "Traditional Procurement"
- "In traditional procurement, buyers manually compare Excel sheets"
- "They calculate TCO in calculator"
- "They score bids by hand"

### Slide 2: "SEQUELX AI Intelligence"
- "Our AI engine automates ALL of this"
- Click ANALYZE
- Show the results

### Slide 3: Explain Each Section

**TCO Analysis:**
"See this table? We're calculating Total Cost of Ownership - not just the base price, but ALL costs including freight, installation, duties. This is what procurement professionals do in Excel, but we do it automatically."

**Evaluation Criteria Scoring:**
"Every RFQ has evaluation criteria weights - in this case price is 40 points, payment terms 10 points, warranty 6 points. Our AI scores each vendor against these weights automatically."

**Winner Prediction:**
"Our probabilistic model predicts the winner. It's using the same logic as predictive analytics - base probability plus factors for budget alignment and price competitiveness."

---

# 7. COMPETITIVE ADVANTAGE vs SAP ARIBA

| Feature | SAP Ariba | SEQUELX |
|---------|-----------|---------|
| TCO Calculation | Manual | **Automated** |
| Bid Scoring | Basic | **Weighted Criteria** |
| Winner Prediction | None | **AI Prediction** |
| Real-time Analysis | Batch | **Instant** |
| Custom Criteria | Limited | **Fully Configurable** |

---

# 8. FUTURE AI/ML ENHANCEMENTS

The current system uses **algorithmic AI**. Future enhancements could include:

- **LLM Integration**: Natural language insights about each bid
- **Anomaly Detection**: ML-based detection of suspicious pricing patterns
- **Historical Learning**: Learning from past bid outcomes to improve predictions
- **Supplier Ranking**: ML-based supplier performance scoring

---

# 9. RUNNING THE APPLICATION

## Backend
```powershell
cd C:\Users\sagar\Downloads\agents2p\sequelx_demo\backend
python main.py
```

## Frontend
```powershell
cd C:\Users\sagar\Downloads\agents2p\sequelx_demo\frontend
npm run dev
```

## Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

---

*Document Version: 1.0*
*Last Updated: April 2026*
