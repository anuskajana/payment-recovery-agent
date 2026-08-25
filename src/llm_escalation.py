"""
LLM Escalation - Layer 2 of the recovery system.

This ONLY runs when the Rule Engine (Layer 1) returns matched=False -
meaning there's no confident, research-backed rule for this failure code.

Design principle: this is the expensive, slower path. It should be rare.
If you find yourself routing most payments here, that's a sign the rule
table needs more research, not that the LLM layer needs to get "smarter."

Two modes are supported:
- MOCK_MODE=True  -> no API key needed, returns a clearly-labeled fake
                      decision so the rest of the pipeline can be tested
- MOCK_MODE=False -> calls the real Anthropic API (needs ANTHROPIC_API_KEY
                      in .env)
"""

import os
import json
from dataclasses import dataclass, asdict

from dotenv import load_dotenv

load_dotenv()

MOCK_MODE = os.getenv("ANTHROPIC_API_KEY") is None


@dataclass
class LLMDecision:
    action: str
    category: str          # will be "D" for every LLM-escalated case
    reasoning: str
    confidence: str         # "high" / "medium" / "low" - LLM self-reports this
    is_mock: bool = False


SYSTEM_PROMPT = """You are a payment recovery reasoning assistant for an Indian
fintech platform (Razorpay). You are only called when a deterministic rule engine
could NOT confidently classify a payment failure - meaning this is a genuinely
ambiguous or unseen case.

Given details about a failed payment, decide:
1. What action should be taken? (e.g. retry_later, notify_customer, escalate_to_support, no_action)
2. Brief reasoning (2-3 sentences max)
3. Your confidence in this decision: high / medium / low

Respond ONLY in this exact JSON format, nothing else:
{"action": "...", "reasoning": "...", "confidence": "..."}

Be conservative: if you are not confident, say so honestly rather than guessing
with false certainty. A payment recovery system that is honestly uncertain is
safer than one that is confidently wrong.
"""


def _build_user_prompt(payment_context: dict) -> str:
    return f"""Failed payment details:
- Error code: {payment_context.get('error_code')}
- Payment method: {payment_context.get('payment_method')}
- Amount: Rs. {payment_context.get('amount')}
- Number of times this payment has already failed: {payment_context.get('failure_count', 1)}
- Rule engine result: {payment_context.get('rule_engine_note', 'No matching rule found')}

Decide the recovery action."""


def _mock_decision(payment_context: dict) -> LLMDecision:
    """
    Returns a clearly-labeled fake decision so the pipeline can be tested
    end-to-end without a live API key. This is NOT a real reasoning engine -
    it's a placeholder that mimics the shape of a real response.
    """
    return LLMDecision(
        action="escalate_to_support_MOCK",
        category="D",
        reasoning=(
            "[MOCK MODE - no ANTHROPIC_API_KEY found in .env] "
            f"Would have asked the LLM to reason about error code "
            f"'{payment_context.get('error_code')}'. Add a real API key "
            f"to .env to get an actual decision here."
        ),
        confidence="n/a (mock)",
        is_mock=True,
    )


def _real_decision(payment_context: dict) -> LLMDecision:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env automatically

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(payment_context)}],
    )

    raw_text = response.content[0].text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Graceful fallback if the LLM doesn't return clean JSON -
        # never let the pipeline crash because of a formatting hiccup.
        return LLMDecision(
            action="escalate_to_support",
            category="D",
            reasoning=f"LLM response could not be parsed cleanly. Raw response: {raw_text[:200]}",
            confidence="low",
        )

    return LLMDecision(
        action=parsed.get("action", "escalate_to_support"),
        category="D",
        reasoning=parsed.get("reasoning", ""),
        confidence=parsed.get("confidence", "unknown"),
    )


def evaluate(payment_context: dict) -> LLMDecision:
    """
    Main entry point. payment_context should look like:
    {
        "error_code": "vpa_resolution_failed",
        "payment_method": "UPI",
        "amount": 499,
        "failure_count": 1,
        "rule_engine_note": "No matching rule found"
    }
    """
    if MOCK_MODE:
        return _mock_decision(payment_context)
    return _real_decision(payment_context)


if __name__ == "__main__":
    # Manual sanity check - run this file directly to see it work
    test_case = {
        "error_code": "vpa_resolution_failed",
        "payment_method": "UPI",
        "amount": 1499,
        "failure_count": 1,
        "rule_engine_note": "No matching rule found - Razorpay docs recommend a support ticket",
    }

    print(f"MOCK_MODE is: {MOCK_MODE}")
    result = evaluate(test_case)
    print("\nDecision:")
    for k, v in asdict(result).items():
        print(f"  {k}: {v}")
