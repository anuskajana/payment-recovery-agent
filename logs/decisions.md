# Decision Log

(Personal notes — why I made each choice. This becomes the source for the README/pitch.)

## 2026-08-24 — Track & direction

Chose Track 3, Direction 2: Payment Degradation → Root Cause → Recovery.
Reason: revenue loss from failed payments is a real, measurable problem, and
"root cause before recovery" is a genuine engineering insight most naive
retry-everything systems miss.

## 2026-08-24 — Rule-first, LLM-fallback architecture

Decided the system should try a deterministic rule table FIRST, and only call
an LLM for genuinely ambiguous failure codes. Reasoning: ~88% of real Razorpay
failure codes have an obvious, well-documented cause and fix (see
docs/failure_taxonomy.md) — using an LLM for these would be slower, costlier,
and less explainable than a plain lookup table. The LLM should be reserved for
the ~12% of cases where even Razorpay's own docs don't give a confident answer.
This directly answers the "AI judgment" criterion: knowing where NOT to use AI.

## 2026-08-24 — Classification method for the rule table

Used a simple 2-question test for every failure code: "Whose fault is it, and
is it fixable by waiting or does something need to change?" This produced 4
categories (A: customer/temporary, B: customer/needs a fix, C: bank/temporary,
D: ambiguous/escalate). Corrected one early mistake: initially mislabeled
"wrong bank account used" as temporary, but the fix required customer action,
not waiting — reclassified to Category B.

## 2026-08-26 — Bug caught: simulator/rule engine naming mismatch

Built simulator.py with error code names that didn't exactly match the keys
in rule_engine.RULE_TABLE (e.g. simulator said "otp_3ds_authentication_failed",
rule engine expected "otp_3ds_failed"). Result: 53% of a batch silently fell
through to LLM escalation instead of the expected ~12%. Caught it by comparing
actual pipeline output against the taxonomy doc's predicted ratio - a real
example of why testing at batch scale (not just 4 hand-picked examples)
matters. Fixed by aligning simulator codes to the rule engine's existing keys.
After fix: 95% rule engine / 5% LLM on a 60-payment batch, consistent with
the taxonomy research.
