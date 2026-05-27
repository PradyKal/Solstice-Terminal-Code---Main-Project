window.solstice.tabs.logs = {
  async mount() {
    const root = document.getElementById('view-logs');
    root.innerHTML = `
      <div class="panel">
        <div class="panel-h">STREAMING LOGS</div>
        <div class="log-stream" id="log-stream"></div>
      </div>`;
    const stream = document.getElementById('log-stream');
    const client = window.solstice.sb();

    async function refresh() {
      const { data } = await client.from('logs').select('*')
        .order('created_at', { ascending: false }).limit(300);
      stream.innerHTML = (data || []).reverse().map(l => `
        <div class="log-row ${l.level}">
          <span class="ts">${new Date(l.created_at).toISOString().slice(11,19)}</span>
          <span class="lvl">[${(l.level || 'INFO').padEnd(5)}]</span>
          <span class="cmp">${(l.component || '').padEnd(20)}</span>
          ${l.message}
        </div>`).join('');
      stream.scrollTop = stream.scrollHeight;
    }
    refresh();

    function append(row) {
      const div = document.createElement('div');
      div.className = `log-row ${row.level}`;
      div.innerHTML = `
        <span class="ts">${new Date(row.created_at).toISOString().slice(11,19)}</span>
        <span class="lvl">[${(row.level || 'INFO').padEnd(5)}]</span>
        <span class="cmp">${(row.component || '').padEnd(20)}</span>
        ${row.message}`;
      stream.appendChild(div);
      stream.scrollTop = stream.scrollHeight;
    }
    client.channel('rt-logs')
      .on('postgres_changes', { event:'INSERT', schema:'public', table:'logs' }, (p) => append(p.new))
      .subscribe();
  },
};
