# cbbtc-dip-rider

A paper-trading bot for the make.fun competition [btc-race-24h-20261117-0603](https://make.fun/competitions/btc-race-24h-20261117-0603): it trades Coinbase Wrapped BTC (cbBTC) against USDC, minute by minute, on a replay of the Orca Whirlpool's on-chain prices, starting from 1,000 USDC of paper money. Nothing is traded for real — simulation only.

[![btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/competitions/btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/agay12/cbbtc-dip-rider/rank.svg)](https://make.fun/competitions/btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/agay12/cbbtc-dip-rider/reward.svg)](https://make.fun/competitions/btc-race-24h-20261117-0603)

## Strategy (cbBTC dip-rider)

All decisions come from bar closes only — no clock, no randomness, fully deterministic byte for byte across runs:

- **Dip entry**: instead of buying the first bar outright, it waits up to 12 bars for a pullback of at least 60 bps below the first close, then goes all-in. If no dip arrives, it buys anyway to keep the drift exposure.
- **Crash stop**: a close 20% below the entry close sells, then re-enters once price recovers within 100 bps of the recent rolling high.
- **Trailing profit**: after the price runs 300 bps above entry, a 150 bps pullback from the running peak banks the gain and sits in cash.

Costs are real: every round trip pays ~26 bps in fees, slippage and constant-product price impact, so the bot trades rarely and holds long.

## Layout

- `main.py` — the bot (Python 3.13, standard library only), speaking agent-fun/bars-replay/v1 on stdin/stdout.
- `vendor/makefun_bars.py` — byte-for-byte copy of the kit's official Python SDK shim.
- `.makefun/freshness.json` — repository freshness anchor written by `makefun init`.

## Local grade on the published dev window

Run with the kit's exact harness (`node cli/makefun.mjs grade-local --kit <kit> --bot . --driver docker`):

- net PnL **+4.05 USDC** (return +0.40%), 1 trade, win rate 1.0
- max drawdown 2.1%, 0 rejected orders, deterministic (two executions reproduce byte for byte)
- guardrails met: >=1 trade, drawdown <= 25%

## License

MIT — see [LICENSE](LICENSE).
