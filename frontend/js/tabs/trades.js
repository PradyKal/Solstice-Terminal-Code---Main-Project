window.solstice.tabs.trades = {
  mount() {
    liveTable('trades', 'trades', [
      { key: 'ticker', label: 'TICKER' },
      { key: 'side', label: 'SIDE', fmt: v => `<span class="pill ${v==='BUY'?'buy':'sell'}">${v}</span>` },
      { key: 'qty', label: 'QTY', cls: 'num', fmt: v => (+v).toFixed(4) },
      { key: 'entry_price', label: 'ENTRY', cls: 'num', fmt: v => '$' + (+v).toFixed(2) },
      { key: 'exit_price', label: 'EXIT', cls: 'num', fmt: v => v ? '$' + (+v).toFixed(2) : '—' },
      { key: 'pnl', label: 'PNL', cls: 'num', fmt: (v, r) => {
        if (v === null || v === undefined) return '—';
        return `<span class="${+v >= 0 ? 'pos':'neg'}">${window.solstice.fmt.usd(v)}</span>`;
      }},
      { key: 'status', label: 'STATUS', fmt: v => {
        const cls = v === 'SUBMITTED' || v === 'FILLED' ? 'buy' :
                    v?.startsWith('REJECT') ? 'sell' : 'hold';
        return `<span class="pill ${cls}">${v}</span>`;
      }},
      { key: 'confidence', label: 'CONF', cls: 'num', fmt: v => v ? (+v).toFixed(3) : '—' },
      { key: 'broker_order_id', label: 'ORDER ID', cls: 'dim', fmt: v => v ? v.slice(0,12)+'…' : '—' },
      { key: 'created_at', label: 'TIME', cls: 'dim', fmt: v => window.solstice.fmt.time(v) },
    ], { title: 'Alpaca Paper Trades', limit: 200 });
  },
};
