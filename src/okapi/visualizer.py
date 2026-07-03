"""Render an OKF bundle as a single self-contained interactive HTML page.

The page embeds a JSON payload (concepts + link graph) and inline CSS/JS —
no network access needed, so the file can be shipped alongside the bundle.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import markdown

from . import okf_schema
from .validator import _parse_frontmatter

_MD_LINK = re.compile(r"(\[[^\]]*\]\()([^)\s]+)([^)]*\))")

_MD_EXTENSIONS = ["tables", "fenced_code", "sane_lists"]


@dataclass
class BundleGraph:
    concepts: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    welcome_html: str = ""  # rendered root index.md, if present


def _concept_id(rel: Path) -> str:
    return rel.as_posix()[: -len(".md")]


def _resolve_link(target: str, source_rel: Path, bundle: Path) -> str | None:
    """Resolve a markdown link target to a concept id, or None if it points
    elsewhere (external URL, anchor, non-concept file)."""
    target = target.split("#", 1)[0].split("?", 1)[0]
    if not target or "://" in target or target.startswith("mailto:"):
        return None
    if target.startswith("/"):  # bundle-root-absolute (Google blog style)
        candidate = (bundle / target.lstrip("/")).resolve()
    else:
        candidate = (bundle / source_rel).parent.joinpath(target).resolve()
    try:
        rel = candidate.relative_to(bundle.resolve())
    except ValueError:
        return None
    if rel.suffix != ".md" or rel.name in okf_schema.RESERVED_FILENAMES:
        return None
    if not (bundle / rel).exists():
        return None
    return _concept_id(rel)


def _render_body(body: str, source_rel: Path, bundle: Path) -> str:
    """Markdown → HTML, rewriting intra-bundle concept links to #concept:<id>
    anchors that the viewer's JS turns into in-app navigation."""

    def rewrite(m: re.Match) -> str:
        cid = _resolve_link(m.group(2), source_rel, bundle)
        if cid is None:
            return m.group(0)
        return f"{m.group(1)}#concept:{cid}{m.group(3)}"

    return markdown.markdown(_MD_LINK.sub(rewrite, body), extensions=_MD_EXTENSIONS)


def load_bundle(bundle_dir: Path) -> BundleGraph:
    """Parse every concept in the bundle into graph nodes and link edges."""
    bundle = Path(bundle_dir)
    graph = BundleGraph()
    seen_edges: set[tuple[str, str]] = set()

    for md_file in sorted(bundle.rglob("*.md")):
        rel = md_file.relative_to(bundle)
        text = md_file.read_text(encoding="utf-8")

        if md_file.name in okf_schema.RESERVED_FILENAMES:
            if rel == Path("index.md"):
                graph.welcome_html = _render_body(text, rel, bundle)
            continue

        try:
            fm = _parse_frontmatter(text)
        except ValueError:
            fm = None
        if fm is None:
            continue  # not a conforming concept; the validator reports these

        body = text.split("---", 2)[2] if text.startswith("---") else text
        cid = _concept_id(rel)
        graph.concepts.append(
            {
                "id": cid,
                "path": rel.as_posix(),
                "type": str(fm.get("type", "Unknown")),
                "title": str(fm.get("title", cid)),
                "description": str(fm.get("description", "")),
                "tags": [str(t) for t in fm.get("tags") or []],
                "resource": str(fm.get("resource", "")),
                "timestamp": str(fm.get("timestamp", "")),
                "html": _render_body(body, rel, bundle),
            }
        )
        for m in _MD_LINK.finditer(body):
            target_id = _resolve_link(m.group(2), rel, bundle)
            if target_id and target_id != cid and (cid, target_id) not in seen_edges:
                seen_edges.add((cid, target_id))
                graph.edges.append({"source": cid, "target": target_id})

    ids = {c["id"] for c in graph.concepts}
    graph.edges = [e for e in graph.edges if e["target"] in ids]
    return graph


def build_visualization(bundle_dir: Path, output_file: Path | None = None) -> Path:
    """Write the viewer HTML next to the bundle and return its path."""
    bundle = Path(bundle_dir)
    graph = load_bundle(bundle)
    if not graph.concepts:
        raise ValueError(f"{bundle}: no concept files found — nothing to visualize")

    payload = {
        "bundle": bundle.resolve().name,
        "concepts": graph.concepts,
        "edges": graph.edges,
        "welcome": graph.welcome_html,
    }
    # </ must not terminate the inline <script> block early.
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = _TEMPLATE.replace("__TITLE__", payload["bundle"]).replace("__DATA__", data)

    out = output_file or bundle / "okf-viewer.html"
    out = Path(out)
    out.write_text(html, encoding="utf-8")
    return out


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — OKF knowledge graph</title>
<style>
  :root {
    --bg: #fafaf8; --panel: #ffffff; --ink: #1f2430; --muted: #6b7280;
    --line: #e5e4df; --accent: #4269d0; --canvas: #f4f3ef;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--ink); background: var(--bg);
    display: grid; grid-template-rows: 52px 1fr;
    grid-template-columns: 270px 1fr minmax(340px, 430px);
    grid-template-areas: "head head head" "side graph detail";
  }
  header {
    grid-area: head; display: flex; align-items: center; gap: 18px;
    padding: 0 18px; background: var(--panel); border-bottom: 1px solid var(--line);
  }
  header h1 { font-size: 15px; margin: 0; font-weight: 650; }
  header h1 span { color: var(--muted); font-weight: 400; }
  .stats { display: flex; gap: 14px; color: var(--muted); font-size: 12.5px; }
  .stats b { color: var(--ink); font-weight: 600; }
  #sidebar {
    grid-area: side; background: var(--panel); border-right: 1px solid var(--line);
    display: flex; flex-direction: column; min-height: 0;
  }
  #search {
    margin: 12px; padding: 7px 10px; border: 1px solid var(--line); border-radius: 8px;
    font: inherit; background: var(--bg); outline: none;
  }
  #search:focus { border-color: var(--accent); }
  #legend { padding: 0 12px 8px; display: flex; flex-wrap: wrap; gap: 6px; }
  .type-chip {
    display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px;
    border: 1px solid var(--line); border-radius: 999px; font-size: 12px;
    cursor: pointer; user-select: none; background: var(--panel);
  }
  .type-chip.off { opacity: 0.35; }
  .dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
  #list { overflow-y: auto; flex: 1; padding: 4px 8px 16px; }
  .group-label {
    font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--muted); margin: 12px 6px 4px;
  }
  .item {
    padding: 6px 8px; border-radius: 7px; cursor: pointer; display: flex;
    align-items: baseline; gap: 8px;
  }
  .item:hover { background: var(--bg); }
  .item.active { background: #e8edfb; }
  .item .t { font-weight: 550; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #graph-wrap { grid-area: graph; position: relative; background: var(--canvas); min-width: 0; }
  #graph { position: absolute; inset: 0; width: 100%; height: 100%; cursor: grab; }
  #hint {
    position: absolute; left: 12px; bottom: 10px; font-size: 11.5px; color: var(--muted);
    background: color-mix(in srgb, var(--canvas) 75%, transparent); padding: 2px 8px; border-radius: 6px;
  }
  #detail {
    grid-area: detail; background: var(--panel); border-left: 1px solid var(--line);
    overflow-y: auto; padding: 20px 22px; min-height: 0;
  }
  #detail h2 { margin: 0 0 2px; font-size: 19px; }
  .badge {
    display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px;
    font-weight: 600; color: #fff; margin: 6px 0 2px;
  }
  .meta { color: var(--muted); font-size: 12.5px; margin: 6px 0 2px; }
  .meta code { background: var(--bg); padding: 1px 5px; border-radius: 4px; }
  .tags { margin: 8px 0 0; display: flex; flex-wrap: wrap; gap: 5px; }
  .tag { background: var(--bg); border: 1px solid var(--line); border-radius: 999px;
         padding: 1px 8px; font-size: 11.5px; color: var(--muted); }
  .body { margin-top: 14px; border-top: 1px solid var(--line); padding-top: 4px; }
  .body h1, .body h2, .body h3 { font-size: 15px; margin: 18px 0 6px; }
  .body p, .body li { font-size: 13.5px; }
  .body code { background: var(--bg); padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
  .body pre { background: #22252d; color: #e6e6e6; padding: 12px 14px; border-radius: 9px;
              overflow-x: auto; font-size: 12.5px; }
  .body pre code { background: none; color: inherit; padding: 0; }
  .body table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 12.8px; }
  .body th, .body td { border: 1px solid var(--line); padding: 5px 9px; text-align: left; }
  .body th { background: var(--bg); }
  .body a { color: var(--accent); text-decoration: none; }
  .body a:hover { text-decoration: underline; }
  .links h3 { font-size: 12px; letter-spacing: 0.05em; text-transform: uppercase;
              color: var(--muted); margin: 18px 0 6px; }
  .links a { display: block; color: var(--accent); text-decoration: none; padding: 2px 0; font-size: 13px; }
  .links a:hover { text-decoration: underline; }
  .empty { color: var(--muted); font-size: 12.5px; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__ <span>· OKF knowledge graph</span></h1>
  <div class="stats" id="stats"></div>
</header>

<div id="sidebar">
  <input id="search" type="search" placeholder="Search concepts, tags…">
  <div id="legend"></div>
  <div id="list"></div>
</div>

<div id="graph-wrap">
  <canvas id="graph"></canvas>
  <div id="hint">scroll to zoom · drag background to pan · drag nodes · click to inspect</div>
</div>

<div id="detail"></div>

<script id="okf-data" type="application/json">__DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("okf-data").textContent);

/* ---------- palette (Observable-10, keyed by known concept types) ---------- */
const TYPE_COLORS = {
  "system": "#4269d0", "service": "#efb118", "module": "#ff725c",
  "entry point": "#6cc5b0", "workflow": "#3ca951", "data model": "#ff8ab7",
  "interface": "#a463f2", "dependency": "#97bbf5", "convention": "#9c6b4e",
  "decision": "#9498a0",
};
const FALLBACK = ["#4269d0","#efb118","#ff725c","#6cc5b0","#3ca951","#ff8ab7","#a463f2","#97bbf5","#9c6b4e","#9498a0"];
const typeColor = (() => {
  const cache = new Map();
  return t => {
    const k = t.toLowerCase();
    if (TYPE_COLORS[k]) return TYPE_COLORS[k];
    if (!cache.has(k)) cache.set(k, FALLBACK[cache.size % FALLBACK.length]);
    return cache.get(k);
  };
})();

/* ---------- model ---------- */
const nodes = DATA.concepts.map(c => ({...c, x: 0, y: 0, vx: 0, vy: 0, deg: 0}));
const byId = new Map(nodes.map(n => [n.id, n]));
const links = DATA.edges
  .map(e => ({s: byId.get(e.source), t: byId.get(e.target)}))
  .filter(l => l.s && l.t);
links.forEach(l => { l.s.deg++; l.t.deg++; });
const inbound = new Map(nodes.map(n => [n.id, []]));
const outbound = new Map(nodes.map(n => [n.id, []]));
links.forEach(l => { outbound.get(l.s.id).push(l.t); inbound.get(l.t.id).push(l.s); });

const types = [...new Set(nodes.map(n => n.type))].sort();
const typeOn = new Map(types.map(t => [t, true]));
let query = "", selected = null, hovered = null;

const visible = n => typeOn.get(n.type) &&
  (!query || (n.title + " " + n.id + " " + n.tags.join(" ")).toLowerCase().includes(query));

/* ---------- stats ---------- */
const orphans = nodes.filter(n => n.deg === 0).length;
document.getElementById("stats").innerHTML =
  `<span><b>${nodes.length}</b> concepts</span><span><b>${links.length}</b> links</span>` +
  `<span><b>${types.length}</b> types</span>` + (orphans ? `<span><b>${orphans}</b> unlinked</span>` : "");

/* ---------- legend ---------- */
const legend = document.getElementById("legend");
types.forEach(t => {
  const n = nodes.filter(x => x.type === t).length;
  const chip = document.createElement("span");
  chip.className = "type-chip";
  chip.innerHTML = `<span class="dot" style="background:${typeColor(t)}"></span>${t} · ${n}`;
  chip.onclick = () => { typeOn.set(t, !typeOn.get(t)); chip.classList.toggle("off"); renderList(); reheat(); };
  legend.appendChild(chip);
});

/* ---------- sidebar list ---------- */
const list = document.getElementById("list");
function renderList() {
  list.innerHTML = "";
  types.filter(t => typeOn.get(t)).forEach(t => {
    const items = nodes.filter(n => n.type === t && visible(n));
    if (!items.length) return;
    const lab = document.createElement("div");
    lab.className = "group-label"; lab.textContent = t;
    list.appendChild(lab);
    items.forEach(n => {
      const el = document.createElement("div");
      el.className = "item" + (selected === n ? " active" : "");
      el.innerHTML = `<span class="dot" style="background:${typeColor(n.type)}"></span><span class="t">${n.title}</span>`;
      el.onclick = () => select(n, true);
      list.appendChild(el);
    });
  });
}
document.getElementById("search").addEventListener("input", e => {
  query = e.target.value.trim().toLowerCase(); renderList(); draw();
});

/* ---------- detail panel ---------- */
const detail = document.getElementById("detail");
function esc(s) { const d = document.createElement("span"); d.textContent = s; return d.innerHTML; }
function linkList(title, arr) {
  if (!arr.length) return "";
  return `<div class="links"><h3>${title}</h3>` + arr.map(n =>
    `<a href="#concept:${encodeURIComponent(n.id)}">${esc(n.title)} <span style="color:var(--muted)">· ${esc(n.type)}</span></a>`).join("") + "</div>";
}
function showWelcome() {
  detail.innerHTML = DATA.welcome
    ? `<div class="body">${DATA.welcome}</div>`
    : `<p class="empty">Select a concept in the graph or the list to inspect it.</p>`;
}
function select(n, center) {
  selected = n; renderList();
  if (!n) { showWelcome(); draw(); return; }
  detail.innerHTML =
    `<h2>${esc(n.title)}</h2>` +
    `<span class="badge" style="background:${typeColor(n.type)}">${esc(n.type)}</span>` +
    (n.description ? `<p style="margin:8px 0 0">${esc(n.description)}</p>` : "") +
    (n.resource ? `<div class="meta">resource <code>${esc(n.resource)}</code></div>` : "") +
    (n.timestamp ? `<div class="meta">updated ${esc(n.timestamp)}</div>` : "") +
    (n.tags.length ? `<div class="tags">${n.tags.map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : "") +
    `<div class="body">${n.html}</div>` +
    linkList("Links to", outbound.get(n.id)) +
    linkList("Linked from", inbound.get(n.id));
  detail.scrollTop = 0;
  if (center) { view.tx = W / 2 - n.x * view.k; view.ty = H / 2 - n.y * view.k; }
  draw();
}
document.addEventListener("click", e => {
  const a = e.target.closest("a");
  if (!a) return;
  const href = a.getAttribute("href") || "";
  if (href.startsWith("#concept:")) {
    e.preventDefault();
    const n = byId.get(decodeURIComponent(href.slice(9)));
    if (n) select(n, true);
  }
});

/* ---------- force-directed canvas graph ---------- */
const canvas = document.getElementById("graph"), ctx = canvas.getContext("2d");
let W = 0, H = 0, DPR = window.devicePixelRatio || 1;
const view = {k: 1, tx: 0, ty: 0};
function resize() {
  const r = canvas.parentElement.getBoundingClientRect();
  W = r.width; H = r.height;
  canvas.width = W * DPR; canvas.height = H * DPR;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  draw();
}
window.addEventListener("resize", resize);

/* initial positions: type clusters on a ring */
types.forEach((t, ti) => {
  const a = (ti / types.length) * 2 * Math.PI, R = 190;
  nodes.filter(n => n.type === t).forEach((n, i) => {
    n.x = Math.cos(a) * R + (i % 5) * 22 - 44 + Math.random() * 8;
    n.y = Math.sin(a) * R + Math.floor(i / 5) * 22 + Math.random() * 8;
  });
});

let alpha = 1;
function reheat() { if (alpha < 0.3) { alpha = 0.3; tick(); } }
function tick() {
  const act = nodes.filter(n => typeOn.get(n.type));
  for (let i = 0; i < act.length; i++) {
    const a = act[i];
    for (let j = i + 1; j < act.length; j++) {   // repulsion
      const b = act[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let d2 = dx * dx + dy * dy || 1;
      if (d2 < 90000) {
        const f = 1400 / d2;
        dx *= f; dy *= f;
        a.vx += dx; a.vy += dy; b.vx -= dx; b.vy -= dy;
      }
    }
    a.vx -= a.x * 0.004; a.vy -= a.y * 0.004;    // gravity to origin
  }
  links.forEach(l => {                            // springs
    if (!typeOn.get(l.s.type) || !typeOn.get(l.t.type)) return;
    const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y;
    const d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 95) * 0.012 / d;
    l.s.vx += dx * f; l.s.vy += dy * f; l.t.vx -= dx * f; l.t.vy -= dy * f;
  });
  act.forEach(n => {
    if (n === dragNode) return;
    n.vx *= 0.72; n.vy *= 0.72;
    n.x += n.vx * alpha; n.y += n.vy * alpha;
  });
  alpha *= 0.985;
  draw();
  if (alpha > 0.005) requestAnimationFrame(tick);
}

const radius = n => 6 + Math.sqrt(n.deg) * 2.2;
function draw() {
  ctx.clearRect(0, 0, W, H);
  ctx.save();
  ctx.translate(view.tx, view.ty); ctx.scale(view.k, view.k);
  const neighbors = selected
    ? new Set([selected.id, ...outbound.get(selected.id).map(n => n.id), ...inbound.get(selected.id).map(n => n.id)])
    : null;
  const dim = n => (neighbors && !neighbors.has(n.id)) || (query && !visible(n));

  links.forEach(l => {
    if (!typeOn.get(l.s.type) || !typeOn.get(l.t.type)) return;
    const faded = dim(l.s) || dim(l.t);
    ctx.strokeStyle = faded ? "rgba(31,36,48,0.05)" : "rgba(31,36,48,0.16)";
    ctx.lineWidth = (selected && (l.s === selected || l.t === selected)) ? 1.8 : 1;
    ctx.beginPath(); ctx.moveTo(l.s.x, l.s.y); ctx.lineTo(l.t.x, l.t.y); ctx.stroke();
  });
  nodes.forEach(n => {
    if (!typeOn.get(n.type)) return;
    const r = radius(n), faded = dim(n);
    ctx.globalAlpha = faded ? 0.18 : 1;
    ctx.fillStyle = typeColor(n.type);
    ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 7); ctx.fill();
    if (n === selected || n === hovered) {
      ctx.strokeStyle = "#1f2430"; ctx.lineWidth = 2 / view.k;
      ctx.beginPath(); ctx.arc(n.x, n.y, r + 2.5, 0, 7); ctx.stroke();
    }
    if (view.k > 0.75 || n === selected || n === hovered || (neighbors && neighbors.has(n.id))) {
      ctx.fillStyle = faded ? "rgba(31,36,48,0.25)" : "#1f2430";
      ctx.font = `${11 / view.k}px -apple-system, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText(n.title, n.x, n.y + r + 12 / view.k);
    }
    ctx.globalAlpha = 1;
  });
  ctx.restore();
}

/* ---------- interaction ---------- */
let dragNode = null, panning = false, px = 0, py = 0, moved = false;
const toWorld = (mx, my) => [(mx - view.tx) / view.k, (my - view.ty) / view.k];
function hit(mx, my) {
  const [x, y] = toWorld(mx, my);
  let best = null, bd = Infinity;
  nodes.forEach(n => {
    if (!typeOn.get(n.type)) return;
    const d = Math.hypot(n.x - x, n.y - y);
    if (d < radius(n) + 4 && d < bd) { best = n; bd = d; }
  });
  return best;
}
canvas.addEventListener("mousedown", e => {
  const n = hit(e.offsetX, e.offsetY);
  moved = false;
  if (n) { dragNode = n; reheat(); }
  else { panning = true; canvas.style.cursor = "grabbing"; }
  px = e.offsetX; py = e.offsetY;
});
window.addEventListener("mousemove", e => {
  const r = canvas.getBoundingClientRect();
  const mx = e.clientX - r.left, my = e.clientY - r.top;
  if (dragNode) {
    const [x, y] = toWorld(mx, my);
    dragNode.x = x; dragNode.y = y; moved = true; reheat();
  } else if (panning) {
    view.tx += mx - px; view.ty += my - py; px = mx; py = my; moved = true; draw();
  } else {
    const h = hit(mx, my);
    if (h !== hovered) { hovered = h; canvas.style.cursor = h ? "pointer" : "grab"; draw(); }
  }
});
window.addEventListener("mouseup", e => {
  if (dragNode && !moved) select(dragNode, false);
  else if (panning && !moved) select(null, false);
  dragNode = null; panning = false; canvas.style.cursor = "grab";
});
canvas.addEventListener("wheel", e => {
  e.preventDefault();
  const f = Math.exp(-e.deltaY * 0.0015);
  const k2 = Math.min(4, Math.max(0.25, view.k * f));
  view.tx = e.offsetX - (e.offsetX - view.tx) * (k2 / view.k);
  view.ty = e.offsetY - (e.offsetY - view.ty) * (k2 / view.k);
  view.k = k2; draw();
}, {passive: false});

/* ---------- boot ---------- */
resize();
view.tx = W / 2; view.ty = H / 2;
renderList(); showWelcome(); tick();
</script>
</body>
</html>
"""
