// Shared app shell — KPIs bar, ticker, footer, particles
window.solstice.appShell = function(activeTab) {
  window.solstice.guard();
  window.solstice.particles(35);

  // Wire nav active state
  document.querySelectorAll('.app-nav a').forEach(a => {
    if (a.dataset.tab === activeTab) a.classList.add('active');
    else a.classList.remove('active');
  });

  const client = window.solstice.sb();
  const fmt = window.solstice.fmt;

  // KPIs in topbar
  async function refreshKPIs() {
    const { data } = await client.from('account_state').select('*')
      .order('created_at', { ascending: false }).limit(1);
    const a = data?.[0];
    if (a) {
      document.getElementById('kpi-equity')?.replaceChildren(document.createTextNode(fmt.usd(a.equity)));
      document.getElementById('kpi-bp')?.replaceChildren(document.createTextNode(fmt.usd(a.buying_power)));
      const positions = Array.isArray(a.open_positions) ? a.open_positions.length : 0;
      document.getElementById('kpi-pos')?.replaceChildren(document.createTextNode(positions));
      const dayPL = (a.open_positions || []).reduce((s,p) => s + (+(p.unrealized_intraday_pl || 0)), 0);
      const el = document.getElementById('kpi-daypl');
      if (el) { el.textContent = fmt.usd(dayPL); el.className = dayPL >= 0 ? 'pos' : 'neg'; }
    }
    const { data: sig } = await client.from('signals').select('regime')
      .order('created_at', { ascending: false }).limit(1);
    if (sig?.[0]) {
      document.getElementById('kpi-regime')?.replaceChildren(
        document.createTextNode((sig[0].regime || '—').toUpperCase()));
    }
  }
  refreshKPIs();

  // Ticker
  async function refreshTicker() {
    const track = document.getElementById('ticker-track');
    if (!track) return;
    const { data } = await client.from('signals')
      .select('ticker, signal, expected_return, price, confidence')
      .order('created_at', { ascending: false }).limit(30);
    if (!data?.length) return;
    const seen = new Set(), items = [];
    for (const s of data) {
      if (seen.has(s.ticker)) continue;
      seen.add(s.ticker); items.push(s);
      if (items.length >= 18) break;
    }
    const html = items.map(s => {
      const dir = s.signal === 'BUY' ? 'pos' : s.signal === 'SELL' ? 'neg' : '';
      const er = ((+s.expected_return || 0) * 100).toFixed(2);
      return `<span class="item"><span class="t">${s.ticker}</span><span class="v">$${(+s.price).toFixed(2)}</span><span class="c ${dir}">${er}%</span></span>`;
    }).join('');
    track.innerHTML = html + html;
  }
  refreshTicker();

  // Footer counts
  async function refreshFooter() {
    const [sig, sim, trd, log] = await Promise.all([
      client.from('signals').select('id', { count:'exact', head:true }),
      client.from('simulations').select('id', { count:'exact', head:true }),
      client.from('trades').select('id', { count:'exact', head:true }),
      client.from('logs').select('created_at').order('created_at',{ascending:false}).limit(1),
    ]);
    const cnts = document.getElementById('footer-counts');
    if (cnts) cnts.textContent = `signals ${sig.count ?? 0} · sims ${sim.count ?? 0} · trades ${trd.count ?? 0}`;
    const lc = document.getElementById('footer-lastcycle');
    if (lc && log.data?.[0]) {
      const m = Math.floor((Date.now() - new Date(log.data[0].created_at).getTime()) / 60000);
      lc.textContent = `last cycle ${m < 1 ? '<1' : m}m ago`;
    }
  }
  refreshFooter();

  // Clocks
  const cET = document.getElementById('clk-et'), cUTC = document.getElementById('clk-utc');
  if (cET || cUTC) setInterval(() => {
    const d = new Date();
    if (cET) cET.textContent = d.toLocaleTimeString('en-US', { hour12:false, timeZone:'America/New_York' }) + ' ET';
    if (cUTC) cUTC.textContent = d.toUTCString().split(' ')[4] + ' UTC';
  }, 1000);

  // User badge
  const u = document.getElementById('footer-user');
  if (u) u.textContent = (sessionStorage.getItem('solstice_user') || '—').toUpperCase();

  // Realtime
  client.channel('rt-shell')
    .on('postgres_changes', { event:'*', schema:'public', table:'account_state' }, refreshKPIs)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals' }, () => { refreshKPIs(); refreshTicker(); refreshFooter(); })
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'simulations' }, refreshFooter)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'trades' }, refreshFooter)
    .subscribe();
  setInterval(refreshFooter, 30_000);

  // Logout
  document.querySelectorAll('.app-exit').forEach(a => a.addEventListener('click', () => sessionStorage.clear()));
};

// Shared HTML for the app shell — inject into pages
window.solstice.shellHTML = function(active) {
  return `
  <header class="app-bar">
    <div class="app-logo">SOLSTICE</div>
    <nav class="app-nav">
      <a href="research.html"  data-tab="research">RESEARCH</a>
      <a href="analysis.html"  data-tab="analysis">ANALYSIS</a>
      <a href="portfolio.html" data-tab="portfolio">PORTFOLIO</a>
      <a href="backtest.html"  data-tab="backtest">BACKTEST</a>
    </nav>
    <div class="app-kpis">
      <div class="app-kpi"><span>EQUITY</span><b id="kpi-equity">—</b></div>
      <div class="app-kpi"><span>DAY P&L</span><b id="kpi-daypl">—</b></div>
      <div class="app-kpi"><span>BP</span><b id="kpi-bp">—</b></div>
      <div class="app-kpi"><span>POS</span><b id="kpi-pos">—</b></div>
      <div class="app-kpi"><span>REGIME</span><b id="kpi-regime">—</b></div>
    </div>
    <div class="app-user">
      <span class="app-dot"></span>
      <span id="clk-et">—</span>
      <a href="index.html" class="app-exit">EXIT</a>
    </div>
  </header>
  <div class="app-ticker">
    <div class="label">LIVE SIGNAL FEED</div>
    <div class="track" id="ticker-track">—</div>
  </div>
  `;
};

window.solstice.footerHTML = function() {
  return `
  <footer class="app-footer">
    <span class="conn up"><span class="d"></span>SUPABASE</span>
    <span class="conn up"><span class="d"></span>ALPACA</span>
    <span class="conn up"><span class="d"></span>ENGINE</span>
    <span class="muted">|</span>
    <span id="footer-lastcycle">—</span>
    <span class="muted">|</span>
    <span id="footer-counts">—</span>
    <div class="right">
      <span id="clk-utc">—</span>
      <span>v5.0</span>
      <span id="footer-user">—</span>
    </div>
  </footer>
  `;
};
