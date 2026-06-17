/**
 * hermes-beads Dashboard Plugin — vis-network DAG renderer
 * v2.0.0-alpha.1
 *
 * Renders the bead dependency graph as an interactive vis-network diagram
 * with neon-glowing nodes, hierarchical layout, and clickable detail panel.
 */

(function () {
  'use strict';

  const PLUGIN_NAME = 'hermes-beads';
  const API_BASE = '/api/plugins/hermes-beads/api';
  const REFRESH_MS = 30000;
  const VIS_CDN = 'https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js';

  // ── state ──────────────────────────────────────────────────────────
  let currentProject = null;
  let network = null;
  let refreshTimer = null;
  let allProjects = [];
  let currentBeads = [];

  // ── DOM helpers ─────────────────────────────────────────────────────
  function el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    if (attrs) Object.assign(e, attrs);
    children.forEach(c => { if (c != null) e.append(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }

  // ── fetch helpers ───────────────────────────────────────────────────
  async function apiGet(path) {
    const resp = await fetch(API_BASE + path);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return resp.json();
  }

  // ── project selector ────────────────────────────────────────────────
  function buildSelector(projects) {
    const sel = el('select', { id: 'hb-project-select', style: 'padding:6px 12px;border-radius:6px;border:1px solid #333;background:#1a1a2e;color:#fff;font-size:14px;margin-bottom:12px;' });
    sel.appendChild(el('option', { value: '' }, '— select project —'));
    projects.forEach(p => {
      sel.appendChild(el('option', { value: p.name }, `${p.name} (${p.bead_count})`));
    });
    sel.addEventListener('change', () => {
      currentProject = sel.value;
      if (currentProject) loadGraph();
    });
    return sel;
  }

  function buildStatusBar(projects) {
    const bar = el('div', { style: 'display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px;font-size:13px;color:#888;' });
    projects.forEach(p => {
      const pill = el('span', {
        style: `padding:2px 10px;border-radius:12px;background:#222;cursor:pointer;border:1px solid #333;`,
        title: `View ${p.name}`,
      }, `${p.name}: ${p.bead_count}`);
      pill.addEventListener('click', () => {
        document.getElementById('hb-project-select').value = p.name;
        currentProject = p.name;
        loadGraph();
      });
      bar.appendChild(pill);
    });
    return bar;
  }

  // ── graph loading ───────────────────────────────────────────────────
  async function loadProjects() {
    try {
      const data = await apiGet('/projects');
      allProjects = data.projects || [];
      return allProjects;
    } catch (e) {
      console.error('[hermes-beads] failed to load projects:', e);
      return [];
    }
  }

  async function loadGraph() {
    if (!currentProject) return;
    const container = document.getElementById('hb-graph-container');
    if (!container) return;

    try {
      const data = await apiGet(`/projects/${encodeURIComponent(currentProject)}/graph`);
      currentBeads = data.nodes || [];
      renderGraph(data.nodes || [], data.edges || [], container);
    } catch (e) {
      console.error('[hermes-beads] failed to load graph:', e);
    }
  }

  // ── detail panel ────────────────────────────────────────────────────
  function showDetail(nodeId) {
    const node = currentBeads.find(n => n.id === nodeId);
    if (!node) return;

    const panel = document.getElementById('hb-detail-panel');
    if (!panel) return;

    panel.innerHTML = [
      `<div style="padding:16px;background:#222244;border-radius:8px;border:1px solid #334;">`,
      `  <h3 style="margin:0 0 8px;color:#00ff88;">${esc(node.id)}</h3>`,
      `  <p style="color:#ccc;margin:0 0 8px;">${esc(node.title || '')}</p>`,
      `  <div style="display:flex;gap:8px;margin-bottom:8px;">`,
      `    <span style="padding:2px 8px;border-radius:4px;background:#333;color:#fff;font-size:12px;">${esc(node.status || '?')}</span>`,
      `    <span style="padding:2px 8px;border-radius:4px;background:#333;color:#fff;font-size:12px;">${esc(node.priority || '?')}</span>`,
      `  </div>`,
      `  <button id="hb-close-detail" style="padding:6px 16px;background:#333;color:#fff;border:1px solid #555;border-radius:4px;cursor:pointer;">Close</button>`,
      `</div>`,
    ].join('\n');

    document.getElementById('hb-close-detail').addEventListener('click', () => {
      panel.innerHTML = '';
    });
  }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ── graph rendering ─────────────────────────────────────────────────
  function renderGraph(nodes, edges, container) {
    container.innerHTML = '';

    if (!nodes.length) {
      container.innerHTML = '<p style="color:#888;padding:2rem;text-align:center;">No beads found for this project.</p>';
      return;
    }

    // Apply visual styling to nodes
    const styledNodes = nodes.map(n => ({
      ...n,
      color: n.color || { background: '#666', border: '#444' },
      font: n.font || { size: 11, color: '#ccc', face: 'monospace' },
      borderWidth: n.borderWidth ?? 2,
      shadow: n.shadow || { enabled: true, size: 10 },
      shape: n.shape || 'dot',
      size: n.size || 18,
    }));

    const data = { nodes: new vis.DataSet(styledNodes), edges: new vis.DataSet(edges) };

    const options = {
      layout: {
        hierarchical: {
          enabled: true,
          direction: 'LR',
          sortMethod: 'directed',
          nodeSpacing: 120,
          levelSeparation: 200,
        },
      },
      edges: {
        arrows: { to: { enabled: true, scaleFactor: 0.6 } },
        color: { color: '#444466', highlight: '#8888aa' },
        smooth: { type: 'curvedCW', roundness: 0.2 },
        width: 1,
      },
      physics: {
        enabled: true,
        hierarchicalRepulsion: { nodeDistance: 150 },
        solver: 'hierarchicalRepulsion',
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        navigationButtons: true,
        keyboard: true,
      },
    };

    network = new vis.Network(container, data, options);

    // Click handler
    network.on('click', function (params) {
      if (params.nodes.length > 0) {
        showDetail(params.nodes[0]);
      }
    });

    // Double-click to focus
    network.on('doubleClick', function (params) {
      if (params.nodes.length > 0) {
        network.focus(params.nodes[0], { scale: 1.5, animation: true });
      }
    });
  }

  // ── auto-refresh ────────────────────────────────────────────────────
  function startRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
      if (currentProject) loadGraph();
    }, REFRESH_MS);
  }

  function stopRefresh() {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  }

  // ── main init ───────────────────────────────────────────────────────
  async function init(container) {
    container.innerHTML = [
      '<div style="height:100%;display:flex;flex-direction:column;font-family:system-ui,sans-serif;">',
      '  <div style="padding:12px 16px;border-bottom:1px solid #333;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">',
      '    <strong style="color:#00ff88;font-size:18px;">🐝 Beads Graph</strong>',
      '    <span id="hb-selector-container"></span>',
      '    <span id="hb-refresh-info" style="color:#666;font-size:12px;"></span>',
      '  </div>',
      '  <div id="hb-status-bar" style="padding:4px 16px;font-size:12px;color:#666;border-bottom:1px solid #222;"></div>',
      '  <div style="flex:1;display:flex;overflow:hidden;">',
      '    <div id="hb-graph-container" style="flex:1;min-width:0;background:#0d0d1a;"></div>',
      '    <div id="hb-detail-panel" style="width:280px;background:#111122;border-left:1px solid #333;overflow-y:auto;flex-shrink:0;"></div>',
      '  </div>',
      '</div>',
    ].join('\n');

    // Load projects
    const projects = await loadProjects();
    const selectorContainer = document.getElementById('hb-selector-container');
    const statusBar = document.getElementById('hb-status-bar');

    if (selectorContainer) {
      selectorContainer.appendChild(buildSelector(projects));
    }
    if (statusBar) {
      statusBar.appendChild(buildStatusBar(projects));
    }

    // Auto-select first project
    if (projects.length > 0) {
      const sel = document.getElementById('hb-project-select');
      if (sel) {
        // Prefer hermes-beads project
        const hbProj = projects.find(p => p.name === 'hermes-beads');
        if (hbProj) {
          sel.value = 'hermes-beads';
          currentProject = 'hermes-beads';
        } else {
          sel.value = projects[0].name;
          currentProject = projects[0].name;
        }
        await loadGraph();
      }
    }

    startRefresh();

    // Update refresh timer display
    const refreshInfo = document.getElementById('hb-refresh-info');
    if (refreshInfo) {
      setInterval(() => {
        refreshInfo.textContent = currentProject ? `auto-refresh ${REFRESH_MS / 1000}s` : '';
      }, 1000);
    }
  }

  // ── load vis-network and bootstrap ──────────────────────────────────
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  async function bootstrap() {
    try {
      await loadScript(VIS_CDN);
    } catch (e) {
      console.warn('[hermes-beads] vis-network CDN failed, retrying...', e);
      try {
        await loadScript(VIS_CDN);
      } catch (e2) {
        console.error('[hermes-beads] vis-network load failed:', e2);
      }
    }

    if (window.registerDashboardPlugin) {
      window.registerDashboardPlugin(PLUGIN_NAME, {
        name: 'Beads',
        version: '2.0.0-alpha.1',
        render: init,
      });
    }
  }

  bootstrap();
})();
