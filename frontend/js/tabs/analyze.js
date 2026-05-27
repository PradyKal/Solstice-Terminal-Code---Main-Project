// helper: realtime-subscribed table with cleaner header + counts
window.solstice.tabs = window.solstice.tabs || {};

function buildView(viewId, title, sub) {
  const root = document.getElementById('view-' + viewId);
  root.innerHTML = `
    <div class="view-header">
      <div class="view-title">${title}</div>
      <div class="view-sub" id="vsub-${viewId}">${sub || ''}</div>
    </div>
    <div id="vbody-${viewId}"></div>`;
  return document.getElementById('vbody-' + viewId);
}

function liveTable(viewId, table, columns, opts = {}) {
  const body = buildView(viewId, opts.title || viewId.toUpperCase(), opts.sub);
  body.innerHTML = `
    <div class="panel">
      <div class="panel-h">
        <span>${(opts.panelTitle || table).toUpperCase()}</span>
        <span class="badge" id="cnt-${viewId}">LIVE</span>
      </div>
      <div class="panel-body flush">
        <table class="dt">
          <thead><tr>${columns.map(c => `<th>${c.label}</th>`).join('')}</tr></thead>
          <tbody id="tb-${viewId}"></tbody>
        </table>
      </div>
    </div>`;
  const tb = document.getElementById('tb-' + viewId);
  const cnt = document.getElementById('cnt-' + viewId);

  function row(r) {
    return `<tr>${columns.map(c => {
      const v = c.fmt ? c.fmt(r[c.key], r) : (r[c.key] ?? '—');
      return `<td class="${c.cls || ''}">${v}</td>`;
    }).join('')}</tr>`;
  }
  const client = window.solstice.sb();
  async function refresh() {
    let q = client.from(table).select('*')
      .order(opts.orderBy || 'created_at', { ascending: false });
    if (opts.limit) q = q.limit(opts.limit);
    const { data } = await q;
    cnt.textContent = (data?.length || 0) + ' ROWS';
    tb.innerHTML = (data || []).map(row).join('') ||
      `<tr><td colspan="${columns.length}"><div class="empty">AWAITING GUMLOOP</div></td></tr>`;
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
      { key: 'ticker', label: 'TICKER', cls: 'bold' },
      { key: 'signal', label: 'SIGNAL', fmt: v => `<span class="pill ${v==='BUY'?'buy':v==='SELL'?'sell':'hold'}">${v}</span>` },
      { key: 'confidence', label: 'CONF', cls: 'num', fmt: v => {
        const n = +v;
        const c = n >= 0.75 ? 'pos' : n >= 0.5 ? '' : 'dim';
        return `<span class="${c}">${n.toFixed(3)}</span>`;
      }},
      { key: 'expected_return', label: 'E[R]', cls: 'num', fmt: v => {
        const n = (+v)*100;
        return `<span class="${n>=0?'pos':'neg'}">${n>=0?'+':''}${n.toFixed(2)}%</span>`;
      }},
      { key: 'risk_score', label: 'RISK', cls: 'num', fmt: v => (+v).toFixed(3) },
      { key: 'price', label: 'PRICE', cls: 'num bold', fmt: v => '$' + (+v).toFixed(2) },
      { key: 'asset_class', label: 'CLASS', cls: 'dim' },
      { key: 'regime', label: 'REGIME', cls: 'dim' },
      { key: 'rationale', label: 'RATIONALE', cls: 'dim mono', fmt: v => v ? v.slice(0, 60) : '—' },
      { key: 'created_at', label: 'TIME', cls: 'dim', fmt: v => window.solstice.fmt.time(v) },
    ], {
      title: 'ANALYZE',
      sub: 'live cross-sectional ranking · realtime postgres_changes',
      panelTitle: 'Live Signals · Top by |Confidence|',
      orderBy: 'created_at',
      limit: 100,
    });
  },
};
