window.solstice.tabs = window.solstice.tabs || {};

// helper: realtime-subscribed table render
function liveTable(viewId, table, columns, opts = {}) {
  const root = document.getElementById('view-' + viewId);
  root.innerHTML = `
    <div class="panel">
      <div class="panel-h">${(opts.title || table).toUpperCase()}</div>
      <div class="panel-body" style="padding:0;max-height:calc(100vh - 110px);overflow:auto">
        <table class="dt">
          <thead><tr>${columns.map(c => `<th>${c.label}</th>`).join('')}</tr></thead>
          <tbody id="tb-${viewId}"></tbody>
        </table>
      </div>
    </div>`;
  const body = document.getElementById('tb-' + viewId);
  function row(r) {
    return `<tr>${columns.map(c => {
      const v = c.fmt ? c.fmt(r[c.key], r) : (r[c.key] ?? '—');
      return `<td class="${c.cls || ''}">${v}</td>`;
    }).join('')}</tr>`;
  }
  const client = window.solstice.sb();
  async function refresh() {
    let q = client.from(table).select('*').order(opts.orderBy || 'created_at', { ascending: false });
    if (opts.limit) q = q.limit(opts.limit);
    const { data } = await q;
    body.innerHTML = (data || []).map(row).join('') ||
      '<tr><td colspan="' + columns.length + '"><div class="empty">AWAITING GUMLOOP</div></td></tr>';
  }
  refresh();
  const channel = client.channel(`rt-${viewId}`)
    .on('postgres_changes', { event: '*', schema: 'public', table }, refresh)
    .subscribe();
  return { refresh, channel };
}

window.solstice.tabs.analyze = {
  mount() {
    liveTable('analyze', 'signals', [
      { key: 'ticker', label: 'TICKER', cls: '' },
      { key: 'signal', label: 'SIGNAL', fmt: v => `<span class="pill ${v==='BUY'?'buy':v==='SELL'?'sell':'hold'}">${v}</span>` },
      { key: 'confidence', label: 'CONF', cls: 'num', fmt: v => (+v).toFixed(3) },
      { key: 'expected_return', label: 'E[R]', cls: 'num', fmt: v => ((+v)*100).toFixed(2)+'%' },
      { key: 'risk_score', label: 'RISK', cls: 'num', fmt: v => (+v).toFixed(3) },
      { key: 'price', label: 'PRICE', cls: 'num', fmt: v => '$' + (+v).toFixed(2) },
      { key: 'asset_class', label: 'CLASS', cls: 'dim' },
      { key: 'regime', label: 'REGIME', cls: 'dim' },
      { key: 'rationale', label: 'RATIONALE', cls: 'dim' },
      { key: 'created_at', label: 'TIME', cls: 'dim', fmt: v => window.solstice.fmt.time(v) },
    ], { title: 'Live Signals · Ranked by Confidence', orderBy: 'created_at', limit: 100 });
  },
};
