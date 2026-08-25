# Payment Recovery Agent

AI-assisted system for diagnosing payment failures and recommending recovery actions.
Built for Razorpay Buildathon — Track 3: Payment Degradation → Root Cause → Recovery.

## Structure
- `docs/failure_taxonomy.md` — researched failure codes + reasoning (start here)
- `logs/decisions.md` — personal decision log / pitch notes
- `src/rule_engine.py` — Layer 1: deterministic rules for known failure codes
- `requirements.txt` — Python dependencies

## Status
Step 1 complete: rule engine built and tested.
Next: LLM escalation layer for ambiguous cases.
