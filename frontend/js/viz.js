// Visualization renderers for every viz_type from `visualization_data`
window.solstice.viz = (() => {
  function clearAndMount(container) {
    container.innerHTML = '';
  }

  // ---------- Three.js helpers ----------
  function makeScene(container) {
    const w = container.clientWidth || 480;
    const h = container.clientHeight || 320;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d0f14);
    const camera = new THREE.PerspectiveCamera(45, w/h, 0.1, 5000);
    camera.position.set(2, 2, 4);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(w, h);
    container.appendChild(renderer.domElement);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const dir = new THREE.DirectionalLight(0xffffff, 0.6);
    dir.position.set(3,5,4); scene.add(dir);
    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();
    return { scene, camera, renderer, controls };
  }

  // VOL SURFACE 3D
  function renderVolSurface(container, payload) {
    clearAndMount(container);
    const { scene } = makeScene(container);
    const strikes = payload.strikes_pct || [];
    const mats = payload.maturities_days || [];
    if (!strikes.length || !mats.length) return;
    const widthSeg = strikes.length - 1, heightSeg = mats.length - 1;
    const geom = new THREE.PlaneGeometry(3, 2, widthSeg, heightSeg);
    const pos = geom.attributes.position;
    const ivByCell = {};
    payload.grid.forEach(g => {
      ivByCell[`${g.maturity_days}_${g.moneyness}`] = g.iv;
    });
    const colors = [];
    const minIV = Math.min(...payload.grid.map(g => g.iv));
    const maxIV = Math.max(...payload.grid.map(g => g.iv));
    for (let j=0; j<=heightSeg; j++) {
      for (let i=0; i<=widthSeg; i++) {
        const iv = ivByCell[`${mats[j]}_${strikes[i]}`] || minIV;
        const idx = j*(widthSeg+1) + i;
        pos.setZ(idx, (iv - minIV) * 6);
        const t = (iv - minIV) / Math.max(1e-6, maxIV - minIV);
        const col = new THREE.Color().setHSL(0.65 - t*0.65, 0.9, 0.5);
        colors.push(col.r, col.g, col.b);
      }
    }
    pos.needsUpdate = true;
    geom.computeVertexNormals();
    geom.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true, side: THREE.DoubleSide,
      flatShading: false, metalness: 0.1, roughness: 0.6, wireframe: false,
    });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.rotation.x = -Math.PI / 2.4;
    scene.add(mesh);

    // Wireframe overlay
    const wire = new THREE.LineSegments(
      new THREE.WireframeGeometry(geom),
      new THREE.LineBasicMaterial({ color: 0x222838, transparent: true, opacity: 0.4 })
    );
    wire.rotation.copy(mesh.rotation);
    scene.add(wire);
  }

  // MC PATH CLOUD
  function renderMCCloud(container, payload) {
    clearAndMount(container);
    const { scene } = makeScene(container);
    const paths = payload.paths || [];
    if (!paths.length) return;
    const horizon = paths[0].length;
    const allVals = paths.flat();
    const minV = Math.min(...allVals), maxV = Math.max(...allVals);
    paths.forEach((p, idx) => {
      const pts = p.map((v, i) => new THREE.Vector3(
        (i / horizon - 0.5) * 4,
        ((v - minV) / (maxV - minV) - 0.5) * 2,
        (Math.random() - 0.5) * 0.2,
      ));
      const geom = new THREE.BufferGeometry().setFromPoints(pts);
      const hue = 0.55 + (Math.random() - 0.5) * 0.1;
      const mat = new THREE.LineBasicMaterial({
        color: new THREE.Color().setHSL(hue, 0.8, 0.55),
        transparent: true, opacity: 0.18,
      });
      scene.add(new THREE.Line(geom, mat));
    });
  }

  // PDF MESH (2D area chart with SVG)
  function renderPDF(container, payload) {
    clearAndMount(container);
    const w = container.clientWidth, h = container.clientHeight;
    const svg = d3.select(container).append('svg')
      .attr('width', w).attr('height', h);
    const xs = payload.x, ys = payload.y;
    if (!xs?.length) return;
    const x = d3.scaleLinear().domain(d3.extent(xs)).range([20, w-20]);
    const y = d3.scaleLinear().domain([0, d3.max(ys)]).range([h-20, 20]);
    const area = d3.area()
      .x((_,i) => x(xs[i])).y0(h-20).y1((d) => y(d))
      .curve(d3.curveBasis);
    svg.append('path').datum(ys)
      .attr('d', area).attr('fill', '#4ade80').attr('opacity', 0.25);
    svg.append('path').datum(ys)
      .attr('d', d3.line().x((_,i)=>x(xs[i])).y((d)=>y(d)).curve(d3.curveBasis))
      .attr('fill', 'none').attr('stroke', '#4ade80').attr('stroke-width', 1.2);
  }

  // COVARIANCE / CORRELATION HEATMAP
  function renderHeatmap(container, payload) {
    clearAndMount(container);
    const matrix = payload.matrix || [];
    const tickers = payload.tickers || [];
    if (!matrix.length) return;
    const w = container.clientWidth, h = container.clientHeight;
    const m = Math.min(w, h) - 24;
    const cell = m / matrix.length;
    const svg = d3.select(container).append('svg').attr('width', w).attr('height', h);
    const flat = matrix.flat();
    const ext = d3.extent(flat);
    const color = d3.scaleSequential(d3.interpolateInferno).domain([ext[0], ext[1]]);
    const g = svg.append('g').attr('transform', `translate(${(w-m)/2},12)`);
    matrix.forEach((row, i) => row.forEach((v, j) => {
      g.append('rect')
        .attr('x', j*cell).attr('y', i*cell)
        .attr('width', cell).attr('height', cell)
        .attr('fill', color(v));
    }));
  }

  // CORRELATION NETWORK (force-directed)
  function renderNetwork(container, payload) {
    clearAndMount(container);
    const nodes = (payload.nodes || []).map(n => ({ ...n }));
    const edges = (payload.edges || []).map(e => ({ ...e }));
    if (!nodes.length) return;
    const w = container.clientWidth, h = container.clientHeight;
    const svg = d3.select(container).append('svg').attr('width', w).attr('height', h);

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(60).strength(0.6))
      .force('charge', d3.forceManyBody().strength(-80))
      .force('center', d3.forceCenter(w/2, h/2));

    const link = svg.append('g').selectAll('line').data(edges).join('line')
      .attr('stroke', d => d.weight > 0 ? '#4ade80' : '#f43f5e')
      .attr('stroke-opacity', d => Math.min(0.8, Math.abs(d.weight)));

    const node = svg.append('g').selectAll('g').data(nodes).join('g');
    node.append('circle').attr('r', 4).attr('fill', '#60a5fa');
    node.append('text').text(d => d.id).attr('x', 6).attr('y', 3)
      .attr('fill', '#6b7187').attr('font-size', 9).attr('font-family', 'monospace');

    sim.on('tick', () => {
      link.attr('x1', d=>d.source.x).attr('y1', d=>d.source.y)
          .attr('x2', d=>d.target.x).attr('y2', d=>d.target.y);
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
  }

  // PCA 3D SCATTER
  function renderPCA(container, payload) {
    clearAndMount(container);
    const { scene } = makeScene(container);
    const pts = payload.scatter || [];
    if (!pts.length) return;
    const geom = new THREE.BufferGeometry();
    const positions = [];
    const colors = [];
    pts.forEach((p, i) => {
      positions.push(p.pc1*3, p.pc2*3, p.pc3*3);
      const hue = i / pts.length;
      const c = new THREE.Color().setHSL(hue, 0.85, 0.6);
      colors.push(c.r, c.g, c.b);
    });
    geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geom.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({ size: 0.08, vertexColors: true });
    scene.add(new THREE.Points(geom, mat));
  }

  // LIQUIDITY HEATMAP
  function renderLiquidityHeatmap(container, payload) {
    return renderHeatmap(container, { matrix: payload.matrix, tickers: [] });
  }

  // RISK TOPOLOGY 3D scatter
  function renderRiskTopology(container, payload) {
    clearAndMount(container);
    const { scene } = makeScene(container);
    const pts = payload.points || [];
    if (!pts.length) return;
    pts.forEach(p => {
      const size = Math.log10(Math.max(1e6, p.size)) - 6;
      const geom = new THREE.SphereGeometry(0.04 + size*0.02, 8, 8);
      const c = new THREE.Color().setHSL(0.3 + p.y, 0.8, 0.55);
      const mat = new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.3 });
      const m = new THREE.Mesh(geom, mat);
      m.position.set(p.x*2, p.y*4, p.z*4);
      scene.add(m);
    });
  }

  // IV SKEW TERM STRUCTURE (line chart)
  function renderSkewTS(container, payload) {
    clearAndMount(container);
    const w = container.clientWidth, h = container.clientHeight;
    const svg = d3.select(container).append('svg').attr('width', w).attr('height', h);
    const data = payload.series || [];
    if (!data.length) return;
    const x = d3.scaleLinear().domain(d3.extent(data, d => d.maturity_days)).range([40, w-20]);
    const y = d3.scaleLinear().domain([
      d3.min(data, d => Math.min(d.iv_otm_call_25d, d.iv_otm_put_25d)) * 0.95,
      d3.max(data, d => Math.max(d.iv_otm_call_25d, d.iv_otm_put_25d)) * 1.05,
    ]).range([h-30, 20]);

    [['iv_otm_call_25d','#4ade80'],['iv_otm_put_25d','#f43f5e'],['atm_iv','#60a5fa']].forEach(([key, color]) => {
      svg.append('path').datum(data)
        .attr('d', d3.line().x(d => x(d.maturity_days)).y(d => y(d[key])))
        .attr('fill', 'none').attr('stroke', color).attr('stroke-width', 1.5);
    });
  }

  // SIGNAL MAP (per-strategy heat grid)
  function renderSignalMap(container, payload) {
    clearAndMount(container);
    const strategies = payload.strategies || {};
    const names = Object.keys(strategies);
    if (!names.length) return;
    const tickers = [...new Set(names.flatMap(s => strategies[s].map(x => x.ticker)))].slice(0, 30);
    const w = container.clientWidth, h = container.clientHeight;
    const cellW = (w - 100) / tickers.length;
    const cellH = Math.min(28, (h - 40) / names.length);
    const svg = d3.select(container).append('svg').attr('width', w).attr('height', h);
    names.forEach((s, i) => {
      svg.append('text').text(s).attr('x', 6).attr('y', 30 + i*cellH + cellH/1.5)
        .attr('fill', '#6b7187').attr('font-size', 10).attr('font-family', 'monospace');
      const byT = Object.fromEntries(strategies[s].map(x => [x.ticker, x.alpha]));
      tickers.forEach((t, j) => {
        const v = byT[t] || 0;
        const color = v > 0 ? d3.interpolateGreens(Math.min(1, Math.abs(v))) :
                                d3.interpolateReds(Math.min(1, Math.abs(v)));
        svg.append('rect').attr('x', 100 + j*cellW).attr('y', 30 + i*cellH)
          .attr('width', cellW-1).attr('height', cellH-1).attr('fill', color);
      });
    });
    tickers.forEach((t, j) => {
      svg.append('text').text(t).attr('x', 100 + j*cellW).attr('y', 20)
        .attr('fill', '#6b7187').attr('font-size', 8).attr('font-family', 'monospace')
        .attr('transform', `rotate(-45 ${100 + j*cellW} 20)`);
    });
  }

  // PORTFOLIO GREEKS bars
  function renderGreeks(container, payload) {
    clearAndMount(container);
    const totals = payload.totals || {};
    const keys = ['delta','gamma','vega','theta'];
    const w = container.clientWidth, h = container.clientHeight;
    const svg = d3.select(container).append('svg').attr('width', w).attr('height', h);
    const max = Math.max(...keys.map(k => Math.abs(totals[k] || 0)));
    keys.forEach((k, i) => {
      const v = totals[k] || 0;
      const len = (Math.abs(v) / Math.max(1e-6, max)) * (w - 120);
      svg.append('text').text(k.toUpperCase()).attr('x', 8).attr('y', 30 + i*30)
        .attr('fill', '#6b7187').attr('font-size', 11).attr('font-family', 'monospace');
      svg.append('rect').attr('x', 70).attr('y', 18 + i*30).attr('height', 16).attr('width', len)
        .attr('fill', v >= 0 ? '#4ade80' : '#f43f5e');
      svg.append('text').text(v.toFixed(2)).attr('x', 80 + len).attr('y', 30 + i*30)
        .attr('fill', '#d8dde9').attr('font-size', 11).attr('font-family', 'monospace');
    });
  }

  // Master dispatcher
  function render(container, vizType, payload) {
    try {
      switch (vizType) {
        case 'vol_surface_3d':           return renderVolSurface(container, payload);
        case 'mc_path_cloud':            return renderMCCloud(container, payload);
        case 'pdf_mesh':                 return renderPDF(container, payload);
        case 'covariance_heatmap':       return renderHeatmap(container, payload);
        case 'correlation_network':      return renderNetwork(container, payload);
        case 'pca_factor_decomposition': return renderPCA(container, payload);
        case 'liquidity_heatmap':        return renderLiquidityHeatmap(container, payload);
        case 'risk_topology':            return renderRiskTopology(container, payload);
        case 'iv_skew_term_structure':   return renderSkewTS(container, payload);
        case 'signal_map':               return renderSignalMap(container, payload);
        case 'portfolio_greeks':         return renderGreeks(container, payload);
        default:
          container.innerHTML = `<div class="empty">[ ${vizType} renderer not yet wired ]</div>`;
      }
    } catch (err) {
      container.innerHTML = `<div class="empty">renderer error: ${err.message}</div>`;
    }
  }

  return { render };
})();
