from __future__ import annotations

"""JSONL logger for whale transactions and Jev classifications."""

import json
import os
from datetime import datetime, timezone


class JSONLLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def _write(self, filename: str, record: dict):
        record["logged_at"] = datetime.now(timezone.utc).isoformat()
        path = os.path.join(self.log_dir, filename)
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def log_whale_tx(self, tx: dict):
        self._write("whale_transactions.jsonl", tx)

    def log_classification(self, tx_hash: str, classification: dict):
        record = {"tx_hash": tx_hash, "classification": classification}
        self._write("classifications.jsonl", record)

    def read_whale_txs(self, limit: int = 100) -> list[dict]:
        return self._read("whale_transactions.jsonl", limit)

    def read_classifications(self, limit: int = 100) -> list[dict]:
        return self._read("classifications.jsonl", limit)

    def _read(self, filename: str, limit: int) -> list[dict]:
        path = os.path.join(self.log_dir, filename)
        if not os.path.exists(path):
            return []
        records = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records[-limit:]

    def stats(self) -> dict:
        whale_txs = self.read_whale_txs(limit=10000)
        classifications = self.read_classifications(limit=10000)
        intents = {}
        severities = {}
        bearish_count = 0
        for c in classifications:
            cl = c.get("classification", {})
            intent = cl.get("intent", "unknown")
            intents[intent] = intents.get(intent, 0) + 1
            sev = cl.get("impact_severity", "unknown")
            severities[sev] = severities.get(sev, 0) + 1
            if cl.get("bearish_signal", False):
                bearish_count += 1
        return {
            "total_whale_txs": len(whale_txs),
            "total_classifications": len(classifications),
            "intent_breakdown": intents,
            "severity_breakdown": severities,
            "bearish_signals": bearish_count,
        }
