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
# ETH addresses — lowercased for case-insensitive matching
KNOWN_EXCHANGES_ETH = {
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance",
    "0x8894e0a0c962cb723c1ef8a1b2c6d40afc0e9c47": "Binance",
    # Coinbase
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase",
    "0x3cd751e6b0078be393132286c442345e68ff0aab": "Coinbase",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    "0x5c3e0e7f6dfc7c9698b0f01c0e23f0e4fca8b3b2": "Coinbase Prime",
    # Kraken
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13": "Kraken",
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Kraken",
    # FTX (legacy — addresses that may still hold funds)
    "0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2": "FTX",
    "0xc098b2a3aa256d2140208c3de6543aaef5cd3a94": "FTX",
    "0x83c209d1e523febc72b7a2d41d6bea3a5e0e1f8c": "FTX",
    # Bitfinex
    "0x1151314c646ce4e0efd76d1af4760ae66a9fe30f": "Bitfinex",
    "0x742d35cc6634c0532925a3b844bc9e7595f2bd3e": "Bitfinex",
    # OKX
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "OKX",
    # Gemini
    "0xd24400ae8bfebb18ca49be86258a3c749cf46853": "Gemini",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8": "Gemini",
    # Huobi / HTX
    "0xab5c66752a9e8167967685f1450532fb96d5d24f": "HTX",
    "0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b": "HTX",
    # Gate.io
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io",
    # KuCoin
    "0xd6216fc19db775df9774a6e33526131da7d19a2c": "KuCoin",
    # Bybit
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit",
}

# BTC addresses — well-known exchange deposit/withdrawal addresses
# These are representative hot-wallet addresses (BTC addresses change frequently)
KNOWN_EXCHANGES_BTC = {
    # Binance
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": "Binance",
    "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j": "Binance",
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s": "Binance",
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": "Binance",
    # Coinbase
    "3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS": "Coinbase",
    "3FHNBLobJnbCTFTVakh5TXmEneyf5PT61B": "Coinbase",
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": "Coinbase",
    # Kraken
    "3FupZp77ySr7jwoLYEJ9mwzJpvoNBXsBnE": "Kraken",
    "bc1qkw8c5rvnzs8qp0w2y9345cv9wd80gasm2spgh3": "Kraken",
    # Bitfinex
    "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j": "Bitfinex",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdpyv5dqv75kn4": "Bitfinex",
}

# Merge for unified lookup (ETH and BTC address spaces don't overlap)
KNOWN_EXCHANGES = {**KNOWN_EXCHANGES_ETH, **KNOWN_EXCHANGES_BTC}


def detect_exchange(addr: str) -> str | None:
    if not addr:
        return None
    return KNOWN_EXCHANGES.get(addr.lower())


_price_cache = {"prices": None, "ts": 0}


def _fetch_prices() -> dict:
    """Fetch ETH and BTC prices from CoinGecko with 60s caching."""
    now = time.time()
    if _price_cache["prices"] and now - _price_cache["ts"] < 60:
        return _price_cache["prices"]
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum,bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        prices = {
            "eth": data["ethereum"]["usd"],
            "btc": data["bitcoin"]["usd"],
        }
        _price_cache["prices"] = prices
        _price_cache["ts"] = now
        return prices
    except Exception:
        return {"eth": 3500.0, "btc": 100000.0}


def get_eth_price() -> float:
    """Get current ETH price in USD."""
    return _fetch_prices()["eth"]


def get_btc_price() -> float:
    """Get current BTC price in USD."""
    return _fetch_prices()["btc"]


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
                    "exchange_from": detect_exchange(str(from_addr)),
                    "exchange_to": detect_exchange(str(to_addr)),
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
