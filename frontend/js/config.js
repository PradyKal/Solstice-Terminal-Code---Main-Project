// Supabase client + helpers
window.solstice = window.solstice || {};

window.solstice.config = {
  SUPABASE_URL: 'https://roogtwurdmsdapgvaspk.supabase.co',
  SUPABASE_ANON: 'sb_publishable_H2NwQKatFKUfH02dmCP32A_XuXpXykZ',
  HEARTBEAT_TIMEOUT_MS: 90_000,
};

window.solstice.sb = () => {
  if (!window.solstice._client) {
    window.solstice._client = window.supabase.createClient(
      window.solstice.config.SUPABASE_URL,
      window.solstice.config.SUPABASE_ANON,
      { realtime: { params: { eventsPerSecond: 10 } } }
    );
  }
  return window.solstice._client;
};

window.solstice.fmt = {
  usd: (n, d=2) => {
    if (n == null || Number.isNaN(+n)) return '—';
    const v = +n;
    if (Math.abs(v) >= 1e9) return '$' + (v/1e9).toFixed(2) + 'B';
    if (Math.abs(v) >= 1e6) return '$' + (v/1e6).toFixed(2) + 'M';
    if (Math.abs(v) >= 1e3) return '$' + (v/1e3).toFixed(2) + 'k';
    return '$' + v.toFixed(d);
  },
  pct: (n, d=2) => (n == null || Number.isNaN(+n)) ? '—' : (+n*100).toFixed(d) + '%',
  num: (n, d=4) => (n == null || Number.isNaN(+n)) ? '—' : (+n).toFixed(d),
  int: (n) => (n == null || Number.isNaN(+n)) ? '—' : Math.round(+n).toLocaleString(),
  time: (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString('en-US', { hour12: false });
  },
};

window.solstice.guard = () => {
  if (sessionStorage.getItem('solstice_user') !== 'Prady0901') {
    window.location.replace('login.html');
  }
};

// Drop floating-particle DOM into the page
window.solstice.particles = (n = 30) => {
  const root = document.createElement('div');
  root.className = 'hud-particles';
  for (let i = 0; i < n; i++) {
    const s = document.createElement('span');
    s.style.left = (Math.random() * 100) + 'vw';
    s.style.top = (50 + Math.random() * 100) + 'vh';
    s.style.animationDelay = (Math.random() * 22) + 's';
    s.style.animationDuration = (16 + Math.random() * 18) + 's';
    s.style.opacity = (0.15 + Math.random() * 0.5).toFixed(2);
    root.appendChild(s);
  }
  document.body.appendChild(root);

  const grid = document.createElement('div');
  grid.className = 'hud-grid';
  document.body.appendChild(grid);
};
