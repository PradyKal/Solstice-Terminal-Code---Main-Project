document.getElementById('shell-top').outerHTML = window.solstice.shellHTML('research');
document.getElementById('shell-bottom').outerHTML = window.solstice.footerHTML();
window.solstice.appShell('research');

(async () => {
  const client = window.solstice.sb();
  const fmt = window.solstice.fmt;

  // ─── Signals table ───
  async function refreshSignals() {
    const { data } = await client.from('signals').select('*')
      .order('created_at', { ascending: false }).limit(40);
    document.getElementById('sig-count').textContent = (data?.length || 0) + ' rows';
    const tb = document.getElementById('sig-tbody');
    if (!data?.length) { tb.innerHTML = '<tr><td colspan="8"><div class="empty">AWAITING ENGINE</div></td></tr>'; return; }
    tb.innerHTML = data.map(s => {
      const conf = +s.confidence;
      const er = (+s.expected_return) * 100;
      return `<tr>
        <td class="bold">${s.ticker}</td>
        <td><span class="pill ${s.signal==='BUY'?'buy':s.signal==='SELL'?'sell':'hold'}">${s.signal}</span></td>
        <td>
          <div class="conf-cell">
            <div class="conf-bar"><div style="width:${Math.min(100, conf*100*1.4)}%"></div></div>
            <span class="cyan tnum">${conf.toFixed(3)}</span>
          </div>
        </td>
        <td class="num ${er>=0?'pos':'neg'}">${er>=0?'+':''}${er.toFixed(2)}%</td>
        <td class="num">${(+s.risk_score).toFixed(3)}</td>
        <td class="num bold">$${(+s.price).toFixed(2)}</td>
        <td class="dim">${s.regime || '—'}</td>
        <td class="dim">${fmt.time(s.created_at)}</td>
      </tr>`;
    }).join('');
  }
  refreshSignals();

  // ─── Latest visualization payloads ───
  async function loadViz(type, containerId, metaId) {
    const { data } = await client.from('visualization_data')
      .select('payload, ticker, created_at')
      .eq('viz_type', type)
      .order('created_at', { ascending: false }).limit(1);
    const c = document.getElementById(containerId);
    if (data?.[0]?.payload) {
      window.solstice.viz.render(c, type, data[0].payload);
      if (metaId && data[0].ticker) document.getElementById(metaId).textContent = data[0].ticker;
    } else {
      c.innerHTML = '<div class="empty">AWAITING ENGINE</div>';
    }
  }
  loadViz('mc_path_cloud', 'viz-mc', 'mc-ticker');
  loadViz('risk_topology', 'viz-risk');
  loadViz('vol_surface_3d', 'viz-vol', 'vol-ticker');
  loadViz('pca_factor_decomposition', 'viz-pca');
  loadViz('correlation_network', 'viz-network');
  loadViz('liquidity_heatmap', 'viz-liq');

  client.channel('rt-research')
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals' }, refreshSignals)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'visualization_data' }, (p) => {
      const map = {
        mc_path_cloud: ['viz-mc','mc-ticker'],
        risk_topology: ['viz-risk', null],
        vol_surface_3d: ['viz-vol','vol-ticker'],
        pca_factor_decomposition: ['viz-pca', null],
        correlation_network: ['viz-network', null],
        liquidity_heatmap: ['viz-liq', null],
      };
      const m = map[p.new.viz_type];
      if (m) loadViz(p.new.viz_type, m[0], m[1]);
    })
    .subscribe();
})();
