# Payment Failure Taxonomy & Recovery Rules

Research source: Razorpay official docs (razorpay.com/docs/errors/payments/upi/,
razorpay.com/docs/errors/payments/cards/, razorpay.com/docs/errors/payments/list/)
+ Razorpay engineering blog on UPI failures.

## The classification logic used

For every failure code, two questions decide the action:
1. **Whose fault is it?** (Customer / Bank / Unclear)
2. **Is it fixable just by waiting, or does something need to actually change?**

This produces 4 categories:
- **A — Customer's fault, temporary:** retry after appropriate delay
- **B — Customer's fault, NOT temporary:** don't retry blindly, notify customer to fix something
- **C — Bank/network fault, temporary:** retry later, don't blame/message customer
- **D — Ambiguous / no confident rule:** escalate to LLM

## Rule Table

| # | Error Code | Payment Method | Whose Fault | Fixable by Waiting? | Timing | Action | Category |
|---|---|---|---|---|---|---|---|
| 1 | insufficient_funds | UPI/Card | Customer | Yes | Wait 2-3 days | Retry once after delay | A |
| 2 | customer_bank_account_mismatch | UPI | Customer | No | — | Notify: use registered account | B |
| 3 | bank_technical_error | Bank | Bank | Yes | Wait few hours | Retry later, no customer blame | C |
| 4 | partner_bank_downtime | Bank | Bank | Yes | Wait few hours | Retry later, no customer blame | C |
| 5 | upi_provider_downtime | UPI | Bank | Yes | Wait few hours | Retry later, no customer blame | C |
| 6 | payment_collect_request_expired (U69) | UPI | Customer | Yes | Almost immediate | Resend collect request | A |
| 7 | payment_cancelled_by_customer | UPI/Card | Customer | Yes | Immediate | Prompt to reattempt | A |
| 8 | invalid_vpa_not_registered | UPI | Customer | No | — | Notify: complete UPI registration | B |
| 9 | otp_3ds_authentication_failed | Card | Customer | Yes | Immediate (same session) | Retry OTP right away | A |
| 10 | upi_pin_attempts_exceeded | UPI | Customer | Yes | Long wait (~24h, bank-enforced) | Wait out lock, then retry | A |
| 11 | card_expired | Card | Customer | No | — | Notify: use different card | B |
| 12 | card_not_enabled_online | Card | Customer | No | — | Notify: enable card via bank/app | B |
| 13 | bank_declined_fraud_suspicion | Card/UPI | Bank | No | — | Notify customer to contact bank; do not blind-retry | B |
| 14 | daily_upi_limit_exceeded | UPI | Customer | No | — | Notify: use different account or lower amount | B |
| 15 | bank_not_enabled_on_upi | UPI | Bank/Customer | No | — | Notify: try a different bank account | B |
| 16 | declined_no_reason_given | Card/UPI | Unclear | Unclear | — | Escalate to LLM | D |
| 17 | repeated_failure_different_reasons | Any | Unclear | Unclear | — | Escalate to LLM | D |

## Why rows 16-17 are genuinely the LLM escalation cases

Razorpay's own docs admit that for "declined, no reason given" cases, they don't have
visibility into the bank's actual reasoning — meaning even Razorpay doesn't have a
confident deterministic rule here. Same logic applies to a payment that's failed multiple
times with *different* reasons each time — no single row in this table fits, so it needs
actual reasoning rather than a lookup. This makes both cases honest escalation triggers,
not artificially inserted ones.

## Summary (this is your "AI judgment" evidence)

- Category A (retry with timing logic): 5 codes — rows 1, 6, 7, 9, 10
- Category B (notify customer, don't blind-retry): 7 codes — rows 2, 8, 11, 12, 13, 14, 15
- Category C (retry later, bank's fault): 3 codes — rows 3, 4, 5
- Category D (escalate to LLM): 2 codes — rows 16, 17

**15 out of 17 known codes (~88%) are handled by fast, free, deterministic rules.**
Only genuinely ambiguous cases go to the LLM. This ratio — and the *reasoning* behind
each row — is the concrete evidence for "AI judgment: the right tool in the right place,
and where you chose not to use one."

## Sources
- https://razorpay.com/docs/errors/payments/upi/
- https://razorpay.com/docs/errors/payments/cards/
- https://razorpay.com/docs/errors/payments/list/
- https://razorpay.com/blog/tackling-upi-payment-failures-with-razorpay/
