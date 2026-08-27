"""
Baseline - the "naive" system most companies actually run today.

Logic: retry EVERY failed payment once, 24 hours later, no matter what
caused the failure. No diagnosis, no differentiation between "customer
needs to change something" and "just wait and it'll work."

This exists purely for comparison. It is deliberately simple - the whole
point is to measure how much the smart system (rule engine + LLM escalation)
improves on doing nothing clever at all.
"""

from dataclasses import dataclass


@dataclass
class BaselineDecision:
    payment_id: str
    error_code: str
    action: str = "retry_after_24h"
    reasoning: str = "Naive baseline: retry every failure once, 24h later, regardless of cause."


def process_failed_payment_naive(payment_id: str, error_code: str, **kwargs) -> BaselineDecision:
    """Same call signature as orchestrator.process_failed_payment, minus the
    intelligence - accepts and ignores amount/payment_method/failure_count
    so it's a drop-in comparison against the smart system."""
    return BaselineDecision(payment_id=payment_id, error_code=error_code)


if __name__ == "__main__":
    result = process_failed_payment_naive("pay_0001", "insufficient_funds", amount=499)
    print(result)
