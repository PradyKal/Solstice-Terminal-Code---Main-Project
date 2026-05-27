document.getElementById('shell-top').outerHTML = window.solstice.shellHTML('analysis');
document.getElementById('shell-bottom').outerHTML = window.solstice.footerHTML();
window.solstice.appShell('analysis');

const client = window.solstice.sb();
const fmt = window.solstice.fmt;

const input = document.getElementById('ticker-input');
const btn = document.getElementById('ticker-load');
const empty = document.getElementById('analysis-empty');
const content = document.getElementById('analysis-content');

async function loadTicker(t) {
  t = (t || '').trim().toUpperCase();
  if (!t) return;
  empty.style.display = 'none';
  content.style.display = 'block';
  document.getElementById('snap-ticker').textContent = t;

  // Latest signal -> feature grid
  const { data: sigData } = await client.from('signals').select('*')
    .eq('ticker', t).order('created_at', { ascending: false }).limit(20);
  const latest = sigData?.[0];
  const fg = document.getElementById('feature-grid');
  if (latest) {
    const conf = +latest.confidence, er = +latest.expected_return * 100, risk = +latest.risk_score;
    fg.innerHTML = `
      <div class="stat-card"><div class="l">PRICE</div><div class="v cyan">$${(+latest.price).toFixed(2)}</div></div>
      <div class="stat-card"><div class="l">SIGNAL</div><div class="v ${latest.signal==='BUY'?'pos':latest.signal==='SELL'?'neg':''}">${latest.signal}</div></div>
      <div class="stat-card"><div class="l">CONFIDENCE</div><div class="v">${conf.toFixed(3)}</div></div>
      <div class="stat-card"><div class="l">EXPECTED RETURN</div><div class="v ${er>=0?'pos':'neg'}">${er.toFixed(2)}%</div></div>
      <div class="stat-card"><div class="l">RISK SCORE</div><div class="v">${risk.toFixed(3)}</div></div>
      <div class="stat-card"><div class="l">REGIME</div><div class="v" style="font-size: 18px;">${(latest.regime || '—').toUpperCase()}</div></div>`;
  } else {
    fg.innerHTML = '<div class="empty col-3" style="grid-column: span 6;">NO SIGNAL HISTORY FOR ' + t + '</div>';
  }

  // Signal history table
  const tb = document.getElementById('hist-tbody');
  document.getElementById('hist-count').textContent = (sigData?.length || 0) + ' RECORDS';
  if (sigData?.length) {
    tb.innerHTML = sigData.map(s => {
      const e = (+s.expected_return * 100);
      return `<tr>
        <td class="dim">${fmt.time(s.created_at)}</td>
        <td><span class="pill ${s.signal==='BUY'?'buy':s.signal==='SELL'?'sell':'hold'}">${s.signal}</span></td>
        <td class="num cyan">${(+s.confidence).toFixed(3)}</td>
        <td class="num ${e>=0?'pos':'neg'}">${e>=0?'+':''}${e.toFixed(2)}%</td>
        <td class="num">${(+s.risk_score).toFixed(3)}</td>
        <td class="num bold">$${(+s.price).toFixed(2)}</td>
        <td class="dim">${s.regime || '—'}</td>
        <td class="dim mono" style="font-size: 10px;">${(s.rationale || '').slice(0,80)}</td>
      </tr>`;
    }).join('');
  } else {
    tb.innerHTML = '<tr><td colspan="8"><div class="empty">NO HISTORY</div></td></tr>';
  }

  // Viz: MC + Vol + PDF + Skew (filtered by ticker)
  async function loadVizForTicker(type, containerId) {
    const c = document.getElementById(containerId);
    const { data } = await client.from('visualization_data')
      .select('payload').eq('viz_type', type).eq('ticker', t)
      .order('created_at', { ascending: false }).limit(1);
    if (data?.[0]?.payload) {
      window.solstice.viz.render(c, type, data[0].payload);
    } else {
      // Fallback: any ticker's payload of that type
      const { data: any } = await client.from('visualization_data')
        .select('payload').eq('viz_type', type)
        .order('created_at', { ascending: false }).limit(1);
      if (any?.[0]?.payload) window.solstice.viz.render(c, type, any[0].payload);
      else c.innerHTML = `<div class="empty">NO ${type.toUpperCase()}</div>`;
    }
  }
  loadVizForTicker('mc_path_cloud', 'viz-mc');
  loadVizForTicker('vol_surface_3d', 'viz-vol');
  loadVizForTicker('pdf_mesh', 'viz-pdf');
  loadVizForTicker('iv_skew_term_structure', 'viz-skew');
}

btn.addEventListener('click', () => loadTicker(input.value));
input.addEventListener('keydown', (e) => { if (e.key === 'Enter') loadTicker(input.value); });
document.querySelectorAll('a[data-q]').forEach(a => a.addEventListener('click', (e) => {
  e.preventDefault();
  input.value = a.dataset.q;
  loadTicker(a.dataset.q);
}));
