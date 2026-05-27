window.solstice.tabs.simulations = {
  async mount() {
    const root = document.getElementById('view-simulations');
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="panel">
          <div class="panel-h">MONTE CARLO RESULTS · 100K PATH SIMULATIONS</div>
          <div class="panel-body" style="padding:0;max-height:80vh;overflow:auto">
            <table class="dt">
              <thead><tr>
                <th>TICKER</th><th>MODEL</th><th>RUNS</th><th>HORIZON</th><th>μ</th><th>VAR95</th><th>CVAR95</th><th>P↑</th><th>REGIME</th><th>TIME</th>
              </tr></thead>
              <tbody id="tb-sims"></tbody>
            </table>
          </div>
        </div>
        <div class="panel">
          <div class="panel-h" id="sim-detail-h">MC PATH CLOUD · select a ticker</div>
          <div class="viz-card" id="sim-cloud" style="height:60vh"></div>
        </div>
      </div>`;
    const client = window.solstice.sb();
    const fmt = window.solstice.fmt;

    async function refresh() {
      const { data } = await client.from('simulations').select('*')
        .order('created_at', { ascending: false }).limit(100);
      const tb = document.getElementById('tb-sims');
      if (!data || !data.length) { tb.innerHTML = '<tr><td colspan="10"><div class="empty">AWAITING GUMLOOP</div></td></tr>'; return; }
      tb.innerHTML = data.map(r => `
        <tr style="cursor:pointer" onclick="window.solstice.tabs.simulations.showCloud('${r.ticker}')">
          <td>${r.ticker}</td>
          <td class="dim">${r.model}</td>
          <td class="num">${r.runs?.toLocaleString() || '—'}</td>
          <td class="num">${r.horizon_days}d</td>
          <td class="num ${(+r.mean_return||0) >= 0 ? 'pos':'neg'}">${fmt.pct(r.mean_return)}</td>
          <td class="num neg">${fmt.pct(r.var_95)}</td>
          <td class="num neg">${fmt.pct(r.cvar_95)}</td>
          <td class="num">${fmt.num(r.prob_up, 3)}</td>
          <td class="dim">${r.regime || '—'}</td>
          <td class="dim">${fmt.time(r.created_at)}</td>
        </tr>`).join('');
      // Auto-render first cloud
      if (data[0]) this.showCloud(data[0].ticker);
    }
    refresh.bind(this)();

    this.showCloud = async function (ticker) {
      document.getElementById('sim-detail-h').textContent = `MC PATH CLOUD · ${ticker}`;
      const { data } = await client.from('visualization_data')
        .select('payload').eq('viz_type','mc_path_cloud').eq('ticker', ticker)
        .order('created_at', { ascending: false }).limit(1);
      const payload = data?.[0]?.payload;
      const c = document.getElementById('sim-cloud');
      if (!payload) { c.innerHTML = '<div class="empty">NO MC PAYLOAD</div>'; return; }
      window.solstice.viz.render(c, 'mc_path_cloud', payload);
    };

    client.channel('rt-sims')
      .on('postgres_changes', { event: '*', schema:'public', table:'simulations' }, () => refresh.bind(this)())
      .subscribe();
  },
};
