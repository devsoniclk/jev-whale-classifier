#!/usr/bin/env python3
from __future__ import annotations

"""Jev Whale Classifier CLI.

Usage:
    python run.py scan          # One-time scan of ETH + BTC whale txs
    python run.py scan --eth    # Scan ETH only
    python run.py scan --btc    # Scan BTC only
    python run.py classify      # Scan and classify with Jev
    python run.py monitor       # Continuous monitoring loop
    python run.py stats         # Show classification statistics
"""

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from classifier import classify_and_alert
from logger import JSONLLogger
from whale_scanner import scan_all, scan_eth_whales, scan_btc_whales


def cmd_scan(args):
    """Scan for whale transactions without Jev classification."""
    logger = JSONLLogger()

    if args.eth:
        txs = scan_eth_whales()
    elif args.btc:
        txs = scan_btc_whales()
    else:
        txs = scan_all()

    if not txs:
        print("No whale transactions found in this scan.")
        return

    print(f"\nFound {len(txs)} whale transaction(s):\n")
    for tx in txs:
        logger.log_whale_tx(tx)
        exchange_info = ""
        if tx.get("exchange_from"):
            exchange_info += f" [from {tx['exchange_from']}]"
        if tx.get("exchange_to"):
            exchange_info += f" [to {tx['exchange_to']}]"
        print(f"  🐋 {tx['asset']} | {tx['amount']} {tx['asset']} (${tx['usd_value']:,.2f})")
        print(f"     {tx['from_anonymized']} → {tx['to_anonymized']}{exchange_info}")
        print(f"     Tx: {tx['tx_hash'][:20]}...")
        print()


def cmd_classify(args):
    """Scan and classify whale transactions with Jev."""
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY not set. Add it to .env file.")
        print("Get a key at https://openrouter.ai/keys")
        sys.exit(1)

    logger = JSONLLogger()

    if args.eth:
        txs = scan_eth_whales()
    elif args.btc:
        txs = scan_btc_whales()
    else:
        txs = scan_all()

    if not txs:
        print("No whale transactions found in this scan.")
        return

    print(f"\nClassifying {len(txs)} whale transaction(s) with Jev...\n")
    results = classify_and_alert(txs, logger)
    print(f"\nDone. Classified {len(results)} transactions.")


def cmd_monitor(args):
    """Continuously monitor for whale transactions."""
    import yaml

    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY not set. Add it to .env file.")
        sys.exit(1)

    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    interval = cfg["scanner"]["poll_interval_seconds"]
    logger = JSONLLogger()
    seen_hashes = set()

    # Load already-seen hashes
    for rec in logger.read_whale_txs(limit=10000):
        seen_hashes.add(rec.get("tx_hash", ""))

    print(f"🐋 Whale Monitor started (polling every {interval}s)")
    print(f"   Tracking ETH (>{cfg['whale']['eth']['min_value_eth']} ETH) and BTC (>{cfg['whale']['btc']['min_value_btc']} BTC)")
    print(f"   Press Ctrl+C to stop\n")

    scan_count = 0
    while True:
        scan_count += 1
        print(f"--- Scan #{scan_count} ---")
        try:
            txs = scan_all(
                min_eth=cfg["whale"]["eth"]["min_value_eth"],
                min_btc=cfg["whale"]["btc"]["min_value_btc"],
            )
            new_txs = [tx for tx in txs if tx["tx_hash"] not in seen_hashes]

            if new_txs:
                print(f"  {len(new_txs)} new whale tx(s) detected!")
                results = classify_and_alert(new_txs, logger)
                for tx in new_txs:
                    seen_hashes.add(tx["tx_hash"])
            else:
                print(f"  No new whale transactions.")
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break
        except Exception as e:
            print(f"  Error during scan: {e}")

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break


def cmd_stats(args):
    """Show classification statistics."""
    logger = JSONLLogger()
    stats = logger.stats()

    print(f"\n🐋 Jev Whale Classifier Statistics")
    print(f"{'='*40}")
    print(f"  Total whale txs logged:       {stats['total_whale_txs']}")
    print(f"  Total classifications:         {stats['total_classifications']}")
    print(f"  Bearish signals:               {stats['bearish_signals']}")

    if stats["intent_breakdown"]:
        print(f"\n  Intent Breakdown:")
        for intent, count in sorted(stats["intent_breakdown"].items(), key=lambda x: -x[1]):
            print(f"    {intent:20s} {count}")

    if stats["severity_breakdown"]:
        print(f"\n  Severity Breakdown:")
        for sev, count in sorted(stats["severity_breakdown"].items(), key=lambda x: -x[1]):
            print(f"    {sev:20s} {count}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Jev Whale Classifier - Smart money movement analysis"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # scan
    scan_p = subparsers.add_parser("scan", help="Scan for whale transactions")
    scan_p.add_argument("--eth", action="store_true", help="Scan ETH only")
    scan_p.add_argument("--btc", action="store_true", help="Scan BTC only")

    # classify
    cls_p = subparsers.add_parser("classify", help="Scan and classify with Jev")
    cls_p.add_argument("--eth", action="store_true", help="Scan ETH only")
    cls_p.add_argument("--btc", action="store_true", help="Scan BTC only")

    # monitor
    subparsers.add_parser("monitor", help="Continuous monitoring loop")

    # stats
    subparsers.add_parser("stats", help="Show classification statistics")

    args = parser.parse_args()

    commands = {
        "scan": cmd_scan,
        "classify": cmd_classify,
        "monitor": cmd_monitor,
        "stats": cmd_stats,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
