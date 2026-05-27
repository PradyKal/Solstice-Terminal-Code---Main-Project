window.solstice.tabs.attribution = {
  async mount() {
    const root = document.getElementById('view-attribution');
    root.innerHTML = `
      <div class="viz-card" id="attr-map" style="height:65vh">
        <div class="viz-title">STRATEGY ATTRIBUTION MAP · per-strategy alpha across top tickers</div>
      </div>`;
    const client = window.solstice.sb();
    async function load() {
      const { data } = await client.from('visualization_data')
        .select('payload').eq('viz_type','signal_map')
        .order('created_at', { ascending: false }).limit(1);
      if (data?.[0]?.payload) {
        window.solstice.viz.render(document.getElementById('attr-map'), 'signal_map', data[0].payload);
      }
    }
    load();
    client.channel('rt-attr')
      .on('postgres_changes', { event:'*', schema:'public', table:'visualization_data' }, load)
      .subscribe();
  },
};
