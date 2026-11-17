"""cbBTC dip-rider: buy-the-dip entry, crash stop, trailing profit.

Strategy (all decisions from bar closes, no clock, deterministic):
- Before entering: wait up to DIP_WAIT_BARS bars for a pullback of at least
  DIP_BPS below the first close seen, then buy with all cash (the dip gives a
  better entry than buying the first bar outright). If no dip arrives within
  DIP_WAIT_BARS bars, buy anyway (stay long, like the market drifts).
- While long: hold, but two exits protect equity:
  * crash stop: close fell STOP_BPS below entry close -> sell, then re-enter
    once the close recovers within 100 bps of the recent rolling max;
  * trailing profit: after the close ran TRAIL_ARM_BPS above entry, a pullback
    of TRAIL_BPS from the running peak sells and stays in cash.
Everything is integer math on the protocol's u64 decimal strings; orders carry
a generous max_slippage_bps so the fills are never refused for slippage.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

DIP_BPS = 60
DIP_WAIT_BARS = 12
STOP_BPS = 2000
TRAIL_ARM_BPS = 300
TRAIL_BPS = 150
REENTRY_WINDOW_BARS = 240  # bars kept for the re-entry watch (~4 hours)
MAX_SLIPPAGE_BPS = 10_000

BPS = 10_000


class Strategy:
    def __init__(self):
        self.first_close = None
        self.entry_close = 0
        self.peak_close = 0
        self.stopped = False
        self.started = False
        self.recent = []  # closes since re-entry watch began
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
            if close * BPS < self.entry_close * (BPS - STOP_BPS):
                self.stopped = True
                self.entry_close = 0
                self.peak_close = 0
                self.recent = []
                return [{"side": "sell", "symbol": self.symbol, "qty": state.positions[0]["qty"], "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            if self.peak_close * BPS > self.entry_close * (BPS + TRAIL_ARM_BPS) and close * BPS < self.peak_close * (BPS - TRAIL_BPS):
                self.entry_close = 0
                self.peak_close = 0
                return [{"side": "sell", "symbol": self.symbol, "qty": state.positions[0]["qty"], "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            return []

        if self.stopped:
            self.recent.append(close)
            if len(self.recent) > REENTRY_WINDOW_BARS:
                self.recent.pop(0)
            if close * BPS >= max(self.recent) * (BPS - 100):
                self.stopped = False
                return self._buy(state, close)
            return []

        if not self.started:
            if close * BPS <= self.first_close * (BPS - DIP_BPS):
                self.started = True
                return self._buy(state, close)
            if state.seq >= DIP_WAIT_BARS:
                self.started = True
                return self._buy(state, close)
            return []

        return []

    def _buy(self, state, close):
        self.entry_close = close
        self.peak_close = close
        self.recent = []
        cash = state.cash
        eq = state.equity
        cap = (state.hello["caps"]["max_weight_bps"] * eq) // BPS
        amount = cash if cash < cap else cap
        if amount < int(state.hello["fees"]["min_notional_quote_units"]):
            return []
        return [{"side": "buy", "symbol": self.symbol, "notional_quote_units": amount, "max_slippage_bps": MAX_SLIPPAGE_BPS}]


def main():
    strat = Strategy()

    def on_batch(state, batch):
        return strat.on_batch(state, batch)

    makefun_bars.run(on_batch)


if __name__ == "__main__":
    main()
