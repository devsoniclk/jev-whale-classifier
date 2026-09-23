from __future__ import annotations

"""Classify whale transactions using Jev and generate alerts."""

import json
from datetime import datetime, timezone

from jev_client import classify_whale_tx
from logger import JSONLLogger


SEVERITY_COLORS = {
    "negligible": "\033[90m",   # gray
    "minor": "\033[92m",        # green
    "moderate": "\033[93m",     # yellow
    "major": "\033[91m",        # red
    "crash-risk": "\033[95m",   # magenta
    "unknown": "\033[0m",       # default
}
RESET = "\033[0m"
BOLD = "\033[1m"


def format_alert(tx: dict, classification: dict) -> str:
    """Format a whale alert for terminal display."""
    severity = classification.get("impact_severity", "unknown")
    color = SEVERITY_COLORS.get(severity, RESET)
    intent = classification.get("intent", "unknown")
    bearish = classification.get("bearish_signal", False)
    bearish_str = "🔴 BEARISH" if bearish else "🟢 Neutral"

    exchange_info = ""
    if tx.get("exchange_from"):
        exchange_info += f" (from {tx['exchange_from']})"
    if tx.get("exchange_to"):
        exchange_info += f" (to {tx['exchange_to']})"

    lines = [
        f"{color}{BOLD}{'='*60}{RESET}",
        f"{color}{BOLD}🐋 WHALE ALERT: {tx['asset']}{RESET}",
        f"  Amount:    {BOLD}{tx['amount']} {tx['asset']}{RESET} (${tx['usd_value']:,.2f})",
        f"  From:      {tx['from_anonymized']}{exchange_info}",
        f"  To:        {tx['to_anonymized']}",
        f"  Intent:    {BOLD}{intent.upper()}{RESET}",
        f"  Signal:    {bearish_str}",
        f"  Severity:  {color}{BOLD}{severity.upper()}{RESET}",
        f"  Tx:        {tx['tx_hash'][:20]}...",
    ]
    if classification.get("reasoning"):
        lines.append(f"  Reasoning: {classification['reasoning'][:100]}")
    lines.append(f"{color}{BOLD}{'='*60}{RESET}")
    return "\n".join(lines)


def classify_and_alert(whale_txs: list[dict], logger: JSONLLogger | None = None) -> list[dict]:
    """Classify a list of whale transactions and print alerts.

    Returns list of {tx, classification} dicts.
    """
    if logger is None:
        logger = JSONLLogger()

    results = []
    for tx in whale_txs:
        # Log raw whale tx
        logger.log_whale_tx(tx)

        # Classify with Jev
        print(f"  Classifying {tx['asset']} tx {tx['tx_hash'][:16]}... ({tx['amount']} {tx['asset']})")
        classification = classify_whale_tx(tx)

        # Log classification
        logger.log_classification(tx["tx_hash"], classification)

        # Print alert
        alert = format_alert(tx, classification)
        print(alert)

        results.append({"tx": tx, "classification": classification})

    return results
