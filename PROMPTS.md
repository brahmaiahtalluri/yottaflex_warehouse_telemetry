# AI Collaboration & Prompt History Log

This document complies with YottaFlex AI Recruitment Drive Guideline 03: Transparent LLM Utilization.

---

## 1. Executive Summary of AI Assistance

* **Where AI Accelerated Development:** 
  * Generating synthetic cold-chain data matching fixed seed `20261022`.
  * Scaffolded boilerplate Java Spring Boot controllers, records, and React dashboard components.
  * Debugging Vite proxy rules, fast-refresh preambles, and PowerShell execution syntax.
* **Where Heavy Reliance Occurred:**
  * Initial mathematical formulation of precision, recall, and F1 evaluation matching ground-truth edge cases.
  * Designing responsive CSS layouts for the multi-zone telemetry dashboard.
* **What I Personally Reviewed, Changed & Validated:**
  * Cleaned up in-memory collections (`TelemetryDataService`) to avoid runtime memory leaks across 15,000 readings.
  * Audited and corrected cross-origin request headers and proxy routings between Vite (:5173) and Tomcat (:8080).
  * Validated the exact ground-truth scenario outputs ($TP=25, FP=0, FN=0$) and confirmed financial valuation calculation of $834,796.36.
  * Isolated Git tracking to the local project folder and audited repository sanitation.

---

## 2. Chronological Prompt History Log

### Phase 1: Problem Formulation & Architecture Setup
* **Prompt 1:** "Design a warehouse zone telemetry system with 10 warehouses, 100 zones, 500 sensors, and 15,000 readings using seed 20261022. I need a Spring Boot backend and React Vite frontend."
* **Prompt 2:** "Generate deterministic synthetic telemetry data in CSV and JSON formats covering temperature excursions, telemetry transmission dropouts, and door breaches."
* **Prompt 3:** "Define Java 24 / Spring Boot records and service layer for in-memory indexing of 15k sensor readings and 500 inventory lots."

### Phase 2: Anomaly Detection & Financial Valuation Logic
* **Prompt 4:** "Implement the TelemetryEvaluationService to compare detected excursions against ground_truth.csv. It must calculate Precision, Recall, and F1 score."
* **Prompt 5:** "How do I calculate the exact financial risk for compromised lots based on zone storage temperature limits and unit costs?"
* **Prompt 6:** "Write REST endpoints for 17 telemetry data services including alarms, inspections, remediations, and audit trail events."

### Phase 3: Frontend Integration & State Synchronization
* **Prompt 7:** "Create an App.jsx dashboard in React with dark mode, showing KPI summary cards, alarm logs, and real-time synchronization with Spring Boot on port 8080."
* **Prompt 8:** "Configure vite.config.js reverse proxy to forward /api/* requests to localhost:8080 without CORS preflight failures."
* **Prompt 9:** "Fix Vite React preamble error: '@vitejs/plugin-react can't detect preamble'."

### Phase 4: Verification, Security & Repository Sanitation
* **Prompt 10:** "Verify endpoint http://localhost:8080/api/overview via PowerShell to ensure seed 20261022 and 100% F1 score are returning."
* **Prompt 11:** "Clean git tracking where accidental user root folder was tracked and prepare a clean public repository with .gitignore."
* **Prompt 12:** "Write a 3-minute technical demonstration walkthrough script covering terminal execution, API metrics, and UI sync."