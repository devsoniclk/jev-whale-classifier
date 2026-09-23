from __future__ import annotations

"""Jev OpenRouter client for whale transaction classification."""

import os

import requests


JEV_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "typesafe/jev-1.13"


def classify_whale_tx(tx_data: dict) -> dict:
    """Send a whale transaction to Jev for classification.

    Returns dict with: intent, bearish_signal (bool), impact_severity, reasoning.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {
            "intent": "unknown",
            "bearish_signal": False,
            "impact_severity": "unknown",
            "reasoning": "No OPENROUTER_API_KEY set",
        }

    # Build the state string describing the whale transaction
    state_parts = [
        f"Whale transaction detected on {tx_data['asset']} network.",
        f"Amount: {tx_data['amount']} {tx_data['asset']} (${tx_data['usd_value']:,.2f} USD).",
        f"From: {tx_data['from_anonymized']}",
        f"To: {tx_data['to_anonymized']}",
    ]
    if tx_data.get("exchange_from"):
        state_parts.append(f"Sender is a known exchange: {tx_data['exchange_from']}.")
    if tx_data.get("exchange_to"):
        state_parts.append(f"Recipient is a known exchange: {tx_data['exchange_to']}.")
    if tx_data.get("input_count"):
        state_parts.append(f"Transaction has {tx_data['input_count']} inputs and {tx_data['output_count']} outputs.")

    # Context clues for Jev
    if tx_data.get("exchange_to") and not tx_data.get("exchange_from"):
        state_parts.append("Funds are moving TO an exchange from a private wallet.")
    elif tx_data.get("exchange_from") and not tx_data.get("exchange_to"):
        state_parts.append("Funds are moving FROM an exchange to a private wallet.")
    elif tx_data.get("exchange_from") and tx_data.get("exchange_to"):
        state_parts.append("Funds are moving between two exchanges.")

    state = " ".join(state_parts)

    payload = {
        "model": JEV_MODEL,
        "state": state,
        "questions": {
            "q0": {
                "type": "choice",
                "instructions": "What is the likely intent of this whale transaction?",
                "criteria": {
                    "accumulation": "Whale is buying/accumulating assets, moving to cold storage or private wallet",
                    "distribution": "Whale is selling/distributing assets, moving to exchange to sell",
                    "hedging": "Whale is hedging an existing position, possibly moving to DeFi protocols",
                    "rebalancing": "Whale is rebalancing portfolio, moving between wallets or assets",
                    "liquidation-prep": "Whale is preparing for liquidation or large OTC deal",
                },
            },
            "q1": {
                "type": "noul",
                "instructions": "Is this whale transaction a bearish signal for the market?",
            },
            "q2": {
                "type": "score",
                "instructions": "What is the market impact severity of this whale movement?",
                "criteria": [
                    "negligible - minimal market impact expected",
                    "minor - slight price movement possible",
                    "moderate - noticeable price impact likely",
                    "major - significant price movement expected",
                    "crash-risk - potential to trigger cascading liquidations or market crash",
                ],
            },
        },
    }

    try:
        r = requests.post(
            JEV_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        # Parse Jev response
        decisions = data.get("decisions", {})
        intent = decisions.get("q0", {}).get("choice", "unknown")
        bearish = decisions.get("q1", {}).get("noul", False)
        severity_score = decisions.get("q2", {}).get("score", 0)

        # Map score to severity label
        severity_map = {1: "negligible", 2: "minor", 3: "moderate", 4: "major", 5: "crash-risk"}
        if isinstance(severity_score, (int, float)):
            severity = severity_map.get(round(float(severity_score)), "moderate")
        else:
            severity = str(severity_score)

        return {
            "intent": intent,
            "bearish_signal": bool(bearish),
            "impact_severity": severity,
            "raw_score": severity_score,
            "reasoning": decisions.get("q0", {}).get("reasoning", ""),
            "state_analyzed": state,
        }

    except requests.exceptions.HTTPError as e:
        return {
            "intent": "error",
            "bearish_signal": False,
            "impact_severity": "unknown",
            "reasoning": f"HTTP error: {e}",
            "state_analyzed": state,
        }
    except Exception as e:
        return {
            "intent": "error",
            "bearish_signal": False,
            "impact_severity": "unknown",
            "reasoning": f"Error: {e}",
            "state_analyzed": state,
        }
