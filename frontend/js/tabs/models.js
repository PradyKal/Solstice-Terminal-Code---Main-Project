window.solstice.tabs.models = {
  async mount() {
    const root = document.getElementById('view-models');
    root.innerHTML = `
      <div class="panel">
        <div class="panel-h">STRATEGY PERFORMANCE · META-MODEL WEIGHTS</div>
        <div class="panel-body" style="padding:0">
          <table class="dt">
            <thead><tr>
              <th>STRATEGY</th><th>WEIGHT</th><th>SIGNALS</th><th>WIN RATE</th><th>AVG RETURN</th><th>SHARPE</th><th>ATTRIBUTED PNL</th><th>REGIME</th><th>UPDATED</th>
            </tr></thead>
            <tbody id="tb-models"></tbody>
          </table>
        </div>
      </div>`;
    const client = window.solstice.sb();
    const fmt = window.solstice.fmt;

    async function refresh() {
      const { data } = await client.from('strategy_performance').select('*')
        .order('created_at', { ascending: false }).limit(50);
      const tb = document.getElementById('tb-models');
      if (!data || !data.length) { tb.innerHTML = '<tr><td colspan="9"><div class="empty">AWAITING GUMLOOP</div></td></tr>'; return; }
      // Take only latest per strategy
      const latest = {};
      data.forEach(r => { if (!latest[r.strategy]) latest[r.strategy] = r; });
      tb.innerHTML = Object.values(latest).map(r => `
        <tr>
          <td>${r.strategy}</td>
          <td class="num">
            ${(+r.weight*100).toFixed(1)}%
            <div class="bar-track" style="width:80px;display:inline-block;margin-left:8px;vertical-align:middle">
              <div class="bar-fill" style="width:${Math.min(100, +r.weight*100*3)}%"></div>
            </div>
          </td>
          <td class="num">${r.signals_emitted ?? '—'}</td>
          <td class="num">${fmt.pct(r.win_rate)}</td>
          <td class="num">${fmt.pct(r.avg_return)}</td>
          <td class="num">${fmt.num(r.sharpe, 2)}</td>
          <td class="num ${(+r.attribution_pnl||0) >= 0 ? 'pos':'neg'}">${fmt.usd(r.attribution_pnl)}</td>
          <td class="dim">${r.regime || '—'}</td>
          <td class="dim">${fmt.time(r.created_at)}</td>
        </tr>`).join('');
    }
    refresh();
    client.channel('rt-models')
      .on('postgres_changes', { event: '*', schema:'public', table:'strategy_performance' }, refresh)
      .subscribe();
  },
};
