// App bootstrap: auth guard, header KPIs, engine heartbeat, clock, router init
window.solstice.guard();

(async () => {
  const client = window.solstice.sb();
  const fmt = window.solstice.fmt;

  // -- Header KPIs from account_state --
  async function refreshKPIs() {
    const { data } = await client.from('account_state').select('*')
      .order('created_at', { ascending: false }).limit(1);
    const a = (data || [])[0];
    if (a) {
      document.getElementById('kpi-equity').textContent     = fmt.usd(a.equity);
      document.getElementById('kpi-bp').textContent         = fmt.usd(a.buying_power);
      document.getElementById('kpi-cash').textContent       = fmt.usd(a.cash);
      const orders = Array.isArray(a.open_orders) ? a.open_orders.length : 0;
      document.getElementById('kpi-orders').textContent     = orders;
    }
    const { data: sig } = await client.from('signals').select('regime')
      .order('created_at', { ascending: false }).limit(1);
    if (sig?.[0]) document.getElementById('kpi-regime').textContent = sig[0].regime || '—';
  }
  refreshKPIs();
  client.channel('rt-header')
    .on('postgres_changes', { event:'*', schema:'public', table:'account_state' }, refreshKPIs)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals' }, refreshKPIs)
    .subscribe();

  // -- Engine heartbeat: any insert into logs within 90s = engine alive --
  const dot = document.getElementById('engine-dot');
  const label = document.getElementById('engine-label');
  let lastHeartbeat = 0;
  function markAlive() {
    lastHeartbeat = Date.now();
    dot.classList.add('live');
    label.textContent = 'ENGINE LIVE';
  }
  function check() {
    if (Date.now() - lastHeartbeat > window.solstice.config.HEARTBEAT_TIMEOUT_MS) {
      dot.classList.remove('live');
      label.textContent = 'AWAITING';
    }
  }
  // Seed from latest log
  client.from('logs').select('created_at')
    .order('created_at', { ascending: false }).limit(1).then(({ data }) => {
      if (data?.[0]) {
        const age = Date.now() - new Date(data[0].created_at).getTime();
        if (age < window.solstice.config.HEARTBEAT_TIMEOUT_MS) markAlive();
      }
    });
  client.channel('rt-heartbeat')
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'logs' }, markAlive)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals' }, markAlive)
    .subscribe();
  setInterval(check, 5000);

  // -- Clock --
  const clk = document.getElementById('clock');
  setInterval(() => {
    const d = new Date();
    clk.textContent = d.toLocaleTimeString('en-US', { hour12:false, timeZone:'America/New_York' }) + ' ET';
  }, 1000);

  // -- Router --
  window.solstice.router.init();

  // Logout
  document.querySelector('.logout').addEventListener('click', (e) => {
    sessionStorage.clear();
  });
})();
