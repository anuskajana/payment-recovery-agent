"""
Audit Trail - append-only log of every recovery decision made.

Design principle: never overwrite or delete past entries. If you need to
correct something, add a new row noting the correction - don't edit history.
This is what makes the system's decisions checkable after the fact, which is
the whole point of an audit trail (see THE BAR in the buildathon brief:
"show the audit trail").
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = "data/payments.db"


def _ensure_table():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT NOT NULL,
            error_code TEXT NOT NULL,
            handled_by TEXT NOT NULL,      -- 'rule_engine' or 'llm_escalation'
            action TEXT NOT NULL,
            category TEXT NOT NULL,        -- A / B / C / D
            reasoning TEXT NOT NULL,
            logged_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def log_decision(decision) -> None:
    """
    Writes one FinalDecision (from orchestrator.py) to the audit trail.
    This is an INSERT only - the table is never updated or cleared by
    normal operation.
    """
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_trail
        (payment_id, error_code, handled_by, action, category, reasoning, logged_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        decision.payment_id,
        decision.error_code,
        decision.handled_by,
        decision.action,
        decision.category,
        decision.reasoning,
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()


def get_all_entries():
    """Returns every audit trail row, oldest first - for the dashboard later."""
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_trail ORDER BY id ASC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_entry_for_payment(payment_id: str):
    """Returns the audit trail row(s) for one specific payment - used for
    the click-through 'why did it decide this' view in the dashboard."""
    _ensure_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_trail WHERE payment_id = ? ORDER BY id ASC", (payment_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    # Manual sanity check - run the full pipeline on a small batch and
    # confirm every decision actually gets written to the audit trail.
    from src import simulator, orchestrator

    batch = simulator.generate_batch(n=5, seed=1)
    for payment in batch:
        decision = orchestrator.process_failed_payment(
            payment_id=payment["payment_id"],
            error_code=payment["error_code"],
            amount=payment["amount"],
            payment_method=payment["payment_method"],
            failure_count=payment["failure_count"],
        )
        log_decision(decision)

    print("Audit trail contents:")
    for entry in get_all_entries():
        print(f"  [{entry['id']}] {entry['payment_id']} | {entry['error_code']} | "
              f"{entry['handled_by']} -> {entry['action']}")
