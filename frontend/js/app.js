// App bootstrap: auth guard, KPI bar, ticker, heartbeat, clock, command bar, router

window.solstice.guard();

(async () => {
  const client = window.solstice.sb();
  const fmt = window.solstice.fmt;

  // ─── KPI BAR ────────────────────────────────────────────────
  async function refreshKPIs() {
    const { data } = await client.from('account_state').select('*')
      .order('created_at', { ascending: false }).limit(1);
    const a = (data || [])[0];
    if (a) {
      document.getElementById('kpi-equity').textContent = fmt.usd(a.equity);
      document.getElementById('kpi-bp').textContent = fmt.usd(a.buying_power);
      document.getElementById('kpi-cash').textContent = fmt.usd(a.cash);
      const orders = Array.isArray(a.open_orders) ? a.open_orders.length : 0;
      const positions = Array.isArray(a.open_positions) ? a.open_positions.length : 0;
      document.getElementById('kpi-orders').textContent = orders;
      document.getElementById('kpi-positions').textContent = positions;

      // Day P&L from open positions
      const dayPL = (a.open_positions || []).reduce((s, p) =>
        s + (+(p.unrealized_intraday_pl || 0)), 0);
      const el = document.getElementById('kpi-daypl');
      el.textContent = fmt.usd(dayPL);
      el.className = dayPL >= 0 ? 'pos' : 'neg';
    }
    const { data: sig } = await client.from('signals')
      .select('regime, volatility').order('created_at', { ascending: false }).limit(1);
    if (sig?.[0]) {
      document.getElementById('kpi-regime').textContent = (sig[0].regime || '—').toUpperCase();
      if (sig[0].volatility) {
        document.getElementById('kpi-vix').textContent = (+sig[0].volatility * 100).toFixed(1);
      }
    }
  }

  // ─── TICKER ─────────────────────────────────────────────────
  async function refreshTicker() {
    const { data } = await client.from('signals')
      .select('ticker, signal, confidence, expected_return, price')
      .order('created_at', { ascending: false }).limit(40);
    if (!data || !data.length) return;
    // Deduplicate by ticker, take latest
    const seen = new Set();
    const items = [];
    for (const s of data) {
      if (seen.has(s.ticker)) continue;
      seen.add(s.ticker);
      items.push(s);
      if (items.length >= 20) break;
    }
    const html = items.map(s => {
      const dir = s.signal === 'BUY' ? 'pos' : (s.signal === 'SELL' ? 'neg' : '');
      const er = ((+s.expected_return || 0) * 100).toFixed(2);
      return `<span class="ticker-item">
        <span class="t">${s.ticker}</span>
        <span class="v">$${(+s.price || 0).toFixed(2)}</span>
        <span class="c ${dir}">${er}%</span>
        <span class="v">conf ${(+s.confidence).toFixed(2)}</span>
      </span>`;
    }).join('');
    // Duplicate for seamless scroll
    document.getElementById('ticker-track').innerHTML = html + html;
  }

  // ─── FOOTER COUNTS ─────────────────────────────────────────
  async function refreshFooter() {
    const [sig, sim, trd, log] = await Promise.all([
      client.from('signals').select('id', { count: 'exact', head: true }),
      client.from('simulations').select('id', { count: 'exact', head: true }),
      client.from('trades').select('id', { count: 'exact', head: true }),
      client.from('logs').select('created_at').order('created_at', { ascending: false }).limit(1),
    ]);
    document.getElementById('footer-counts').textContent =
      `signals ${sig.count ?? 0} · sims ${sim.count ?? 0} · trades ${trd.count ?? 0}`;
    if (log.data?.[0]) {
      const d = new Date(log.data[0].created_at);
      const min = Math.floor((Date.now() - d.getTime()) / 60000);
      document.getElementById('footer-lastcycle').textContent =
        `last cycle ${min < 1 ? '< 1' : min}m ago`;
    }
  }

  refreshKPIs(); refreshTicker(); refreshFooter();

  // Realtime
  client.channel('rt-header')
    .on('postgres_changes', { event:'*', schema:'public', table:'account_state' }, refreshKPIs)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals' }, () => {
      refreshKPIs(); refreshTicker(); refreshFooter();
    })
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'simulations' }, refreshFooter)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'trades' }, refreshFooter)
    .subscribe();
  setInterval(refreshFooter, 30_000);

  // ─── ENGINE HEARTBEAT ──────────────────────────────────────
  const dot = document.getElementById('engine-dot');
  const label = document.getElementById('engine-label');
  const connEngine = document.getElementById('conn-engine');
  const connAlpaca = document.getElementById('conn-alpaca');
  let lastHeartbeat = 0;
  function markAlive() {
    lastHeartbeat = Date.now();
    dot.classList.add('live');
    label.textContent = 'ENGINE LIVE';
    connEngine.className = 'footer-conn up';
  }
  function check() {
    if (Date.now() - lastHeartbeat > window.solstice.config.HEARTBEAT_TIMEOUT_MS) {
      dot.classList.remove('live');
      label.textContent = 'AWAITING';
      connEngine.className = 'footer-conn';
    }
  }
  client.from('logs').select('created_at')
    .order('created_at', { ascending: false }).limit(1).then(({ data }) => {
      if (data?.[0]) {
        const age = Date.now() - new Date(data[0].created_at).getTime();
        if (age < window.solstice.config.HEARTBEAT_TIMEOUT_MS) markAlive();
      }
    });
  // Account state freshness implies Alpaca is reachable
  client.from('account_state').select('created_at')
    .order('created_at', { ascending: false }).limit(1).then(({ data }) => {
      if (data?.[0]) {
        const age = Date.now() - new Date(data[0].created_at).getTime();
        if (age < 30 * 60_000) connAlpaca.className = 'footer-conn up';
      }
    });
  client.channel('rt-heartbeat')
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'logs' }, markAlive)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals' }, markAlive)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'account_state' }, () => {
      connAlpaca.className = 'footer-conn up';
    })
    .subscribe();
  setInterval(check, 5000);

  // ─── CLOCKS ─────────────────────────────────────────────────
  const clkET = document.getElementById('clock-et');
  const clkUTC = document.getElementById('clock-utc');
  setInterval(() => {
    const d = new Date();
    clkET.textContent = d.toLocaleTimeString('en-US',
      { hour12: false, timeZone: 'America/New_York' }) + ' ET';
    clkUTC.textContent = d.toUTCString().split(' ')[4] + ' UTC';
  }, 1000);

  // ─── COMMAND BAR (⌘K / Ctrl+K) ─────────────────────────────
  const cmdbar = document.getElementById('cmdbar');
  const cmdInput = document.getElementById('cmdbar-input');
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      cmdbar.classList.toggle('open');
      if (cmdbar.classList.contains('open')) cmdInput.focus();
    } else if (e.key === 'Escape') {
      cmdbar.classList.remove('open');
    } else if (cmdbar.classList.contains('open') === false &&
               !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) {
      // Number key tab switching
      const keys = { '1':'analyze','2':'models','3':'simulations','4':'regime','5':'attribution',
                     '6':'trades','7':'portfolio','8':'risk','9':'engine','0':'logs' };
      if (keys[e.key]) location.hash = '#' + keys[e.key];
    }
  });
  cmdInput?.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const q = cmdInput.value.trim().toLowerCase();
    if (!q) return;
    const tabKeys = ['analyze','portfolio','trades','models','simulations','risk','regime','attribution','engine','logs'];
    const hit = tabKeys.find(t => t.startsWith(q));
    if (hit) {
      location.hash = '#' + hit;
      cmdbar.classList.remove('open');
      cmdInput.value = '';
    }
  });

  // ─── USER ──────────────────────────────────────────────────
  document.getElementById('footer-user').textContent =
    (sessionStorage.getItem('solstice_user') || '—').toUpperCase();

  // ─── ROUTER ────────────────────────────────────────────────
  window.solstice.router.init();

  // Logout clears session
  document.querySelector('.logout').addEventListener('click', () => sessionStorage.clear());
})();
