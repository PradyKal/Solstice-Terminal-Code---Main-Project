// Advanced visualization renderers — HUD-styled, Iron Man feel
window.solstice.viz = (() => {
  const CYAN = 0x06b6d4, BLUE = 0x3b82f6, PURPLE = 0xa855f7, GREEN = 0x10b981, RED = 0xef4444;

  function clear(c) { c.innerHTML = ''; }

  function makeScene(container) {
    const w = container.clientWidth || 480, h = container.clientHeight || 360;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080c14);
    scene.fog = new THREE.Fog(0x080c14, 6, 14);
    const camera = new THREE.PerspectiveCamera(45, w/h, 0.1, 5000);
    camera.position.set(2.5, 2.2, 4.2);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(w, h);
    container.appendChild(renderer.domElement);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.4;

    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const d1 = new THREE.DirectionalLight(0x4dd0e1, 0.8); d1.position.set(3,5,2); scene.add(d1);
    const d2 = new THREE.PointLight(0x06b6d4, 0.6, 20); d2.position.set(-3,2,-3); scene.add(d2);

    // Floor grid
    const grid = new THREE.GridHelper(8, 16, 0x06b6d4, 0x1a2030);
    grid.material.opacity = 0.18; grid.material.transparent = true;
    grid.position.y = -1.6; scene.add(grid);

    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();
    // Resize observer
    new ResizeObserver(() => {
      const w = container.clientWidth, h = container.clientHeight;
      camera.aspect = w/h; camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }).observe(container);
    return { scene, camera, renderer, controls };
  }

  // ── VOL SURFACE 3D ──
  function volSurface(c, payload) {
    clear(c); const { scene } = makeScene(c);
    const strikes = payload.strikes_pct || [], mats = payload.maturities_days || [];
    if (!strikes.length || !mats.length) return;
    const ws = strikes.length - 1, hs = mats.length - 1;
    const geo = new THREE.PlaneGeometry(3.5, 2.4, ws, hs);
    const pos = geo.attributes.position;
    const ivBy = {};
    payload.grid.forEach(g => ivBy[`${g.maturity_days}_${g.moneyness}`] = g.iv);
    const ivs = payload.grid.map(g => g.iv);
    const minIV = Math.min(...ivs), maxIV = Math.max(...ivs);
    const colors = [];
    for (let j = 0; j <= hs; j++) for (let i = 0; i <= ws; i++) {
      const iv = ivBy[`${mats[j]}_${strikes[i]}`] || minIV;
      const idx = j*(ws+1) + i;
      pos.setZ(idx, (iv - minIV) * 7);
      const t = (iv - minIV) / Math.max(1e-6, maxIV - minIV);
      const col = new THREE.Color().setHSL(0.55 - t*0.5, 0.95, 0.55);
      colors.push(col.r, col.g, col.b);
    }
    pos.needsUpdate = true; geo.computeVertexNormals();
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true, side: THREE.DoubleSide,
      metalness: 0.2, roughness: 0.45, emissive: 0x06b6d4, emissiveIntensity: 0.12,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = -Math.PI/2.3;
    scene.add(mesh);
    // wireframe
    const wf = new THREE.LineSegments(new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: CYAN, transparent: true, opacity: 0.35 }));
    wf.rotation.copy(mesh.rotation); scene.add(wf);
  }

  // ── MC PATH CLOUD ──
  function mcCloud(c, payload) {
    clear(c); const { scene } = makeScene(c);
    const paths = payload.paths || []; if (!paths.length) return;
    const horizon = paths[0].length;
    const flat = paths.flat();
    const minV = Math.min(...flat), maxV = Math.max(...flat);
    paths.forEach((p, idx) => {
      const start = p[0], end = p[p.length-1];
      const isUp = end > start;
      const pts = p.map((v, i) => new THREE.Vector3(
        (i / horizon - 0.5) * 4,
        ((v - minV) / (maxV - minV) - 0.5) * 2.5,
        (Math.random() - 0.5) * 0.5,
      ));
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({
        color: isUp ? GREEN : RED,
        transparent: true, opacity: 0.12 + Math.random() * 0.12,
      });
      scene.add(new THREE.Line(geo, mat));
    });
  }

  // ── PCA SCATTER ──
  function pca(c, payload) {
    clear(c); const { scene } = makeScene(c);
    const pts = payload.scatter || []; if (!pts.length) return;
    const positions = [], colors = [];
    pts.forEach((p, i) => {
      positions.push(p.pc1 * 4, p.pc2 * 4, p.pc3 * 4);
      const col = new THREE.Color().setHSL(i / pts.length, 0.85, 0.6);
      colors.push(col.r, col.g, col.b);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({ size: 0.12, vertexColors: true, sizeAttenuation: true });
    scene.add(new THREE.Points(geo, mat));
    // axes
    scene.add(new THREE.AxesHelper(2));
  }

  // ── RISK TOPOLOGY ──
  function riskTopo(c, payload) {
    clear(c); const { scene } = makeScene(c);
    const pts = payload.points || []; if (!pts.length) return;
    pts.forEach(p => {
      const lq = Math.max(1e6, p.size);
      const size = 0.04 + (Math.log10(lq) - 6) * 0.025;
      const col = new THREE.Color().setHSL(0.3 + p.y * 0.3, 0.85, 0.55);
      const geo = new THREE.SphereGeometry(Math.max(0.04, size), 12, 12);
      const mat = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.5, roughness: 0.4 });
      const m = new THREE.Mesh(geo, mat);
      m.position.set(p.x * 2.5, p.y * 4, p.z * 4);
      scene.add(m);
    });
  }

  // ── PDF MESH (return distribution) ──
  function pdfMesh(c, payload) {
    clear(c);
    const w = c.clientWidth, h = c.clientHeight;
    const svg = d3.select(c).append('svg').attr('width', w).attr('height', h);
    const xs = payload.x, ys = payload.y;
    if (!xs?.length) return;
    const x = d3.scaleLinear().domain(d3.extent(xs)).range([40, w-20]);
    const y = d3.scaleLinear().domain([0, d3.max(ys)]).range([h-30, 30]);
    const area = d3.area().x((_,i)=>x(xs[i])).y0(h-30).y1(d=>y(d)).curve(d3.curveBasis);
    // gradient
    const grad = svg.append('defs').append('linearGradient').attr('id','pg').attr('x1',0).attr('x2',0).attr('y1',0).attr('y2',1);
    grad.append('stop').attr('offset','0%').attr('stop-color','#06b6d4').attr('stop-opacity',0.6);
    grad.append('stop').attr('offset','100%').attr('stop-color','#06b6d4').attr('stop-opacity',0);
    svg.append('path').datum(ys).attr('d', area).attr('fill','url(#pg)');
    svg.append('path').datum(ys)
      .attr('d', d3.line().x((_,i)=>x(xs[i])).y(d=>y(d)).curve(d3.curveBasis))
      .attr('fill','none').attr('stroke','#06b6d4').attr('stroke-width',1.5);
    // zero line
    if (xs[0] < 0 && xs[xs.length-1] > 0) {
      svg.append('line').attr('x1',x(0)).attr('x2',x(0)).attr('y1',30).attr('y2',h-30)
        .attr('stroke','#3f475d').attr('stroke-dasharray','3,3');
    }
  }

  // ── COVARIANCE HEATMAP ──
  function heatmap(c, payload) {
    clear(c);
    const matrix = payload.matrix || [];
    if (!matrix.length) return;
    const w = c.clientWidth, h = c.clientHeight;
    const size = Math.min(w, h) - 30;
    const cell = size / matrix.length;
    const svg = d3.select(c).append('svg').attr('width', w).attr('height', h);
    const flat = matrix.flat(), ext = d3.extent(flat);
    const color = d3.scaleSequential(d3.interpolateInferno).domain(ext);
    const g = svg.append('g').attr('transform', `translate(${(w-size)/2},15)`);
    matrix.forEach((row,i) => row.forEach((v,j) => {
      g.append('rect').attr('x',j*cell).attr('y',i*cell)
        .attr('width',cell).attr('height',cell).attr('fill',color(v));
    }));
  }

  // ── CORRELATION NETWORK ──
  function network(c, payload) {
    clear(c);
    const nodes = (payload.nodes || []).map(n => ({...n}));
    const edges = (payload.edges || []).map(e => ({...e}));
    if (!nodes.length) return;
    const w = c.clientWidth, h = c.clientHeight;
    const svg = d3.select(c).append('svg').attr('width', w).attr('height', h);
    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d=>d.id).distance(70).strength(0.6))
      .force('charge', d3.forceManyBody().strength(-100))
      .force('center', d3.forceCenter(w/2, h/2));
    const link = svg.append('g').selectAll('line').data(edges).join('line')
      .attr('stroke', d => d.weight >= 0 ? '#06b6d4' : '#a855f7')
      .attr('stroke-opacity', d => Math.min(0.9, Math.abs(d.weight)));
    const node = svg.append('g').selectAll('g').data(nodes).join('g');
    node.append('circle').attr('r', 4).attr('fill', '#3b82f6')
      .attr('stroke', '#06b6d4').attr('stroke-width', 1);
    node.append('text').text(d=>d.id).attr('x',6).attr('y',3)
      .attr('fill','#8089a3').attr('font-size',9).attr('font-family','JetBrains Mono');
    sim.on('tick', () => {
      link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
          .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
  }

  // ── LIQUIDITY HEATMAP ──
  function liquidity(c, payload) {
    clear(c);
    const matrix = payload.matrix || [];
    if (!matrix.length) return;
    const w = c.clientWidth, h = c.clientHeight;
    const cell = Math.min((w-40)/10, (h-40)/10);
    const svg = d3.select(c).append('svg').attr('width', w).attr('height', h);
    const max = Math.max(...matrix.flat());
    const color = d3.scaleSequential(d3.interpolateViridis).domain([0, max || 1]);
    const g = svg.append('g').attr('transform',`translate(${(w-cell*10)/2},20)`);
    matrix.forEach((row,i) => row.forEach((v,j) => {
      g.append('rect').attr('x',j*cell).attr('y',i*cell)
        .attr('width',cell-1).attr('height',cell-1).attr('fill',color(v));
    }));
  }

  // ── IV SKEW TERM STRUCTURE ──
  function ivSkew(c, payload) {
    clear(c);
    const data = payload.series || []; if (!data.length) return;
    const w = c.clientWidth, h = c.clientHeight;
    const svg = d3.select(c).append('svg').attr('width',w).attr('height',h);
    const x = d3.scaleLinear().domain(d3.extent(data, d=>d.maturity_days)).range([40, w-20]);
    const y = d3.scaleLinear().domain([
      d3.min(data,d=>Math.min(d.iv_otm_call_25d,d.iv_otm_put_25d))*0.95,
      d3.max(data,d=>Math.max(d.iv_otm_call_25d,d.iv_otm_put_25d))*1.05,
    ]).range([h-30, 30]);
    [['iv_otm_call_25d','#10b981'],['iv_otm_put_25d','#ef4444'],['atm_iv','#06b6d4']].forEach(([k,col]) => {
      svg.append('path').datum(data)
        .attr('d', d3.line().x(d=>x(d.maturity_days)).y(d=>y(d[k])).curve(d3.curveMonotoneX))
        .attr('fill','none').attr('stroke',col).attr('stroke-width',1.5);
    });
  }

  // ── EQUITY CURVE (synthetic for backtest preview) ──
  function equityCurve(c, series) {
    clear(c);
    if (!series?.length) return;
    const w = c.clientWidth, h = c.clientHeight;
    const svg = d3.select(c).append('svg').attr('width',w).attr('height',h);
    const x = d3.scaleLinear().domain([0, series[0].pts.length-1]).range([40, w-20]);
    const yAll = series.flatMap(s => s.pts);
    const y = d3.scaleLinear().domain([Math.min(...yAll)*0.98, Math.max(...yAll)*1.02]).range([h-30, 30]);
    series.forEach(s => {
      svg.append('path').datum(s.pts)
        .attr('d', d3.line().x((_,i)=>x(i)).y(d=>y(d)).curve(d3.curveBasis))
        .attr('fill','none').attr('stroke',s.color).attr('stroke-width',1.5).attr('opacity',0.85);
    });
  }

  // ── ALLOCATION DONUT ──
  function donut(c, items) {
    clear(c);
    const w = c.clientWidth, h = c.clientHeight;
    const r = Math.min(w,h)/2 - 16;
    const svg = d3.select(c).append('svg').attr('width',w).attr('height',h)
      .append('g').attr('transform',`translate(${w/2},${h/2})`);
    const pie = d3.pie().value(d=>d.value).sort(null);
    const arc = d3.arc().innerRadius(r*0.6).outerRadius(r);
    const colors = ['#06b6d4','#3b82f6','#a855f7','#10b981','#f59e0b','#ef4444','#8089a3'];
    svg.selectAll('path').data(pie(items)).join('path')
      .attr('d', arc).attr('fill',(d,i) => colors[i % colors.length])
      .attr('stroke', '#04060a').attr('stroke-width', 2);
    svg.append('text').attr('text-anchor','middle').attr('dy',-2)
      .attr('fill','#06b6d4').attr('font-family','Orbitron').attr('font-size',16).attr('font-weight',700)
      .text(items.length);
    svg.append('text').attr('text-anchor','middle').attr('dy',16)
      .attr('fill','#8089a3').attr('font-size',9).attr('letter-spacing','0.25em')
      .text('POSITIONS');
  }

  function render(container, vizType, payload) {
    try {
      switch (vizType) {
        case 'vol_surface_3d':           return volSurface(container, payload);
        case 'mc_path_cloud':            return mcCloud(container, payload);
        case 'pca_factor_decomposition': return pca(container, payload);
        case 'risk_topology':            return riskTopo(container, payload);
        case 'pdf_mesh':                 return pdfMesh(container, payload);
        case 'covariance_heatmap':       return heatmap(container, payload);
        case 'correlation_network':      return network(container, payload);
        case 'liquidity_heatmap':        return liquidity(container, payload);
        case 'iv_skew_term_structure':   return ivSkew(container, payload);
        default:
          container.innerHTML = `<div class="empty">${vizType} no renderer</div>`;
      }
    } catch (e) {
      container.innerHTML = `<div class="empty">renderer error: ${e.message}</div>`;
    }
  }

  return { render, equityCurve, donut };
})();
