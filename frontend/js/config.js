/* Supabase client + helpers — exposed on window.solstice */
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
  usd: (n) => {
    if (n === null || n === undefined || Number.isNaN(+n)) return '—';
    const v = +n;
    if (Math.abs(v) >= 1e6) return '$' + (v/1e6).toFixed(2) + 'M';
    if (Math.abs(v) >= 1e3) return '$' + (v/1e3).toFixed(2) + 'k';
    return '$' + v.toFixed(2);
  },
  pct: (n) => (n === null || n === undefined || Number.isNaN(+n)) ? '—' : (+n*100).toFixed(2) + '%',
  num: (n, d=4) => (n === null || n === undefined || Number.isNaN(+n)) ? '—' : (+n).toFixed(d),
  time: (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false });
  },
};

window.solstice.guard = () => {
  if (sessionStorage.getItem('solstice_user') !== 'Prady0901') {
    window.location.replace('login.html');
  }
};
