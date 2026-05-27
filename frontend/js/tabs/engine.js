window.solstice.tabs.engine = {
  async mount() {
    const root = document.getElementById('view-engine');
    const vizTypes = [
      ['vol_surface_3d',           'IMPLIED VOL SURFACE 3D'],
      ['mc_path_cloud',            'MONTE CARLO PATH CLOUD'],
      ['pca_factor_decomposition', 'PCA FACTOR DECOMPOSITION'],
      ['covariance_heatmap',       'COVARIANCE HEATMAP'],
      ['correlation_network',      'CORRELATION NETWORK'],
      ['liquidity_heatmap',        'LIQUIDITY HEATMAP'],
      ['risk_topology',            'RISK TOPOLOGY'],
      ['iv_skew_term_structure',   'IV SKEW · TERM STRUCTURE'],
      ['portfolio_greeks',         'PORTFOLIO GREEKS'],
      ['signal_map',               'STRATEGY × TICKER SIGNAL MAP'],
    ];
    root.innerHTML = `
      <div class="view-header">
        <div class="view-title">ENGINE VIEW</div>
        <div class="view-sub">all visualization payloads · auto-refresh on insert</div>
      </div>
      <div class="grid cols-2">` +
      vizTypes.map(([t, label]) => `
        <div class="viz-card" style="height:42vh" id="viz-${t}">
          <div class="viz-title">${label}</div>
          <div class="viz-meta" id="vm-${t}">—</div>
        </div>`).join('') +
      `</div>`;

    const client = window.solstice.sb();
    async function loadOne(vizType) {
      const { data } = await client.from('visualization_data')
        .select('payload, created_at, ticker').eq('viz_type', vizType)
        .order('created_at', { ascending: false }).limit(1);
      const el = document.getElementById('viz-' + vizType);
      const meta = document.getElementById('vm-' + vizType);
      if (!el) return;
      // Preserve title/meta children
      const titleEl = el.querySelector('.viz-title');
      const metaEl = el.querySelector('.viz-meta');
      if (data?.[0]?.payload) {
        // Clear except title/meta
        Array.from(el.children).forEach(c => {
          if (c !== titleEl && c !== metaEl) el.removeChild(c);
        });
        const wrap = document.createElement('div');
        wrap.style.position = 'absolute';
        wrap.style.inset = '0';
        el.appendChild(wrap);
        window.solstice.viz.render(wrap, vizType, data[0].payload);
        if (meta) {
          const t = data[0].ticker || 'aggregate';
          meta.textContent = `${t} · ${new Date(data[0].created_at).toLocaleTimeString('en-US',{hour12:false})}`;
        }
      } else {
        if (!el.querySelector('.empty')) {
          const empty = document.createElement('div');
          empty.className = 'empty';
          empty.textContent = `NO ${vizType} YET`;
          empty.style.position = 'absolute'; empty.style.inset = '0';
          empty.style.display = 'flex'; empty.style.alignItems = 'center'; empty.style.justifyContent = 'center';
          el.appendChild(empty);
        }
      }
    }
    vizTypes.forEach(([t]) => loadOne(t));

    client.channel('rt-engine')
      .on('postgres_changes', { event:'*', schema:'public', table:'visualization_data' }, (payload) => {
        const vt = payload.new?.viz_type;
        if (vt) loadOne(vt);
      })
      .subscribe();
  },
};
