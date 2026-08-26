"""
Simulator - generates a realistic batch of failed payments for testing.

Design decision: failures are NOT equally likely in real life. This simulator
weights common failures (insufficient funds, OTP timeout) much higher than
rare ones (fraud suspicion, unknown codes) - based on the taxonomy research
in docs/failure_taxonomy.md.

This matters for later steps: a baseline-vs-smart-system comparison only
means something if tested on a realistic, lumpy distribution - not a
perfectly even one nobody would see in production.
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from collections import Counter

# (error_code, payment_method, relative_weight)
# Higher weight = more common in real life. Weights are relative, not percentages.
FAILURE_DISTRIBUTION = [
    # NOTE: these codes must exactly match the keys in rule_engine.RULE_TABLE.
    # Mismatched names here would silently send everything to the LLM layer -
    # this bit us once already (see logs/decisions.md), keeping the note as
    # a reminder for future edits.
    ("insufficient_funds", "UPI", 22),
    ("otp_3ds_failed", "Card", 18),
    ("payment_cancelled", "UPI", 15),
    ("payment_collect_request_expired", "UPI", 10),
    ("customer_bank_account_mismatch", "UPI", 7),
    ("bank_technical_error", "UPI", 6),
    ("card_expired", "Card", 6),
    ("upi_pin_attempts_exceeded", "UPI", 5),
    ("payment_declined", "Card", 4),
    ("partner_bank_downtime", "UPI", 3),
    ("invalid_vpa", "UPI", 3),
    ("partner_bank_technical_issues", "UPI", 2),
    ("vpa_resolution_failed", "UPI", 2),            # ambiguous -> LLM (on purpose)
    ("session_timeout_unmapped", "UPI", 2),          # ambiguous -> LLM (on purpose)
    ("some_never_seen_code", "Card", 1),             # ambiguous -> LLM (on purpose)
]

DB_PATH = "data/payments.db"


def _weighted_choice():
    codes = [row[0] for row in FAILURE_DISTRIBUTION]
    methods = [row[1] for row in FAILURE_DISTRIBUTION]
    weights = [row[2] for row in FAILURE_DISTRIBUTION]
    idx = random.choices(range(len(codes)), weights=weights, k=1)[0]
    return codes[idx], methods[idx]


def _random_amount(payment_method: str) -> float:
    # UPI skews smaller (everyday purchases), card skews larger (bigger tickets)
    if payment_method == "UPI":
        return round(random.uniform(50, 3000), 2)
    return round(random.uniform(500, 15000), 2)


def _random_timestamp(days_back: int = 14) -> str:
    now = datetime.now(timezone.utc)
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return (now - delta).isoformat()


def generate_batch(n=60, seed=42):
    """
    Generates n realistic failed payment records.
    seed=42 by default for reproducible test batches - change or set to None
    for a fresh random batch each time.
    """
    if seed is not None:
        random.seed(seed)

    batch = []
    for i in range(1, n + 1):
        error_code, method = _weighted_choice()
        batch.append({
            "payment_id": f"pay_{i:04d}",
            "error_code": error_code,
            "payment_method": method,
            "amount": _random_amount(method),
            "failure_count": random.choices([1, 2, 3], weights=[70, 22, 8], k=1)[0],
            "created_at": _random_timestamp(),
        })
    return batch


def save_batch_to_db(batch):
    os.makedirs("data", exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS failed_payments (
            payment_id TEXT PRIMARY KEY,
            error_code TEXT,
            payment_method TEXT,
            amount REAL,
            failure_count INTEGER,
            created_at TEXT
        )
    """)
    cur.executemany("""
        INSERT OR REPLACE INTO failed_payments
        (payment_id, error_code, payment_method, amount, failure_count, created_at)
        VALUES (:payment_id, :error_code, :payment_method, :amount, :failure_count, :created_at)
    """, batch)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    batch = generate_batch(n=60)
    save_batch_to_db(batch)

    print(f"Generated {len(batch)} failed payments -> saved to {DB_PATH}\n")

    counts = Counter(p["error_code"] for p in batch)
    print("Distribution in this batch:")
    for code, count in counts.most_common():
        print(f"  {code:40s} {count:3d}  ({count/len(batch)*100:.1f}%)")
