window.solstice.tabs.regime = {
  async mount() {
    const root = document.getElementById('view-regime');
    root.innerHTML = `
      <div class="panel">
        <div class="panel-h">MARKET REGIME · ROLLING CLASSIFIER</div>
        <div class="panel-body" id="regime-body">
          <div class="empty">AWAITING GUMLOOP</div>
        </div>
      </div>`;
    const client = window.solstice.sb();
    async function refresh() {
      const { data } = await client.from('signals').select('regime, created_at')
        .order('created_at', { ascending: false }).limit(200);
      if (!data || !data.length) return;
      const series = [];
      const seen = new Set();
      data.reverse().forEach(r => {
        const key = r.regime + '|' + r.created_at.slice(0,10);
        if (seen.has(key)) return;
        seen.add(key);
        series.push({ ts: r.created_at, regime: r.regime });
      });
      const body = document.getElementById('regime-body');
      body.innerHTML = '<table class="dt"><thead><tr><th>TIME</th><th>REGIME</th></tr></thead><tbody>' +
        series.slice(-50).map(s => `
          <tr><td class="dim">${new Date(s.ts).toLocaleString()}</td><td>${s.regime}</td></tr>
        `).join('') + '</tbody></table>';
    }
    refresh();
    client.channel('rt-regime')
      .on('postgres_changes', { event:'INSERT', schema:'public', table:'signals' }, refresh)
      .subscribe();
  },
};
