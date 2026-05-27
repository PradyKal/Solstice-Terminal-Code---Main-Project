document.getElementById('shell-top').outerHTML = window.solstice.shellHTML('portfolio');
document.getElementById('shell-bottom').outerHTML = window.solstice.footerHTML();
window.solstice.appShell('portfolio');

const client = window.solstice.sb();
const fmt = window.solstice.fmt;

async function refresh() {
  // Account state -> stat cards
  const { data: a } = await client.from('account_state').select('*')
    .order('created_at', { ascending: false }).limit(1);
  const acc = a?.[0];
  if (acc) {
    document.getElementById('s-equity').textContent = fmt.usd(acc.equity);
    const dayPL = (acc.open_positions || []).reduce((s,p) => s + (+(p.unrealized_intraday_pl || 0)), 0);
    const el = document.getElementById('s-daypl');
    el.textContent = fmt.usd(dayPL);
    el.className = 'v ' + (dayPL >= 0 ? 'pos' : 'neg');
    const dayPLPct = acc.equity ? (dayPL / acc.equity * 100) : 0;
    document.getElementById('s-daypl-pct').textContent = (dayPLPct >= 0 ? '+' : '') + dayPLPct.toFixed(2) + '%';
    document.getElementById('s-bp').textContent = fmt.usd(acc.buying_power);
    document.getElementById('s-cash').textContent = 'CASH ' + fmt.usd(acc.cash);
  }
  // Portfolio metrics
  const { data: pm } = await client.from('portfolio_metrics').select('*')
    .order('created_at', { ascending: false }).limit(1);
  const m = pm?.[0];
  if (m) {
    document.getElementById('s-sharpe').textContent = fmt.num(m.rolling_sharpe, 2);
    document.getElementById('s-mdd').textContent = 'MDD ' + fmt.pct(m.max_drawdown);
    document.getElementById('pm-body').innerHTML = `
      <table class="dt">
        <tbody>
          <tr><td class="dim">Gross Exposure</td><td class="num bold">${fmt.usd(m.gross_exposure)}</td></tr>
          <tr><td class="dim">Net Exposure</td><td class="num bold">${fmt.usd(m.net_exposure)}</td></tr>
          <tr><td class="dim">Unrealized PnL</td><td class="num ${(+m.unrealized_pnl||0)>=0?'pos':'neg'}">${fmt.usd(m.unrealized_pnl)}</td></tr>
          <tr><td class="dim">Realized PnL</td><td class="num ${(+m.realized_pnl||0)>=0?'pos':'neg'}">${fmt.usd(m.realized_pnl)}</td></tr>
          <tr><td class="dim">Rolling Sortino</td><td class="num">${fmt.num(m.rolling_sortino, 2)}</td></tr>
          <tr><td class="dim">Beta vs SPY</td><td class="num">${fmt.num(m.beta_spy, 2)}</td></tr>
          <tr><td class="dim">HHI Concentration</td><td class="num">${fmt.num(m.concentration_hhi, 4)}</td></tr>
          <tr><td class="dim">Market Regime</td><td class="bold cyan">${m.regime || '—'}</td></tr>
        </tbody>
      </table>`;
  }

  // Positions
  const { data: pos } = await client.from('positions').select('*')
    .order('updated_at', { ascending: false });
  document.getElementById('pos-count').textContent = (pos?.length || 0) + ' POSITIONS';
  const tb = document.getElementById('pos-tbody');
  if (!pos?.length) {
    tb.innerHTML = '<tr><td colspan="7"><div class="empty">NO OPEN POSITIONS</div></td></tr>';
    document.getElementById('donut').innerHTML = '<div class="empty">AWAITING POSITIONS</div>';
  } else {
    const total = pos.reduce((s,p) => s + Math.abs(+p.qty * +p.mark_price), 0);
    tb.innerHTML = pos.map(p => {
      const mv = +p.qty * +p.mark_price;
      const pct = total ? (Math.abs(mv) / total * 100) : 0;
      const upl = +p.unrealized_pnl || 0;
      return `<tr>
        <td class="bold">${p.ticker}</td>
        <td class="num">${(+p.qty).toFixed(4)}</td>
        <td class="num">${fmt.usd(p.avg_entry)}</td>
        <td class="num">${fmt.usd(p.mark_price)}</td>
        <td class="num">${fmt.usd(mv)}</td>
        <td class="num ${upl>=0?'pos':'neg'}">${fmt.usd(upl)}</td>
        <td class="num cyan">${pct.toFixed(1)}%</td>
      </tr>`;
    }).join('');
    // Donut data
    window.solstice.viz.donut(document.getElementById('donut'),
      pos.map(p => ({ name: p.ticker, value: Math.abs(+p.qty * +p.mark_price) })));
  }

  // Recent trades
  const { data: trd } = await client.from('trades').select('*')
    .order('created_at', { ascending: false }).limit(40);
  document.getElementById('trd-count').textContent = (trd?.length || 0) + ' EXECUTIONS';
  const ttb = document.getElementById('trd-tbody');
  if (!trd?.length) {
    ttb.innerHTML = '<tr><td colspan="7"><div class="empty">NO TRADES</div></td></tr>';
  } else {
    ttb.innerHTML = trd.map(t => `<tr>
      <td class="dim">${fmt.time(t.created_at)}</td>
      <td class="bold">${t.ticker}</td>
      <td><span class="pill ${t.side==='BUY'?'buy':'sell'}">${t.side}</span></td>
      <td class="num">${(+t.qty).toFixed(4)}</td>
      <td class="num">${fmt.usd(t.entry_price)}</td>
      <td class="dim">${t.status || '—'}</td>
      <td class="num">${t.confidence ? (+t.confidence).toFixed(3) : '—'}</td>
    </tr>`).join('');
  }
}
refresh();

client.channel('rt-portfolio')
  .on('postgres_changes', { event:'*', schema:'public', table:'account_state' }, refresh)
  .on('postgres_changes', { event:'*', schema:'public', table:'positions' }, refresh)
  .on('postgres_changes', { event:'*', schema:'public', table:'trades' }, refresh)
  .on('postgres_changes', { event:'INSERT', schema:'public', table:'portfolio_metrics' }, refresh)
  .subscribe();
