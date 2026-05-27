window.solstice.tabs.risk = {
  async mount() {
    const root = document.getElementById('view-risk');
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="viz-card" id="risk-topo" style="height:45vh">
          <div class="viz-title">RISK TOPOLOGY · alpha × E[R] × risk × liquidity</div>
        </div>
        <div class="viz-card" id="risk-liq" style="height:45vh">
          <div class="viz-title">LIQUIDITY HEATMAP · ADV × realized vol deciles</div>
        </div>
        <div class="panel" style="grid-column:1 / -1">
          <div class="panel-h">RISK ENGINE STATE · LATEST CYCLE</div>
          <div class="panel-body" id="risk-state"><div class="empty">AWAITING GUMLOOP</div></div>
        </div>
      </div>`;
    const client = window.solstice.sb();

    async function loadViz(vizType, container) {
      const { data } = await client.from('visualization_data')
        .select('payload').eq('viz_type', vizType)
        .order('created_at', { ascending: false }).limit(1);
      if (data?.[0]?.payload) {
        window.solstice.viz.render(document.getElementById(container), vizType, data[0].payload);
      }
    }
    loadViz('risk_topology', 'risk-topo');
    loadViz('liquidity_heatmap', 'risk-liq');

    async function refreshState() {
      const { data } = await client.from('portfolio_metrics').select('*')
        .order('created_at', { ascending: false }).limit(1);
      const m = (data || [])[0];
      const el = document.getElementById('risk-state');
      if (!m) { el.innerHTML = '<div class="empty">AWAITING GUMLOOP</div>'; return; }
      const fmt = window.solstice.fmt;
      el.innerHTML = `
        <div class="grid cols-3">
          <div><span class="dim">GROSS EXPOSURE</span><br><b>${fmt.usd(m.gross_exposure)}</b></div>
          <div><span class="dim">NET EXPOSURE</span><br><b>${fmt.usd(m.net_exposure)}</b></div>
          <div><span class="dim">CONCENTRATION HHI</span><br><b>${fmt.num(m.concentration_hhi, 4)}</b></div>
          <div><span class="dim">MAX DRAWDOWN</span><br><b class="neg">${fmt.pct(m.max_drawdown)}</b></div>
          <div><span class="dim">ROLLING SHARPE</span><br><b>${fmt.num(m.rolling_sharpe, 2)}</b></div>
          <div><span class="dim">REGIME</span><br><b>${m.regime || '—'}</b></div>
        </div>`;
    }
    refreshState();
    client.channel('rt-risk')
      .on('postgres_changes', { event:'*', schema:'public', table:'portfolio_metrics' }, refreshState)
      .on('postgres_changes', { event:'*', schema:'public', table:'visualization_data' }, () => {
        loadViz('risk_topology', 'risk-topo');
        loadViz('liquidity_heatmap', 'risk-liq');
      })
      .subscribe();
  },
};
