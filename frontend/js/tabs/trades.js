window.solstice.tabs.trades = {
  mount() {
    liveTable('trades', 'trades', [
      { key: 'ticker', label: 'TICKER', cls: 'bold' },
      { key: 'side', label: 'SIDE', fmt: v => `<span class="pill ${v==='BUY'?'buy':'sell'}">${v}</span>` },
      { key: 'qty', label: 'QTY', cls: 'num', fmt: v => (+v).toFixed(4) },
      { key: 'entry_price', label: 'ENTRY', cls: 'num', fmt: v => '$' + (+v).toFixed(2) },
      { key: 'exit_price', label: 'EXIT', cls: 'num', fmt: v => v ? '$' + (+v).toFixed(2) : '—' },
      { key: 'pnl', label: 'PNL', cls: 'num', fmt: v => v == null ? '—' :
        `<span class="${+v >= 0 ? 'pos' : 'neg'}">${window.solstice.fmt.usd(v)}</span>` },
      { key: 'status', label: 'STATUS', fmt: v => {
        const cls = v === 'SUBMITTED' || v === 'FILLED' ? 'buy' :
                    v?.startsWith('REJECT') ? 'sell' : v?.includes('CLOSED') ? 'warn' : 'hold';
        return `<span class="pill ${cls}">${v}</span>`;
      }},
      { key: 'confidence', label: 'CONF', cls: 'num', fmt: v => v ? (+v).toFixed(3) : '—' },
      { key: 'broker', label: 'BROKER', cls: 'dim' },
      { key: 'broker_order_id', label: 'ORDER ID', cls: 'dim', fmt: v => v ? v.slice(0,10)+'…' : '—' },
      { key: 'created_at', label: 'TIME', cls: 'dim', fmt: v => window.solstice.fmt.time(v) },
    ], {
      title: 'TRADES',
      sub: 'alpaca paper · risk-cleared executions only',
      panelTitle: 'Trade Ledger',
      limit: 200,
    });
  },
};
