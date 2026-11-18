"""cbBTC deep-dip rider: buy a big drawdown, ride the bounce with a tight trail.

Strategy (all decisions from bar closes, no clock, deterministic):
- Anchor on the first close seen after warm-up.
- Deep-dip entry: when the close falls at least DIP_BPS below the first close,
  buy with all available cash (capped by max_weight). A 2.5% drawdown in a
  single 24h window is a large, rare move; bounces off it pay far more than the
  ~26 bps full round-trip cost (4 bps fee + 4 bps pool fee + 2 bps slippage +
  constant-product impact).
- Exits while long (whichever comes first):
  * take profit: close runs TAKE_BPS above the entry close;
  * trailing stop: close falls TRAIL_BPS from the running peak close since entry.
  After an exit the same dip condition can re-trigger, so the bot re-rides
  further bounces.
- Fallback: if no deep dip arrived by FALLBACK_BAR, buy once anyway and hold
  with the same exits, so the bot is never flat for the whole window.

Everything is integer math on the protocol's u64 decimal strings; orders carry
a generous max_slippage_bps so fills are never refused for slippage.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

DIP_BPS = 250        # close at least this far below the first close -> buy
TAKE_BPS = 250       # close this far above the entry close -> sell
TRAIL_BPS = 100      # close this far below the peak close since entry -> sell
FALLBACK_BAR = 480   # if no dip by this batch index, buy once anyway
MAX_SLIPPAGE_BPS = 10_000

BPS = 10_000


class Strategy:
    def __init__(self):
        self.first_close = None
        self.entry_close = 0
        self.peak_close = 0
        self.ever_traded = False
        self.symbol = None

    def on_batch(self, state, batch):
        bar = None
        for b in batch["bars"]:
            if self.symbol is None or b["symbol"] == self.symbol:
                self.symbol = b["symbol"]
                bar = b
        if bar is None:
            return []
        close = int(bar["c"])
        if self.first_close is None:
            self.first_close = close

        if state.warming_up:
            return []

        if state.positions:
            self.peak_close = max(self.peak_close, close)
            if close * BPS >= self.entry_close * (BPS + TAKE_BPS):
                return self._sell(state)
            if close * BPS <= self.peak_close * (BPS - TRAIL_BPS):
                return self._sell(state)
            return []

        dipped = close * BPS <= self.first_close * (BPS - DIP_BPS)
        if dipped or (not self.ever_traded and state.seq >= FALLBACK_BAR):
            return self._buy(state, close)
        return []

    def _sell(self, state):
        self.entry_close = 0
        self.peak_close = 0
        return [{"side": "sell", "symbol": self.symbol, "qty": state.positions[0]["qty"],
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]

    def _buy(self, state, close):
        self.entry_close = close
        self.peak_close = close
        self.ever_traded = True
        cash = state.cash
        eq = state.equity
        cap = (state.hello["caps"]["max_weight_bps"] * eq) // BPS
        amount = cash if cash < cap else cap
        if amount < int(state.hello["fees"]["min_notional_quote_units"]):
            return []
        return [{"side": "buy", "symbol": self.symbol, "notional_quote_units": amount,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]


def main():
    strat = Strategy()

    def on_batch(state, batch):
        return strat.on_batch(state, batch)

    makefun_bars.run(on_batch)


if __name__ == "__main__":
    main()
