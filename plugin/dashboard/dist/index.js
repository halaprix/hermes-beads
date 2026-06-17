/**
 * hermes-beads Dashboard Plugin — interactive bead DAG viewer
 * v2.0.0-alpha.1
 *
 * Uses Hermes Plugin SDK (React + shadcn). Renders a vis-network DAG
 * with neon glow styling, status filters, search, dispatch, and gate resolve.
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  const React = SDK.React;
  const h = React.createElement;
  const { useState, useEffect, useRef, useCallback } = SDK.hooks;
  const { Card, CardContent, Button, Badge, Input, Select, SelectOption } = SDK.components;
  const cn = SDK.utils.cn || function () { return Array.from(arguments).filter(Boolean).join(" "); };

  const API_BASE = "/api/plugins/hermes-beads/api";
  const REFRESH_MS = 30000;
  const STATUSES = ["open", "in_progress", "blocked", "closed", "deferred"];
  const STATUS_COLORS = { open: "#00ff88", in_progress: "#ffaa00", blocked: "#ff4477", closed: "#666", deferred: "#888" };
  const STATUS_LABELS = { open: "Ready", in_progress: "In Progress", blocked: "Blocked", closed: "Closed", deferred: "Deferred" };

  // ── API helpers ───────────────────────────────────────────────────
  async function apiGet(path) {
    const resp = await fetch(API_BASE + path);
    if (!resp.ok) throw new Error(resp.status + "");
    return resp.json();
  }
  async function apiPost(path, body) {
    const resp = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(resp.status + "");
    return resp.json();
  }

  // ── Graph renderer (imperative, called from useEffect) ────────────
  function renderVisNetwork(container, nodes, edges, onNodeClick) {
    if (!container) return null;
    container.innerHTML = "";

    if (!window.vis) {
      container.innerHTML = '<div style="color:#888;padding:2rem;text-align:center;">Loading vis-network…</div>';
      return null;
    }
    if (!nodes.length) {
      container.innerHTML = '<div style="color:#666;padding:3rem;text-align:center;"><p style="font-size:18px;">📭 No beads found</p><p style="font-size:13px;">Run <code>bd init</code> in a project to start tracking.</p></div>';
      return null;
    }

    const styled = nodes.map(n => ({
      ...n,
      color: n.color || { background: "#666", border: "#444", highlight: { background: "#888", border: "#666" } },
      font: n.font || { size: 11, color: "#ccc", face: "monospace" },
      borderWidth: n.borderWidth ?? 2,
      shadow: n.shadow || { enabled: true, size: 10 },
      shape: n.shape || "dot",
      size: n.size || 18,
    }));
    const styledEdges = edges.map((e, i) => ({ ...e, id: e.id || "e" + i }));
    const dsNodes = new vis.DataSet(styled);
    const dsEdges = new vis.DataSet(styledEdges);

    const net = new vis.Network(container, { nodes: dsNodes, edges: dsEdges }, {
      layout: {
        hierarchical: { enabled: true, direction: "LR", sortMethod: "directed", nodeSpacing: 120, levelSeparation: 200 },
      },
      edges: { arrows: { to: { enabled: true, scaleFactor: 0.6 } }, color: { color: "#444466", highlight: "#8888aa" }, smooth: { type: "curvedCW", roundness: 0.2 }, width: 1 },
      physics: { enabled: true, hierarchicalRepulsion: { nodeDistance: 150 }, solver: "hierarchicalRepulsion" },
      interaction: { hover: true, tooltipDelay: 200, navigationButtons: true, keyboard: true },
    });

    net.on("click", p => { if (p.nodes.length && onNodeClick) onNodeClick(p.nodes[0]); });
    net.on("doubleClick", p => { if (p.nodes.length) net.focus(p.nodes[0], { scale: 1.5, animation: true }); });

    return net;
  }

  // ── Detail panel ─────────────────────────────────────────────────
  function DetailPanel({ nodeId, nodes, project, onClose, onDispatch, onGate }) {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return null;
    const s = node.status || "open";
    const color = STATUS_COLORS[s] || "#666";

    return h(Card, { className: "hb-detail-card", style: { margin: "12px" } },
      h(CardContent, null,
        h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 8 } },
          h("h3", { style: { margin: 0, fontSize: 15, color: "#fff" } }, node.id),
          h(Button, { size: "sm", variant: "ghost", onClick: onClose, style: { color: "#888" } }, "✕")
        ),
        h("p", { style: { color: "#aaa", fontSize: 13, margin: "0 0 10px" } }, node.title || ""),
        h("div", { style: { display: "flex", gap: 6, marginBottom: 10 } },
          h(Badge, { style: { background: color + "22", color, border: "1px solid " + color } }, STATUS_LABELS[s] || s),
          h(Badge, { style: { background: "#333", color: "#ccc" } }, node.priority || "?")
        ),
        h("div", { style: { display: "flex", gap: 8 } },
          h(Button, { size: "sm", style: { background: "#00cc66", color: "#000", fontWeight: 600 }, onClick: () => onDispatch(nodeId) }, "🚀 Dispatch"),
          h(Button, { size: "sm", variant: "outline", onClick: () => onGate(nodeId) }, "🔓 Resolve")
        )
      )
    );
  }

  // ── Toast ────────────────────────────────────────────────────────
  function useToast() {
    const [toast, setToast] = useState(null);
    const show = useCallback((msg, type) => {
      setToast({ msg, type, ts: Date.now() });
      setTimeout(() => setToast(null), 3500);
    }, []);
    return { toast, show };
  }

  // ── Main BeadsPage ───────────────────────────────────────────────
  function BeadsPage() {
    const [projects, setProjects] = useState([]);
    const [project, setProject] = useState("");
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [filters, setFilters] = useState(new Set(STATUSES));
    const [search, setSearch] = useState("");
    const [selectedNode, setSelectedNode] = useState(null);
    const [visLoaded, setVisLoaded] = useState(false);
    const graphRef = useRef(null);
    const networkRef = useRef(null);
    const { toast, show } = useToast();

    // Load vis-network CDN
    useEffect(() => {
      if (window.vis) { setVisLoaded(true); return; }
      const s = document.createElement("script");
      s.src = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js";
      s.onload = () => setVisLoaded(true);
      s.onerror = () => { s.src = s.src; document.head.appendChild(s); };
      document.head.appendChild(s);
    }, []);

    // Load projects
    useEffect(() => {
      apiGet("/projects").then(d => {
        setProjects(d.projects || []);
        const hb = (d.projects || []).find(p => p.name === "hermes-beads");
        if (hb) setProject("hermes-beads");
        else if (d.projects?.length) setProject(d.projects[0].name);
      }).catch(() => {});
    }, []);

    // Load graph when project changes
    useEffect(() => {
      if (!project || !visLoaded) return;
      setLoading(true);
      setError(null);
      apiGet("/projects/" + encodeURIComponent(project) + "/graph")
        .then(d => {
          setNodes(d.nodes || []);
          setEdges(d.edges || []);
          setSelectedNode(null);
        })
        .catch(e => setError("Failed to load: " + (e.message || "unknown")))
        .finally(() => setLoading(false));
    }, [project, visLoaded]);

    // Render vis-network into container
    useEffect(() => {
      if (!visLoaded || !graphRef.current) return;
      const filteredNodes = nodes.filter(n => filters.has(n.group || n.status));
      const visibleIds = new Set(filteredNodes.map(n => n.id));
      const filteredEdges = edges.filter(e => visibleIds.has(e.from) && visibleIds.has(e.to));
      // Apply search
      const q = search.toLowerCase().trim();
      const finalNodes = q
        ? filteredNodes.filter(n => (n.id + " " + (n.title || "")).toLowerCase().includes(q))
        : filteredNodes;
      const finalIds = new Set(finalNodes.map(n => n.id));
      const finalEdges = filteredEdges.filter(e => finalIds.has(e.from) && finalIds.has(e.to));

      if (networkRef.current) networkRef.current.destroy();
      networkRef.current = renderVisNetwork(graphRef.current, finalNodes, finalEdges, setSelectedNode);
    }, [nodes, edges, filters, search, visLoaded]);

    // Auto-refresh
    useEffect(() => {
      if (!project) return;
      const timer = setInterval(() => {
        apiGet("/projects/" + encodeURIComponent(project) + "/graph")
          .then(d => { setNodes(d.nodes || []); setEdges(d.edges || []); })
          .catch(() => {});
      }, REFRESH_MS);
      return () => clearInterval(timer);
    }, [project]);

    const handleDispatch = async (beadId) => {
      show("Dispatching " + beadId + "…", "info");
      try {
        const r = await apiPost("/projects/" + encodeURIComponent(project) + "/dispatch", { bead_ids: [beadId] });
        const ok = r.results?.[0]?.success;
        show(ok ? "✅ Dispatched " + beadId : "❌ " + (r.results?.[0]?.output || "Failed"), ok ? "success" : "error");
        if (ok) {
          const d = await apiGet("/projects/" + encodeURIComponent(project) + "/graph");
          setNodes(d.nodes || []); setEdges(d.edges || []);
        }
      } catch (e) { show("❌ " + e.message, "error"); }
    };

    const handleGate = async (beadId) => {
      show("Resolving " + beadId + "…", "info");
      try {
        const r = await apiPost("/projects/" + encodeURIComponent(project) + "/gate/" + encodeURIComponent(beadId), { comment: "Resolved via dashboard" });
        show("✅ " + (r.message || "Resolved"), "success");
        const d = await apiGet("/projects/" + encodeURIComponent(project) + "/graph");
        setNodes(d.nodes || []); setEdges(d.edges || []);
      } catch (e) { show("❌ " + e.message, "error"); }
    };

    const toggleFilter = (s) => {
      const next = new Set(filters);
      next.has(s) ? next.delete(s) : next.add(s);
      setFilters(next);
    };

    return h("div", { style: { height: "100%", display: "flex", flexDirection: "column", background: "#0d0d1a", color: "#ccc", fontFamily: "system-ui, sans-serif" } },
      // Header
      h("div", { style: { padding: "8px 14px", borderBottom: "1px solid #222", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" } },
        h("strong", { style: { color: "#00ff88", fontSize: 17 } }, "🐝 Beads"),
        projects.length > 0 && h(Select, { value: project, onValueChange: setProject, style: { maxWidth: 200 } },
          h(SelectOption, { value: "" }, "— select —"),
          ...projects.map(p => h(SelectOption, { key: p.name, value: p.name }, p.name + " (" + p.bead_count + ")"))
        ),
        h(Input, { placeholder: "Search beads…", value: search, onChange: e => setSearch(e.target.value), style: { width: 160, background: "#1a1a2e", color: "#fff", border: "1px solid #333" } }),
        h("span", { style: { color: "#666", fontSize: 12 } }, nodes.length + " beads"),
        h("span", { style: { flex: 1 } }),
        h(Button, { size: "sm", variant: "outline", onClick: () => { if (project) { setLoading(true); apiGet("/projects/" + encodeURIComponent(project) + "/graph").then(d => { setNodes(d.nodes || []); setEdges(d.edges || []); }).catch(() => {}).finally(() => setLoading(false)); } } }, "🔄 Refresh"),
      ),
      // Filters
      h("div", { style: { padding: "4px 14px", borderBottom: "1px solid #222", display: "flex", gap: 6, flexWrap: "wrap" } },
        ...STATUSES.map(s => {
          const on = filters.has(s);
          return h(Button, {
            key: s,
            size: "sm",
            variant: on ? "default" : "ghost",
            style: { fontSize: 11, opacity: on ? 1 : 0.4, borderColor: STATUS_COLORS[s], color: STATUS_COLORS[s] },
            onClick: () => toggleFilter(s),
          }, STATUS_LABELS[s] || s);
        })
      ),
      // Graph + detail
      h("div", { style: { flex: 1, display: "flex", overflow: "hidden" } },
        h("div", {
          ref: graphRef,
          style: { flex: 1, minWidth: 0, background: "#0d0d1a" },
        }, loading && h("div", { style: { color: "#888", padding: "3rem", textAlign: "center" } }, "⏳ Loading beads…"),
           error && h("div", { style: { color: "#ff4477", padding: "2rem", textAlign: "center" } }, "❌ " + error)),
        selectedNode && h("div", { style: { width: 300, background: "#111122", borderLeft: "1px solid #222", overflowY: "auto", flexShrink: 0 } },
          h(DetailPanel, { nodeId: selectedNode, nodes, project, onClose: () => setSelectedNode(null), onDispatch: handleDispatch, onGate: handleGate })
        )
      ),
      // Footer
      h("div", { style: { padding: "3px 14px", borderTop: "1px solid #222", fontSize: 11, color: "#555", display: "flex", gap: 16 } },
        h("span", null, "Click: detail"), h("span", null, "Dbl-click: zoom"), h("span", null, "Esc: close panel"), h("span", null, "30s auto-refresh")
      ),
      // Toast
      toast && h("div", {
        style: { position: "fixed", bottom: 20, right: 20, padding: "10px 20px", borderRadius: 6, zIndex: 9999,
          background: toast.type === "error" ? "#ff4477" : toast.type === "success" ? "#00cc66" : "#333",
          color: "#fff", fontSize: 13 }
      }, toast.msg)
    );
  }

  // ── Register ─────────────────────────────────────────────────────
  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("hermes-beads", BeadsPage);
  }
})();
