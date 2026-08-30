# Payment Recovery Agent

Built for the Razorpay Buildathon — Track 3: Payment Degradation → Root Cause → Recovery.

## What this actually does

When a payment fails, most systems do one of two things: retry blindly a fixed
number of hours later, or throw the whole problem at an LLM and hope for a good
answer. Both are kind of lazy. A blind retry doesn't ask *why* something failed,
so it retries "card expired" the same way it retries "insufficient funds" — even
though retrying an expired card will never, ever work. And routing everything
through an LLM means paying (in time and cost) for reasoning you often don't
actually need.

This project tries to do the more obvious thing instead: figure out why a
payment failed, and only then decide what to do about it.

## How it's structured

1. **Research first.** I went through Razorpay's own docs and pulled 17 real
   failure codes across UPI, cards, and netbanking — see
   [`docs/failure_taxonomy.md`](docs/failure_taxonomy.md). For each one I asked
   two questions: *whose fault is this, and is it fixable by just waiting, or
   does something actually need to change?* That gave me four buckets (A/B/C/D),
   and from there, a concrete recommended action for each code.

2. **Rule engine first, LLM second.** [`src/rule_engine.py`](src/rule_engine.py)
   handles any failure code that matches the researched table — instantly, for
   free, no API call. Only genuinely unmapped or ambiguous codes fall through
   to [`src/llm_escalation.py`](src/llm_escalation.py), which asks Gemini to
   reason it out and self-report a confidence level, rather than guessing
   confidently. On a realistic batch, this split lands around 95-97% rule
   engine, 3-5% LLM — which is the point, not a limitation. If the LLM were
   handling most of the traffic, that would mean the rule research wasn't done
   properly.

3. **Everything gets logged.** [`src/audit_trail.py`](src/audit_trail.py) writes
   every decision to an append-only table — nothing gets edited or deleted
   after the fact, so any decision can be traced back to its reasoning.

4. **Proving it's actually better.** [`src/comparison.py`](src/comparison.py)
   runs the same batch of failures through this system and against a
   deliberately dumb baseline (retry everything once, 24 hours later,
   regardless of cause). On a batch of ~80-190 simulated payments, the smart
   system recovers roughly 50-60% more revenue and avoids most of the wasted
   retry attempts the naive approach would have made. These numbers are
   **estimates** based on researched success-rate assumptions per failure
   category — I don't have access to real bank-side outcome data, and I say
   so explicitly in the dashboard rather than presenting a made-up number as fact.

5. **A real Razorpay API call, not just simulated data.**
   [`src/razorpay_integration.py`](src/razorpay_integration.py) creates and
   fetches back an actual test-mode Order through Razorpay's API — this is
   separate from the simulator, which generates the batch-scale synthetic
   failures used to test the rule engine and LLM layers.

6. **A dashboard to see it all.** `app.py` (Streamlit) shows the headline
   recovery numbers, the rule-vs-LLM split, a click-through audit trail, and
   the baseline comparison chart.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

You'll need a `.env` file (see `.env.example`) with:
- `GEMINI_API_KEY` — for the LLM escalation layer
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — for the Razorpay integration

Without these, the LLM layer automatically falls back to a clearly-labeled
mock mode, so the rest of the pipeline still runs and can be tested end to end.

## A bug worth mentioning, because it was a good one

Partway through, the simulator and the rule engine disagreed on how a few
failure codes were spelled (`otp_3ds_authentication_failed` vs.
`otp_3ds_failed`, for instance). Nothing crashed — it just silently sent over
half the batch to the LLM instead of the ~12% the research predicted. I only
caught it because I compared the actual pipeline output against what the
taxonomy doc predicted, rather than trusting that four hand-picked test cases
working meant everything worked. Once the naming was aligned, the ratio
dropped back to the expected ~95/5 split. It's logged in
[`logs/decisions.md`](logs/decisions.md) along with the rest of the reasoning
behind each design choice made along the way.

## What I'd do with more time

- Wire the recovery actions into actual retry calls against Razorpay's API,
  rather than just deciding what the action *should* be
- Replace the fixed success-rate assumptions in the baseline comparison with
  something that updates based on real outcomes over time
- Add the UPI-mandate-specific compliance guardrails (retry caps, pre-debit
  notification timing) I initially scoped in and then cut for time
