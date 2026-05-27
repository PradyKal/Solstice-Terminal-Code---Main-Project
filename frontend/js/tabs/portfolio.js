window.solstice.tabs.portfolio = {
  async mount() {
    const root = document.getElementById('view-portfolio');
    root.innerHTML = `
      <div class="grid cols-2">
        <div class="panel">
          <div class="panel-h">POSITIONS</div>
          <div class="panel-body" style="padding:0;max-height:60vh;overflow:auto">
            <table class="dt">
              <thead><tr>
                <th>TICKER</th><th>QTY</th><th>AVG ENTRY</th><th>MARK</th><th>UNREALIZED PNL</th><th>CLASS</th>
              </tr></thead>
              <tbody id="tb-positions"></tbody>
            </table>
          </div>
        </div>
        <div class="panel">
          <div class="panel-h">PORTFOLIO METRICS</div>
          <div class="panel-body" id="pm-body">
            <div class="empty">AWAITING GUMLOOP</div>
          </div>
        </div>
      </div>`;
    const client = window.solstice.sb();
    const fmt = window.solstice.fmt;

    async function refreshPositions() {
      const { data } = await client.from('positions').select('*').order('updated_at', { ascending: false });
      const tb = document.getElementById('tb-positions');
      if (!data || !data.length) {
        tb.innerHTML = '<tr><td colspan="6"><div class="empty">NO POSITIONS</div></td></tr>';
        return;
      }
      tb.innerHTML = data.map(r => `
        <tr>
          <td>${r.ticker}</td>
          <td class="num">${(+r.qty).toFixed(4)}</td>
          <td class="num">${fmt.usd(r.avg_entry)}</td>
          <td class="num">${fmt.usd(r.mark_price)}</td>
          <td class="num ${(+r.unrealized_pnl||0) >= 0 ? 'pos':'neg'}">${fmt.usd(r.unrealized_pnl)}</td>
          <td class="dim">${r.asset_class || '—'}</td>
        </tr>`).join('');
    }

    async function refreshMetrics() {
      const { data } = await client.from('portfolio_metrics').select('*')
        .order('created_at', { ascending: false }).limit(1);
      const m = (data || [])[0];
      const body = document.getElementById('pm-body');
      if (!m) { body.innerHTML = '<div class="empty">AWAITING GUMLOOP</div>'; return; }
      body.innerHTML = `
        <table class="dt">
          <tbody>
            <tr><td class="dim">Gross Exposure</td><td class="num">${fmt.usd(m.gross_exposure)}</td></tr>
            <tr><td class="dim">Net Exposure</td><td class="num">${fmt.usd(m.net_exposure)}</td></tr>
            <tr><td class="dim">Unrealized PnL</td><td class="num">${fmt.usd(m.unrealized_pnl)}</td></tr>
            <tr><td class="dim">Realized PnL</td><td class="num">${fmt.usd(m.realized_pnl)}</td></tr>
            <tr><td class="dim">Rolling Sharpe</td><td class="num">${fmt.num(m.rolling_sharpe, 2)}</td></tr>
            <tr><td class="dim">Rolling Sortino</td><td class="num">${fmt.num(m.rolling_sortino, 2)}</td></tr>
            <tr><td class="dim">Max Drawdown</td><td class="num neg">${fmt.pct(m.max_drawdown)}</td></tr>
            <tr><td class="dim">Beta vs SPY</td><td class="num">${fmt.num(m.beta_spy, 2)}</td></tr>
            <tr><td class="dim">HHI Concentration</td><td class="num">${fmt.num(m.concentration_hhi, 4)}</td></tr>
            <tr><td class="dim">Regime</td><td>${m.regime || '—'}</td></tr>
          </tbody>
        </table>`;
    }

    refreshPositions(); refreshMetrics();
    client.channel('rt-portfolio')
      .on('postgres_changes', { event: '*', schema:'public', table:'positions' }, refreshPositions)
      .on('postgres_changes', { event: '*', schema:'public', table:'portfolio_metrics' }, refreshMetrics)
      .subscribe();
  },
};
