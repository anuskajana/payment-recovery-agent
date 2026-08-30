"""
Razorpay Integration - proves this project actually talks to Razorpay's
real test-mode APIs, not just simulated data.

This is deliberately separate from simulator.py. The simulator generates
realistic failure scenarios for testing the rule engine / LLM escalation
at scale (50+ records, as the buildathon brief asks for). This module does
one real thing: creates an actual test-mode Order via Razorpay's API, so
there's a genuine, verifiable integration point with the platform - not
just an isolated local simulation.
"""

import os
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")


def _get_client():
    import razorpay
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_test_order(amount_rupees: float, receipt_id: str) -> dict:
    """
    Creates a real test-mode Order on Razorpay. Amount must be in paise
    (Razorpay's smallest currency unit), so we convert from rupees here.

    Returns the raw Order object from Razorpay's API - this is real data
    coming back from their servers, not something we generated locally.
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise RuntimeError(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not found in .env. "
            "Add your test-mode keys before calling this."
        )

    client = _get_client()
    order = client.order.create({
        "amount": int(amount_rupees * 100),  # rupees -> paise
        "currency": "INR",
        "receipt": receipt_id,
        "notes": {
            "project": "payment-recovery-agent",
            "purpose": "Razorpay Buildathon Track 3 - integration proof",
        },
    })
    return order


def fetch_order(order_id: str) -> dict:
    """Fetches back an order by ID - a second real API call, useful for
    demoing that data round-trips correctly with Razorpay's servers."""
    client = _get_client()
    return client.order.fetch(order_id)


if __name__ == "__main__":
    # Manual sanity check - creates one real test order and fetches it back
    print("Creating a real test-mode order on Razorpay...")
    order = create_test_order(amount_rupees=499, receipt_id="demo_receipt_001")

    print("\nOrder created successfully:")
    print(f"  id:       {order['id']}")
    print(f"  amount:   {order['amount']} paise (Rs. {order['amount']/100})")
    print(f"  currency: {order['currency']}")
    print(f"  status:   {order['status']}")

    print("\nFetching the same order back to confirm round-trip works...")
    fetched = fetch_order(order["id"])
    print(
        f"  Confirmed - fetched order id matches: {fetched['id'] == order['id']}")
