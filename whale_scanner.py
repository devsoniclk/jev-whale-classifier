from __future__ import annotations

"""Fetch large crypto transactions from public APIs.

ETH: Uses public Ethereum RPC (Cloudflare, Ankr) - no API key needed
BTC: Uses blockchain.info API - no API key needed
Etherscan: Optional, for enhanced data when API key is available
"""

import os
import time
from datetime import datetime, timezone

import requests
import yaml


def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def anonymize_address(addr: str) -> str:
    """Show first 6 and last 4 chars only."""
    if not addr or len(addr) <= 10:
        return addr or "unknown"
    return f"{addr[:6]}...{addr[-4:]}"


# Known exchange addresses (subset for detection)
KNOWN_EXCHANGES = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance",
    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase",
    "0x3cd751e6b0078be393132286c442345e68ff0aab": "Coinbase",
    # Kraken
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": "Kraken",
    # Bitfinex
    "0x1151314c646ce4e0efd76d1af4760ae66a9fe30f": "Bitfinex",
    "0x742d35cc6634c0532925a3b844bc9e7595f2bd3e": "Bitfinex",
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": "Gemini",
}


def detect_exchange(addr: str) -> str | None:
    if not addr:
        return None
    return KNOWN_EXCHANGES.get(addr.lower())


def get_eth_price() -> float:
    """Get current ETH price in USD."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "usd"},
            timeout=10,
        )
        return r.json()["ethereum"]["usd"]
    except Exception:
        return 3500.0


def get_btc_price() -> float:
    """Get current BTC price in USD."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        return r.json()["bitcoin"]["usd"]
    except Exception:
        return 100000.0


# Public Ethereum RPC endpoints (free, no key)
ETH_RPC_ENDPOINTS = [
    "https://cloudflare-eth.com",
    "https://rpc.ankr.com/eth",
    "https://eth.llamarpc.com",
    "https://ethereum-rpc.publicnode.com",
]


def _eth_rpc(method: str, params: list) -> dict:
    """Call Ethereum JSON-RPC with fallback endpoints."""
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    for endpoint in ETH_RPC_ENDPOINTS:
        try:
            r = requests.post(endpoint, json=payload, timeout=10)
            data = r.json()
            if "result" in data:
                return data["result"]
        except Exception:
            continue
    return None


def _hex_to_int(val: str) -> int:
    if isinstance(val, str) and val.startswith("0x"):
        return int(val, 16)
    return int(val) if val else 0


def scan_eth_whales(min_value_eth: float = 100) -> list[dict]:
    """Fetch recent large ETH transfers using public RPC."""
    eth_price = get_eth_price()
    min_wei = int(min_value_eth * 10**18)

    # Get latest block number
    latest_hex = _eth_rpc("eth_blockNumber", [])
    if not latest_hex:
        print("  Failed to get latest block from ETH RPC")
        return []
    latest_block = _hex_to_int(latest_hex)

    whales = []
    blocks_to_scan = 5
    for block_offset in range(blocks_to_scan):
        block_num = latest_block - block_offset
        block_hex = hex(block_num)
        block_data = _eth_rpc("eth_getBlockByNumber", [block_hex, True])

        if not block_data or not isinstance(block_data, dict):
            continue

        txs = block_data.get("transactions", [])
        for tx in txs:
            if not isinstance(tx, dict):
                continue
            value_wei = _hex_to_int(tx.get("value", "0x0"))
            if value_wei >= min_wei:
                value_eth = value_wei / 10**18
                from_addr = tx.get("from", "")
                to_addr = tx.get("to", "") or ""
                whales.append({
                    "asset": "ETH",
                    "tx_hash": tx.get("hash", ""),
                    "from": from_addr,
                    "from_anonymized": anonymize_address(from_addr),
                    "to": to_addr,
                    "to_anonymized": anonymize_address(to_addr),
                    "amount": round(value_eth, 4),
                    "usd_value": round(value_eth * eth_price, 2),
                    "exchange_from": detect_exchange(from_addr),
                    "exchange_to": detect_exchange(to_addr),
                    "block": block_num,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        time.sleep(0.2)

    return whales


def scan_btc_whales(min_value_btc: float = 50) -> list[dict]:
    """Fetch recent large BTC transactions from blockchain.info."""
    btc_price = get_btc_price()
    min_satoshi = int(min_value_btc * 10**8)

    whales = []
    try:
        r = requests.get(
            "https://blockchain.info/unconfirmed-transactions?format=json",
            timeout=15,
        )
        r.raise_for_status()
        txs = r.json().get("txs", [])
        for tx in txs:
            total_out = sum(o.get("value", 0) for o in tx.get("out", []))
            if total_out >= min_satoshi:
                value_btc = total_out / 10**8
                in_addrs = [
                    inp.get("prev_out", {}).get("addr", "unknown")
                    for inp in tx.get("inputs", [])
                ]
                out_addrs = [o.get("addr", "unknown") for o in tx.get("out", [])]
                from_addr = in_addrs[0] if in_addrs else "unknown"
                to_addr = out_addrs[0] if out_addrs else "unknown"
                whales.append({
                    "asset": "BTC",
                    "tx_hash": tx.get("hash", ""),
                    "from": from_addr,
                    "from_anonymized": anonymize_address(str(from_addr)),
                    "to": to_addr,
                    "to_anonymized": anonymize_address(str(to_addr)),
                    "amount": round(value_btc, 8),
                    "usd_value": round(value_btc * btc_price, 2),
                    "exchange_from": None,
                    "exchange_to": None,
                    "block": tx.get("block_height", 0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "input_count": len(tx.get("inputs", [])),
                    "output_count": len(tx.get("out", [])),
                })
    except Exception as e:
        print(f"  Error scanning BTC: {e}")

    return whales


def scan_all(min_eth: float = 100, min_btc: float = 50) -> list[dict]:
    """Scan both ETH and BTC for whale transactions."""
    print("Scanning ETH whale transactions...")
    eth_whales = scan_eth_whales(min_eth)
    print(f"  Found {len(eth_whales)} ETH whale txs")

    print("Scanning BTC whale transactions...")
    btc_whales = scan_btc_whales(min_btc)
    print(f"  Found {len(btc_whales)} BTC whale txs")

    return eth_whales + btc_whales
