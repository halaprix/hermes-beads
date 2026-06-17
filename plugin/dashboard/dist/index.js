// hermes-beads dashboard plugin — placeholder entry point
// v2.0.0-alpha.1
//
// This file is loaded by the Hermes dashboard when the "Beads" tab is active.
// For now, it renders a status placeholder. Phase 3 (hb-dv3) replaces this
// with a full vis-network DAG rendering.

(function () {
  'use strict';

  console.log('[hermes-beads] plugin loaded');

  // Register with the Hermes dashboard plugin host
  if (window.registerDashboardPlugin) {
    window.registerDashboardPlugin('hermes-beads', {
      name: 'Beads',
      version: '2.0.0-alpha.1',
      render: function (container) {
        container.innerHTML = [
          '<div style="padding: 2rem; font-family: system-ui, sans-serif;">',
          '  <h2>🐝 Beads Task Graph</h2>',
          '  <p>Visual DAG rendering coming in <strong>Phase 3</strong> (hb-dv3).</p>',
          '  <p>API endpoints available:</p>',
          '  <ul>',
          '    <li><code>GET /api/plugins/hermes-beads/hello</code> — health check</li>',
          '    <li><code>GET /api/plugins/hermes-beads/beads</code> — all beads</li>',
          '    <li><code>GET /api/plugins/hermes-beads/beads/ready</code> — ready beads</li>',
          '    <li><code>GET /api/plugins/hermes-beads/beads/&lt;id&gt;</code> — bead detail</li>',
          '    <li><code>GET /api/plugins/hermes-beads/beads/graph</code> — DAG data</li>',
          '  </ul>',
          '</div>',
        ].join('\n');
      },
    });
  } else {
    console.warn('[hermes-beads] window.registerDashboardPlugin not found — running standalone?');
  }
})();
