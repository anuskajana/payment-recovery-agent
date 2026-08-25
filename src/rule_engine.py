"""
Rule Engine - Layer 1 of the recovery system.

This handles all failure codes where we have a CONFIDENT, research-backed
rule (see docs/failure_taxonomy.md for the reasoning behind each entry).

Design principle: fast, free, explainable. No LLM call happens here.
If a failure code isn't in this table, the caller should escalate to the
LLM layer instead of guessing.
"""

from dataclasses import dataclass


@dataclass
class RuleDecision:
    matched: bool
    action: str          # what to do
    category: str        # A / B / C / D (see taxonomy doc)
    reasoning: str        # why - shown in the audit trail
    retry_delay_hours: float | None = None  # None = no retry recommended


# The rule table itself - directly encodes docs/failure_taxonomy.md
# Keys are Razorpay's real error/reason codes.
RULE_TABLE: dict[str, RuleDecision] = {

    "insufficient_funds": RuleDecision(
        matched=True,
        action="retry_after_delay",
        category="A",
        reasoning="Customer's fault, but temporary - balance may be topped up. "
                   "Wait before retrying so we don't annoy the customer.",
        retry_delay_hours=48,
    ),

    "customer_bank_account_mismatch": RuleDecision(
        matched=True,
        action="notify_customer_use_registered_account",
        category="B",
        reasoning="Customer's fault, NOT temporary - retrying the same way "
                   "will never work. They must use the account they registered.",
        retry_delay_hours=None,
    ),

    "bank_technical_error": RuleDecision(
        matched=True,
        action="retry_later_no_blame",
        category="C",
        reasoning="Bank/UPI provider's fault, temporary. Not the customer's "
                   "problem - don't message them accusingly.",
        retry_delay_hours=3,
    ),

    "partner_bank_downtime": RuleDecision(
        matched=True,
        action="retry_later_no_blame",
        category="C",
        reasoning="Partner bank downtime, outside our control but usually "
                   "recovers within hours.",
        retry_delay_hours=3,
    ),

    "partner_bank_technical_issues": RuleDecision(
        matched=True,
        action="retry_later_no_blame",
        category="C",
        reasoning="Partner bank technical issue, Razorpay's own docs "
                   "recommend retrying after some time.",
        retry_delay_hours=3,
    ),

    "payment_collect_request_expired": RuleDecision(
        matched=True,
        action="resend_collect_request",
        category="A",
        reasoning="Customer simply didn't act within the ~10 min window. "
                   "No real block - just resend, no need to wait.",
        retry_delay_hours=0,
    ),

    "payment_cancelled": RuleDecision(
        matched=True,
        action="ask_retry_immediate",
        category="A",
        reasoning="Customer backed out, possibly by accident. Safe to "
                   "prompt an immediate retry.",
        retry_delay_hours=0,
    ),

    "payment_declined": RuleDecision(
        matched=True,
        action="ask_retry_once",
        category="A",
        reasoning="Funds couldn't be debited for an unspecified reason. "
                   "Razorpay's own guidance is to just retry.",
        retry_delay_hours=0,
    ),

    "invalid_vpa": RuleDecision(
        matched=True,
        action="notify_customer_complete_registration",
        category="B",
        reasoning="Customer's UPI registration isn't complete - retrying "
                   "payment won't fix an incomplete registration.",
        retry_delay_hours=None,
    ),

    "otp_3ds_failed": RuleDecision(
        matched=True,
        action="retry_otp_immediate",
        category="A",
        reasoning="Simple entry mistake, fixable in the very same session.",
        retry_delay_hours=0,
    ),

    "upi_pin_attempts_exceeded": RuleDecision(
        matched=True,
        action="wait_out_lock_then_retry",
        category="A",
        reasoning="Bank enforces a real lockout period (~24h). Retrying "
                   "before that expires is pointless and against bank rules.",
        retry_delay_hours=24,
    ),

    "card_expired": RuleDecision(
        matched=True,
        action="notify_customer_new_card",
        category="B",
        reasoning="Card expiry doesn't fix itself. Customer must provide "
                   "a different payment method.",
        retry_delay_hours=None,
    ),

    # vpa_resolution_failed is DELIBERATELY NOT in this table.
    # Razorpay's own docs recommend raising a support ticket for this -
    # meaning even Razorpay doesn't have a confident deterministic answer.
    # This is our genuine LLM-escalation case (Category D).
}


def evaluate(error_code: str) -> RuleDecision:
    """
    Look up a failure code in the rule table.

    Returns a RuleDecision with matched=False if no confident rule exists -
    the caller should then escalate to the LLM layer (see llm_escalation.py).
    """
    decision = RULE_TABLE.get(error_code)
    if decision is not None:
        return decision

    return RuleDecision(
        matched=False,
        action="escalate_to_llm",
        category="D",
        reasoning=f"No confident rule exists for '{error_code}'. "
                   f"Escalating to LLM for reasoning.",
        retry_delay_hours=None,
    )


if __name__ == "__main__":
    # Quick manual sanity check - run this file directly to see it work
    test_codes = [
        "insufficient_funds",
        "card_expired",
        "vpa_resolution_failed",   # should escalate
        "some_totally_unknown_code",  # should escalate
    ]
    for code in test_codes:
        result = evaluate(code)
        print(f"\n{code}:")
        print(f"  matched:  {result.matched}")
        print(f"  action:   {result.action}")
        print(f"  category: {result.category}")
        print(f"  reason:   {result.reasoning}")
