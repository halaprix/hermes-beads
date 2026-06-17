/**
 * hermes-beads Dashboard Plugin — interactive bead DAG viewer
 * v2.0.0-alpha.1
 *
 * vis-network DAG with neon glow, detail panel, dispatch, filters, search.
 */
(function () {
  'use strict';

  const PLUGIN_NAME = 'hermes-beads';
  const API_BASE = '/api/plugins/hermes-beads/api';
  const REFRESH_MS = 30000;
  const VIS_CDN = 'https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js';
  const STATUSES = ['open', 'in_progress', 'blocked', 'closed', 'deferred'];

  let currentProject = null;
  let network = null;
  let refreshTimer = null;
  let allProjects = [];
  let currentBeads = [];
  let currentEdges = [];
  let activeFilters = new Set(STATUSES);
  let searchQuery = '';

  // ── DOM helpers ─────────────────────────────────────────────────────
  function el(t, a, ...c) {
    const e = document.createElement(t);
    if (a) Object.assign(e, a);
    c.forEach(x => { if (x != null) e.append(typeof x === 'string' ? document.createTextNode(x) : x); });
    return e;
  }
  function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

  // ── API ─────────────────────────────────────────────────────────────
  async function api(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(API_BASE + path, opts);
    if (!resp.ok) throw new Error(`${resp.status}`);
    return resp.json();
  }
  const apiGet = path => api('GET', path);
  const apiPost = (path, body) => api('POST', path, body);

  // ── toast ───────────────────────────────────────────────────────────
  function toast(msg, type) {
    const t = el('div', {
      style: `position:fixed;bottom:20px;right:20px;padding:10px 20px;border-radius:6px;z-index:9999;
        background:${type==='error'?'#ff4477':type==='success'?'#00cc66':'#333'};color:#fff;font-size:13px;`
    }, msg);
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  // ── project selector ────────────────────────────────────────────────
  function buildSelector(projects) {
    const sel = el('select', {
      id: 'hb-select',
      style: 'padding:5px 10px;border-radius:6px;border:1px solid #333;background:#1a1a2e;color:#fff;font-size:13px;'
    });
    sel.appendChild(el('option', { value: '' }, '— select —'));
    projects.forEach(p => sel.appendChild(el('option', { value: p.name }, `${p.name} (${p.bead_count})`)));
    sel.addEventListener('change', () => { currentProject = sel.value; if (currentProject) loadGraph(); });
    return sel;
  }

  // ── status filter pills ─────────────────────────────────────────────
  function buildFilters() {
    const bar = el('div', { id: 'hb-filters', style: 'display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;' });
    const colors = { open: '#00ff88', in_progress: '#ffaa00', blocked: '#ff4477', closed: '#666', deferred: '#888' };
    STATUSES.forEach(s => {
      const btn = el('button', {
        id: `hb-filter-${s}`,
        style: `padding:3px 10px;border-radius:12px;border:1px solid ${colors[s]};background:${colors[s]}22;color:${colors[s]};font-size:11px;cursor:pointer;`,
        textContent: s.replace('_', ' '),
      });
      btn.addEventListener('click', () => {
        if (activeFilters.has(s)) { activeFilters.delete(s); btn.style.opacity = '0.4'; }
        else { activeFilters.add(s); btn.style.opacity = '1'; }
        applyFilters();
      });
      bar.appendChild(btn);
    });
    return bar;
  }

  // ── search ──────────────────────────────────────────────────────────
  function buildSearch() {
    const inp = el('input', {
      type: 'text', id: 'hb-search', placeholder: 'Search beads…',
      style: 'padding:5px 10px;border-radius:6px;border:1px solid #333;background:#1a1a2e;color:#fff;font-size:13px;width:160px;'
    });
    inp.addEventListener('input', () => { searchQuery = inp.value.toLowerCase(); applyFilters(); });
    return inp;
  }

  // ── apply filters ───────────────────────────────────────────────────
  function applyFilters() {
    if (!network) return;
    const visible = new Set();
    currentBeads.forEach(n => {
      const ok = activeFilters.has(n.group || n.status) &&
        (!searchQuery || (n.id + ' ' + (n.title || '')).toLowerCase().includes(searchQuery));
      if (ok) visible.add(n.id);
    });
    // Show nodes in filter, hide others
    currentBeads.forEach(n => {
      network.body.data.nodes.update({ id: n.id, hidden: !visible.has(n.id) });
    });
    // Show edges only if both endpoints visible
    currentEdges.forEach(e => {
      network.body.data.edges.update({ id: e.id, hidden: !(visible.has(e.from) && visible.has(e.to)) });
    });
    document.getElementById('hb-bead-count').textContent = `${visible.size} / ${currentBeads.length}`;
  }

  // ── detail panel ────────────────────────────────────────────────────
  function showDetail(nodeId) {
    const node = currentBeads.find(n => n.id === nodeId);
    if (!node) return;
    const panel = document.getElementById('hb-detail');
    if (!panel) return;

    const statusColor = { open: '#00ff88', in_progress: '#ffaa00', blocked: '#ff4477', closed: '#666', deferred: '#888' };
    const s = node.status || 'open';

    panel.innerHTML = [
      `<div style="padding:14px;">`,
      `  <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:10px;">`,
      `    <h3 style="margin:0;color:#fff;font-size:15px;">${esc(node.id)}</h3>`,
      `    <button id="hb-detail-close" style="background:none;border:none;color:#888;cursor:pointer;font-size:18px;">✕</button>`,
      `  </div>`,
      `  <p style="color:#aaa;margin:0 0 10px;font-size:13px;">${esc(node.title || '')}</p>`,
      `  <div style="display:flex;gap:6px;margin-bottom:10px;">`,
      `    <span style="padding:2px 8px;border-radius:4px;background:${statusColor[s]}22;color:${statusColor[s]};font-size:11px;border:1px solid ${statusColor[s]};">${(s||'').replace('_',' ')}</span>`,
      `    <span style="padding:2px 8px;border-radius:4px;background:#333;color:#ccc;font-size:11px;">${esc(node.priority||'?')}</span>`,
      `  </div>`,
      `  <div style="display:flex;gap:8px;flex-wrap:wrap;">`,
      `    <button id="hb-dispatch-btn" style="padding:6px 14px;background:#00cc66;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:600;font-size:12px;">🚀 Dispatch</button>`,
      `    <button id="hb-gate-btn" style="padding:6px 14px;background:#333;color:#fff;border:1px solid #555;border-radius:4px;cursor:pointer;font-size:12px;">🔓 Resolve gate</button>`,
      `  </div>`,
      `  <div id="hb-detail-status" style="margin-top:10px;font-size:12px;color:#888;"></div>`,
      `</div>`,
    ].join('\n');

    document.getElementById('hb-detail-close').addEventListener('click', () => panel.innerHTML = '');
    document.getElementById('hb-dispatch-btn').addEventListener('click', () => dispatchBead(node.id));
    document.getElementById('hb-gate-btn').addEventListener('click', () => resolveGate(node.id));
  }

  async function dispatchBead(beadId) {
    if (!currentProject) return;
    const status = document.getElementById('hb-detail-status');
    if (status) status.innerHTML = '<span style="color:#ffaa00;">⏳ Dispatching…</span>';
    try {
      const result = await apiPost(`/projects/${encodeURIComponent(currentProject)}/dispatch`, { bead_ids: [beadId] });
      const r = result.results?.[0];
      if (r?.success) {
        if (status) status.innerHTML = '<span style="color:#00cc66;">✅ Dispatched</span>';
        toast(`Dispatched ${beadId}`, 'success');
        setTimeout(loadGraph, 1000);
      } else {
        if (status) status.innerHTML = `<span style="color:#ff4477;">❌ ${esc(r?.output || 'Failed')}</span>`;
        toast(`Dispatch failed: ${r?.output || 'Unknown error'}`, 'error');
      }
    } catch (e) {
      if (status) status.innerHTML = `<span style="color:#ff4477;">❌ ${esc(e.message)}</span>`;
      toast(`Error: ${e.message}`, 'error');
    }
  }

  async function resolveGate(beadId) {
    if (!currentProject) return;
    const status = document.getElementById('hb-detail-status');
    if (status) status.innerHTML = '<span style="color:#ffaa00;">⏳ Resolving…</span>';
    try {
      const result = await apiPost(`/projects/${encodeURIComponent(currentProject)}/gate/${encodeURIComponent(beadId)}`, { comment: 'Resolved via dashboard' });
      if (status) status.innerHTML = `<span style="color:#00cc66;">✅ ${esc(result.message || 'Resolved')}</span>`;
      toast(result.message, 'success');
      setTimeout(loadGraph, 1000);
    } catch (e) {
      if (status) status.innerHTML = `<span style="color:#ff4477;">❌ ${esc(e.message)}</span>`;
      toast(`Error: ${e.message}`, 'error');
    }
  }

  // ── graph rendering ─────────────────────────────────────────────────
  function renderGraph(nodes, edges, container) {
    container.innerHTML = '';
    if (!nodes.length) {
      container.innerHTML = '<div style="color:#666;padding:3rem;text-align:center;"><p style="font-size:18px;">📭 No beads found</p><p style="font-size:13px;">Run <code>bd init</code> in a project to start tracking.</p></div>';
      return;
    }

    const styled = nodes.map((n, i) => ({
      ...n,
      id: n.id,
      color: n.color || { background: '#666', border: '#444' },
      font: n.font || { size: 11, color: '#ccc', face: 'monospace' },
      borderWidth: n.borderWidth ?? 2,
      shadow: n.shadow || { enabled: true, size: 10 },
      shape: n.shape || 'dot',
      size: n.size || 18,
    }));
    const styledEdges = edges.map((e, i) => ({ ...e, id: e.id || `e${i}` }));

    currentBeads = styled;
    currentEdges = styledEdges;

    const dsNodes = new vis.DataSet(styled);
    const dsEdges = new vis.DataSet(styledEdges);

    network = new vis.Network(container, { nodes: dsNodes, edges: dsEdges }, {
      layout: {
        hierarchical: { enabled: true, direction: 'LR', sortMethod: 'directed', nodeSpacing: 120, levelSeparation: 200 },
      },
      edges: { arrows: { to: { enabled: true, scaleFactor: 0.6 } }, color: { color: '#444466', highlight: '#8888aa' }, smooth: { type: 'curvedCW', roundness: 0.2 }, width: 1 },
      physics: { enabled: true, hierarchicalRepulsion: { nodeDistance: 150 }, solver: 'hierarchicalRepulsion' },
      interaction: { hover: true, tooltipDelay: 200, navigationButtons: true, keyboard: true },
    });

    network.on('click', p => { if (p.nodes.length) showDetail(p.nodes[0]); });
    network.on('doubleClick', p => { if (p.nodes.length) network.focus(p.nodes[0], { scale: 1.5, animation: true }); });
    applyFilters();
  }

  // ── data loading ────────────────────────────────────────────────────
  async function loadProjects() {
    try { const d = await apiGet('/projects'); allProjects = d.projects || []; return allProjects; }
    catch (e) { console.error('[hb] projects:', e); return []; }
  }

  async function loadGraph() {
    if (!currentProject) return;
    const c = document.getElementById('hb-graph');
    if (!c) return;
    c.innerHTML = '<div style="color:#888;padding:3rem;text-align:center;">⏳ Loading beads…</div>';
    try {
      const d = await apiGet(`/projects/${encodeURIComponent(currentProject)}/graph`);
      renderGraph(d.nodes || [], d.edges || [], c);
    } catch (e) {
      c.innerHTML = `<div style="color:#ff4477;padding:2rem;text-align:center;">❌ Failed to load: ${esc(e.message)}</div>`;
    }
  }

  // ── refresh ─────────────────────────────────────────────────────────
  function startRefresh() { stopRefresh(); refreshTimer = setInterval(() => { if (currentProject) loadGraph(); }, REFRESH_MS); }
  function stopRefresh() { if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; } }

  // ── main init ───────────────────────────────────────────────────────
  async function init(container) {
    container.innerHTML = [
      '<style>',
      '  @keyframes hb-pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }',
      '  @keyframes hb-slide { from{transform:translateX(100%)} to{transform:translateX(0)} }',
      '  #hb-detail:not(:empty) { animation: hb-slide 0.2s ease-out; }',
      '</style>',
      '<div style="height:100%;display:flex;flex-direction:column;font-family:system-ui,sans-serif;background:#0d0d1a;color:#ccc;">',
      '  <div style="padding:8px 14px;border-bottom:1px solid #222;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">',
      '    <strong style="color:#00ff88;font-size:17px;">🐝 Beads</strong>',
      '    <span id="hb-sel-wrap"></span>',
      '    <span id="hb-search-wrap"></span>',
      '    <span id="hb-bead-count" style="color:#666;font-size:12px;"></span>',
      '    <span style="flex:1;"></span>',
      '    <button id="hb-refresh-btn" style="padding:4px 10px;background:#333;color:#fff;border:1px solid #555;border-radius:4px;cursor:pointer;font-size:12px;">🔄 Refresh</button>',
      '  </div>',
      '  <div style="padding:4px 14px;border-bottom:1px solid #222;" id="hb-filters-wrap"></div>',
      '  <div style="flex:1;display:flex;overflow:hidden;">',
      '    <div id="hb-graph" style="flex:1;min-width:0;background:#0d0d1a;"></div>',
      '    <div id="hb-detail" style="width:300px;background:#111122;border-left:1px solid #222;overflow-y:auto;flex-shrink:0;"></div>',
      '  </div>',
      '  <div style="padding:3px 14px;border-top:1px solid #222;font-size:11px;color:#555;display:flex;gap:16px;">',
      '    <span>Esc: close panel</span><span>/: search</span><span>Click: detail</span><span>Dbl-click: zoom</span>',
      '  </div>',
      '</div>',
    ].join('\n');

    const projects = await loadProjects();
    document.getElementById('hb-sel-wrap').appendChild(buildSelector(projects));
    document.getElementById('hb-search-wrap').appendChild(buildSearch());
    document.getElementById('hb-filters-wrap').appendChild(buildFilters());
    document.getElementById('hb-refresh-btn').addEventListener('click', loadGraph);

    if (projects.length) {
      const hb = projects.find(p => p.name === 'hermes-beads');
      const sel = document.getElementById('hb-select');
      if (hb) { sel.value = 'hermes-beads'; currentProject = 'hermes-beads'; }
      else { sel.value = projects[0].name; currentProject = projects[0].name; }
      await loadGraph();
    }
    startRefresh();

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') document.getElementById('hb-detail').innerHTML = '';
      if (e.key === '/' && document.activeElement !== document.getElementById('hb-search')) {
        e.preventDefault();
        document.getElementById('hb-search').focus();
      }
    });
  }

  // ── bootstrap ───────────────────────────────────────────────────────
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script'); s.src = src; s.onload = resolve; s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  async function bootstrap() {
    try { await loadScript(VIS_CDN); } catch (e) { console.warn('[hb] vis-network CDN retry…'); try { await loadScript(VIS_CDN); } catch (e2) { console.error('[hb] vis-network failed:', e2); } }
    if (window.registerDashboardPlugin) window.registerDashboardPlugin(PLUGIN_NAME, { name: 'Beads', version: '2.0.0-alpha.1', render: init });
  }
  bootstrap();
})();
