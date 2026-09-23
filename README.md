# Jev Whale Classifier

A smart money movement analyzer that monitors large crypto transactions (whale movements) on Ethereum and Bitcoin, then classifies their likely intent using [Jev](https://openrouter.ai) AI decision engine.

## What It Does

- **Scans** ETH (public RPC) and BTC (Blockchain.info) for large transactions
- **Classifies** each whale movement with Jev:
  - **Intent**: accumulation, distribution, hedging, rebalancing, or liquidation-prep
  - **Bearish signal**: whether the movement suggests bearish market conditions
  - **Impact severity**: negligible → minor → moderate → major → crash-risk
- **Alerts** on significant movements with color-coded terminal output
- **Logs** all data to JSONL for analysis

## Setup

```bash
cd ~/Projects/jev-whale-classifier

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install requests python-dotenv pyyaml

# Configure
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY (required)
```

## Usage

```bash
# One-time scan (no Jev classification needed)
python run.py scan
python run.py scan --eth    # ETH only
python run.py scan --btc    # BTC only

# Scan + classify with Jev (requires OPENROUTER_API_KEY)
python run.py classify
python run.py classify --eth

# Continuous monitoring
python run.py monitor

# View statistics
python run.py stats
```

## Configuration

Edit `config.yaml` to adjust:
- **Whale thresholds**: minimum ETH/BTC amounts to flag
- **Poll interval**: how often to check in monitor mode
- **RPC endpoints**: public Ethereum RPC endpoints (free, no key needed)

## Architecture

```
run.py (CLI)
├── whale_scanner.py    # Fetches large txs from ETH public RPC + Blockchain.info
├── classifier.py       # Orchestrates scanning → Jev classification → alerts
├── jev_client.py       # Jev OpenRouter API client
└── logger.py           # JSONL logging for txs and classifications
```

## Data Sources

- **Ethereum**: Public RPC endpoints (Cloudflare, Ankr, LlamaRPC, Publicnode) — free, no API key
- **Bitcoin**: Blockchain.info unconfirmed transactions API — free, no API key
- **Prices**: CoinGecko free API for ETH/BTC USD prices

## Jev Questions

For each whale transaction, Jev answers:

1. **Intent** (choice): What is the whale doing?
   - `accumulation` - Buying, moving to cold storage
   - `distribution` - Selling, moving to exchange
   - `hedging` - Hedging via DeFi
   - `rebalancing` - Portfolio rebalancing
   - `liquidation-prep` - Preparing for large sale/OTC

2. **Bearish signal** (noul): Is this bearish for the market?

3. **Impact severity** (score 1-5): How much market impact?
   - negligible / minor / moderate / major / crash-risk

## API Keys

- **OPENROUTER_API_KEY** (required for classify/monitor): Get at https://openrouter.ai/keys
- No other API keys needed — uses free public endpoints
