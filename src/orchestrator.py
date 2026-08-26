"""
Orchestrator - the core routing logic of the recovery system.

This is the single entry point every failed payment goes through. It embodies
the central design decision of this project: try the free, fast, explainable
rule engine FIRST. Only pay the cost (time + money) of an LLM call when the
rule engine genuinely has no confident answer.

This file is deliberately small. The intelligence lives in:
- docs/failure_taxonomy.md   (the research)
- src/rule_engine.py         (Layer 1 - deterministic)
- src/llm_escalation.py      (Layer 2 - reasoning, for ambiguous cases only)
This file just decides WHICH layer handles a given payment, and records why.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from src import rule_engine
from src import llm_escalation


@dataclass
class FinalDecision:
    payment_id: str
    error_code: str
    handled_by: str      # "rule_engine" or "llm_escalation"
    action: str
    category: str
    reasoning: str
    timestamp: str


def process_failed_payment(payment_id: str, error_code: str, amount: float,
                            payment_method: str = "UPI",
                            failure_count: int = 1) -> FinalDecision:
    """
    The main pipeline. Every failed payment flows through here.
    """
    rule_result = rule_engine.evaluate(error_code)

    if rule_result.matched:
        # Layer 1 handled it - fast, free, explainable. No LLM touched.
        return FinalDecision(
            payment_id=payment_id,
            error_code=error_code,
            handled_by="rule_engine",
            action=rule_result.action,
            category=rule_result.category,
            reasoning=rule_result.reasoning,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Layer 1 had no confident answer - escalate to Layer 2.
    payment_context = {
        "error_code": error_code,
        "payment_method": payment_method,
        "amount": amount,
        "failure_count": failure_count,
        "rule_engine_note": rule_result.reasoning,
    }
    llm_result = llm_escalation.evaluate(payment_context)

    return FinalDecision(
        payment_id=payment_id,
        error_code=error_code,
        handled_by="llm_escalation",
        action=llm_result.action,
        category=llm_result.category,
        reasoning=llm_result.reasoning,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    # Manual sanity check - a mixed batch showing BOTH paths firing correctly
    test_batch = [
        {"payment_id": "pay_001", "error_code": "insufficient_funds", "amount": 499},
        {"payment_id": "pay_002", "error_code": "card_expired", "amount": 1200},
        {"payment_id": "pay_003", "error_code": "vpa_resolution_failed", "amount": 799},
        {"payment_id": "pay_004", "error_code": "some_never_seen_code", "amount": 250},
    ]

    print(f"LLM mock mode active: {llm_escalation.MOCK_MODE}\n")

    handled_by_rule_engine = 0
    handled_by_llm = 0

    for payment in test_batch:
        decision = process_failed_payment(**payment)
        print(f"{decision.payment_id} ({decision.error_code}):")
        print(f"  handled_by: {decision.handled_by}")
        print(f"  action:     {decision.action}")
        print(f"  category:   {decision.category}")
        print(f"  reasoning:  {decision.reasoning}")
        print()

        if decision.handled_by == "rule_engine":
            handled_by_rule_engine += 1
        else:
            handled_by_llm += 1

    total = len(test_batch)
    print("--- Summary ---")
    print(f"Handled by rule engine: {handled_by_rule_engine}/{total} "
          f"({handled_by_rule_engine/total*100:.0f}%) - fast, free, explainable")
    print(f"Escalated to LLM:       {handled_by_llm}/{total} "
          f"({handled_by_llm/total*100:.0f}%) - genuinely ambiguous cases only")
