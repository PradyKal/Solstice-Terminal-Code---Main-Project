window.solstice.tabs.logs = {
  async mount() {
    const root = document.getElementById('view-logs');
    root.innerHTML = `
      <div class="view-header">
        <div class="view-title">LOGS</div>
        <div class="view-sub">streaming · realtime INSERT subscription</div>
      </div>
      <div class="panel">
        <div class="panel-h">
          <span>SYSTEM LOG STREAM</span>
          <span class="badge" id="log-cnt">0</span>
        </div>
        <div class="log-stream" id="log-stream"></div>
      </div>`;
    const stream = document.getElementById('log-stream');
    const cnt = document.getElementById('log-cnt');
    const client = window.solstice.sb();

    async function refresh() {
      const { data } = await client.from('logs').select('*')
        .order('created_at', { ascending: false }).limit(300);
      stream.innerHTML = (data || []).reverse().map(l => `
        <div class="log-row ${l.level}">
          <span class="ts">${new Date(l.created_at).toISOString().slice(11,19)}</span>
          <span class="lvl">[${(l.level || 'INFO').padEnd(5)}]</span>
          <span class="cmp">${(l.component || '').padEnd(20).slice(0,20)}</span>
          ${l.message}
        </div>`).join('');
      cnt.textContent = (data?.length || 0) + ' LINES';
      stream.scrollTop = stream.scrollHeight;
    }
    refresh();

    client.channel('rt-logs')
      .on('postgres_changes', { event:'INSERT', schema:'public', table:'logs' }, (p) => {
        const l = p.new;
        const div = document.createElement('div');
        div.className = `log-row ${l.level}`;
        div.innerHTML = `
          <span class="ts">${new Date(l.created_at).toISOString().slice(11,19)}</span>
          <span class="lvl">[${(l.level || 'INFO').padEnd(5)}]</span>
          <span class="cmp">${(l.component || '').padEnd(20).slice(0,20)}</span>
          ${l.message}`;
        stream.appendChild(div);
        stream.scrollTop = stream.scrollHeight;
        cnt.textContent = (parseInt(cnt.textContent) + 1) + ' LINES';
      })
      .subscribe();
  },
};
