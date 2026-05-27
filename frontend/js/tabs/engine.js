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
      ['iv_skew_term_structure',   'IV SKEW TERM STRUCTURE'],
      ['portfolio_greeks',         'PORTFOLIO GREEKS'],
      ['signal_map',               'SIGNAL MAP'],
    ];
    root.innerHTML = `<div class="grid cols-2">` +
      vizTypes.map(([t, label]) => `
        <div class="viz-card" id="viz-${t}" style="height:42vh">
          <div class="viz-title">${label}</div>
        </div>`).join('') +
      `</div>`;

    const client = window.solstice.sb();
    async function loadOne(vizType) {
      const { data } = await client.from('visualization_data')
        .select('payload').eq('viz_type', vizType)
        .order('created_at', { ascending: false }).limit(1);
      const el = document.getElementById('viz-' + vizType);
      if (!el) return;
      if (data?.[0]?.payload) {
        window.solstice.viz.render(el, vizType, data[0].payload);
      } else {
        el.innerHTML += `<div class="empty">NO ${vizType} PAYLOAD YET</div>`;
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
