"""
Comparison Engine - runs the same batch through both systems and estimates
recovered revenue for each.

IMPORTANT HONESTY NOTE: we don't have access to real bank-side success data
(no live API key, test mode doesn't simulate customer behavior). So recovery
is ESTIMATED using success-rate assumptions per category, clearly labeled as
estimates, not measured fact. This is stated explicitly in the dashboard/pitch -
never present an estimate as if it were a measured real-world result.

Where the estimates come from (reasoning, not made up):
- Category A (retry, temporary issue): retrying at the RIGHT time works often
  -> smart system uses researched delay, baseline retries blind at 24h
- Category B (needs customer action, not a timing issue): a blind retry
  almost never works because the underlying problem wasn't fixed
- Category C (bank's fault, temporary): similar to A, timing matters
- Category D (LLM-handled, genuinely ambiguous): moderate, uncertain success
"""

from src import simulator, orchestrator, baseline, audit_trail

# (category -> success rate) if retried at the RIGHT time (smart system)
SMART_SUCCESS_RATE = {
    "A": 0.65,   # correctly-timed retry on a temporary issue
    "B": 0.55,   # notifying the customer to fix something works over half the time
    "C": 0.60,   # bank issue, correctly delayed retry
    "D": 0.40,   # LLM-handled ambiguous case, genuinely less certain
}

# Baseline retries EVERYTHING blind, 24h later, regardless of category.
# A blind retry on a Category B failure (needs a real fix) rarely works.
BASELINE_SUCCESS_RATE = {
    "A": 0.45,   # got lucky on timing sometimes, but not researched
    "B": 0.10,   # blind retry on a "needs customer action" failure - rarely works
    "C": 0.35,   # blind retry on bank issue - moderate luck
    "D": 0.20,   # blind retry on a genuinely ambiguous case - mostly doesn't work
}


def run_comparison(n: int = 60, seed: int = 42) -> dict:
    batch = simulator.generate_batch(n=n, seed=seed)

    smart_recovered = 0.0
    baseline_recovered = 0.0
    smart_attempts_wasted = 0
    baseline_attempts_wasted = 0

    for payment in batch:
        # --- Smart system ---
        decision = orchestrator.process_failed_payment(
            payment_id=payment["payment_id"],
            error_code=payment["error_code"],
            amount=payment["amount"],
            payment_method=payment["payment_method"],
            failure_count=payment["failure_count"],
        )
        audit_trail.log_decision(decision)

        smart_rate = SMART_SUCCESS_RATE.get(decision.category, 0.3)
        # Deterministic "expected value" rather than random simulation -
        # keeps results reproducible for the same seed, which matters for
        # an honest, repeatable demo.
        smart_recovered += payment["amount"] * smart_rate
        if smart_rate < 0.5:
            smart_attempts_wasted += 1

        # --- Naive baseline ---
        base_decision = baseline.process_failed_payment_naive(
            payment_id=payment["payment_id"], error_code=payment["error_code"]
        )
        # Baseline doesn't know the category - so we look it up from the
        # smart system's own classification, purely to score what WOULD
        # have happened if a blind retry were applied to this same failure.
        base_rate = BASELINE_SUCCESS_RATE.get(decision.category, 0.2)
        baseline_recovered += payment["amount"] * base_rate
        if base_rate < 0.5:
            baseline_attempts_wasted += 1

    total_at_risk = sum(p["amount"] for p in batch)

    return {
        "n_payments": n,
        "total_at_risk": round(total_at_risk, 2),
        "smart_recovered": round(smart_recovered, 2),
        "baseline_recovered": round(baseline_recovered, 2),
        "improvement_rs": round(smart_recovered - baseline_recovered, 2),
        "improvement_pct": round(
            (smart_recovered - baseline_recovered) / baseline_recovered * 100, 1
        ) if baseline_recovered > 0 else 0,
        "smart_wasted_attempts": smart_attempts_wasted,
        "baseline_wasted_attempts": baseline_attempts_wasted,
    }


if __name__ == "__main__":
    results = run_comparison(n=60)

    print("=== Baseline vs Smart System Comparison ===\n")
    print(f"Batch size:              {results['n_payments']} failed payments")
    print(f"Total revenue at risk:   Rs. {results['total_at_risk']:,.2f}\n")

    print(f"Naive baseline recovered: Rs. {results['baseline_recovered']:,.2f}")
    print(f"Smart system recovered:   Rs. {results['smart_recovered']:,.2f}")
    print(f"Improvement:              Rs. {results['improvement_rs']:,.2f} "
          f"({results['improvement_pct']}% more)\n")

    print(f"Wasted retry attempts (baseline): {results['baseline_wasted_attempts']}")
    print(f"Wasted retry attempts (smart):    {results['smart_wasted_attempts']}")

    print("\nNOTE: recovery figures are ESTIMATES based on researched success-rate "
          "assumptions per failure category, not measured real-world outcomes "
          "(no live payment gateway data available in test mode).")
