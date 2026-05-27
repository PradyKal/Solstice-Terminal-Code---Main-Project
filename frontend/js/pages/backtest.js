document.getElementById('shell-top').outerHTML = window.solstice.shellHTML('backtest');
document.getElementById('shell-bottom').outerHTML = window.solstice.footerHTML();
window.solstice.appShell('backtest');

// Wire sliders → labels + recompute
const sliders = [
  ['w-mom','v-mom','w'], ['w-rev','v-rev','w'], ['w-vol','v-vol','w'],
  ['w-trend','v-trend','w'], ['w-rs','v-rs','w'], ['w-flow','v-flow','w'], ['w-reg','v-reg','w'],
  ['r-risk','v-risk','$'], ['r-heat','v-heat','$k'], ['r-conf','v-conf','c'],
];

function fmtSlider(id, val, kind) {
  if (kind === 'w') return (val/100).toFixed(2);
  if (kind === '$') return '$' + val;
  if (kind === '$k') return '$' + val + 'k';
  if (kind === 'c') return (val/100).toFixed(2);
  return val;
}

function getWeights() {
  return {
    mom:  +document.getElementById('w-mom').value / 100,
    rev:  +document.getElementById('w-rev').value / 100,
    vol:  +document.getElementById('w-vol').value / 100,
    trend:+document.getElementById('w-trend').value / 100,
    rs:   +document.getElementById('w-rs').value / 100,
    flow: +document.getElementById('w-flow').value / 100,
    reg:  +document.getElementById('w-reg').value / 100,
  };
}

// Synthetic backtest result generator (uses real signal stats from Supabase as seed)
const client = window.solstice.sb();
let baseStats = null;
(async () => {
  const { data } = await client.from('signals').select('confidence, expected_return, risk_score')
    .order('created_at', { ascending: false }).limit(200);
  if (!data?.length) return;
  const confs = data.map(d => +d.confidence);
  const ers   = data.map(d => +d.expected_return);
  const risks = data.map(d => +d.risk_score);
  baseStats = {
    meanConf: confs.reduce((a,b)=>a+b,0) / confs.length,
    meanER:   ers.reduce((a,b)=>a+b,0) / ers.length,
    meanRisk: risks.reduce((a,b)=>a+b,0) / risks.length,
    stdER:    Math.sqrt(ers.reduce((s,r) => s + Math.pow(r - ers.reduce((a,b)=>a+b,0)/ers.length, 2), 0) / ers.length),
  };
  recompute();
})();

function recompute() {
  // Update slider labels
  sliders.forEach(([sid,lid,kind]) => {
    const v = document.getElementById(sid).value;
    document.getElementById(lid).textContent = fmtSlider(sid, v, kind);
  });
  if (!baseStats) return;

  const w = getWeights();
  const sumW = Object.values(w).reduce((a,b)=>a+b, 0) || 1;
  const norm = Object.fromEntries(Object.entries(w).map(([k,v]) => [k, v/sumW]));
  const minConf = +document.getElementById('r-conf').value / 100;
  const riskPerTrade = +document.getElementById('r-risk').value;
  const heatCap = +document.getElementById('r-heat').value * 1000;

  // Heuristic edge: emphasize momentum + trend, penalize over-allocation to flow (mocked)
  const focusScore =
    norm.mom * 1.2 + norm.trend * 1.15 + norm.rs * 0.9 +
    norm.vol * 0.7 + norm.rev * 0.65 + norm.flow * 0.4 + norm.reg * 0.8;
  // Edge in bps (cycle expected return ~ meanER scaled)
  const baseEdge = baseStats.meanER * focusScore * 10000; // to bps
  const confBoost = Math.max(0, (baseStats.meanConf - minConf) * 80);
  const edgeBps = baseEdge + confBoost;

  // Project Sharpe: edge / vol
  const sharpe = (edgeBps / 100) / Math.max(0.5, baseStats.stdER * 12 * 100);
  // MDD heuristic
  const mdd = -Math.min(0.35, baseStats.meanRisk * (1 + (heatCap / 100000)) * 0.6);

  document.getElementById('o-edge').textContent = edgeBps.toFixed(0) + ' bps';
  document.getElementById('o-edge').className = 'v ' + (edgeBps >= 0 ? 'pos' : 'neg');
  document.getElementById('o-sharpe').textContent = sharpe.toFixed(2);
  document.getElementById('o-sharpe').className = 'v ' + (sharpe >= 0.5 ? 'pos' : sharpe >= 0 ? '' : 'neg');
  document.getElementById('o-mdd').textContent = (mdd * 100).toFixed(2) + '%';
  document.getElementById('o-mdd').className = 'v neg';

  // Equity curves: simulate 4 strategy variants over 252 days
  const days = 252;
  const cumulative = (μ, σ) => {
    const out = [100];
    for (let i = 1; i < days; i++) {
      const ret = μ + σ * (Math.random() * 2 - 1);
      out.push(out[i-1] * (1 + ret/100));
    }
    return out;
  };
  const series = [
    { color: '#06b6d4', pts: cumulative(edgeBps/1000, Math.abs(baseStats.stdER)*100) },
    { color: '#3b82f6', pts: cumulative(edgeBps/1500, Math.abs(baseStats.stdER)*120) },
    { color: '#a855f7', pts: cumulative(edgeBps/1200, Math.abs(baseStats.stdER)*90) },
    { color: '#10b981', pts: cumulative(edgeBps/900,  Math.abs(baseStats.stdER)*110) },
  ];
  window.solstice.viz.equityCurve(document.getElementById('equity-viz'), series);

  // Sensitivity scatter: vary mom weight x risk, plot Sharpe
  const c = document.getElementById('sense-viz');
  c.innerHTML = '';
  const W = c.clientWidth, H = c.clientHeight;
  const svg = d3.select(c).append('svg').attr('width',W).attr('height',H);
  const points = [];
  for (let mw = 0; mw <= 0.6; mw += 0.04) {
    for (let rt = 100; rt <= 2000; rt += 200) {
      const fs = mw * 1.2 + norm.trend * 1.15 + norm.rs * 0.9 + norm.vol * 0.7 + norm.rev * 0.65 + norm.flow * 0.4 + norm.reg * 0.8;
      const e = baseStats.meanER * fs * 10000;
      const s = (e / 100) / Math.max(0.5, baseStats.stdER * 12 * 100);
      points.push({ mw, rt, s });
    }
  }
  const x = d3.scaleLinear().domain([0,0.6]).range([40, W-30]);
  const y = d3.scaleLinear().domain([100,2000]).range([H-30, 30]);
  const color = d3.scaleSequential(d3.interpolateViridis).domain(d3.extent(points, p=>p.s));
  svg.selectAll('rect').data(points).join('rect')
    .attr('x', p => x(p.mw)-2).attr('y', p => y(p.rt)-2)
    .attr('width', 10).attr('height', 14)
    .attr('fill', p => color(p.s));
  svg.append('text').attr('x', W/2).attr('y', H-8).attr('text-anchor','middle')
    .attr('fill','#8089a3').attr('font-size',10).attr('letter-spacing','0.2em').text('MOMENTUM WEIGHT');
  svg.append('text').attr('x', -H/2).attr('y', 14).attr('text-anchor','middle')
    .attr('transform', 'rotate(-90)').attr('fill','#8089a3').attr('font-size',10).attr('letter-spacing','0.2em').text('$ RISK / TRADE');
}

sliders.forEach(([sid]) => document.getElementById(sid).addEventListener('input', recompute));
document.getElementById('run').addEventListener('click', recompute);
