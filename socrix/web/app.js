/* SOCRIX dashboard — vanilla JS, no external libraries, works fully offline.
   Server mode: reads /api/*.  Static-report mode: reads window.SOCRIX_DATA (embedded by `socrix export`). */
"use strict";

/* ---------- identity: the single source for all identity text ---------- */
const SITE = {
  product: "SOCRIX",
  longName: "SOC Risk & Assurance Index",
  tagline: "Supervisory analytics for SOC assurance across critical sectors",
  team: "Team AIRIX",
  teamId: "153754",
  institution: "Bennett University",
  event: "Smart India Hackathon 2026",
  psId: "SIH26157",
  psTitle: "Supervisory Analytics Tool for SOC Assessment (SAT-SA)",
  psOwner: "NTRO / NCIIPC",
  data: "Demonstration dataset (SimSOC)",
  // the one place the demonstration-data disclosure appears on screen (site footer, print footer)
  disclosure: "Demonstration dataset: SimSOC (seed 26157) · Built for SIH 2026 evaluation — not an official NTRO, NCIIPC or Government of India product.",
};

/* ---------- verified strengths (source: docs/VALIDATION.md, docs/ARCHITECTURE.md; not served by the API) ---------- */
const TRUST = [
  ["Independent re-implementation", "576 of 576 figures match exactly."],
  ["Robustness", "98.8% detection across 10 independent test datasets (336/340), 0 false alarms."],
  ["Specificity", "0 false alarms across 24 test runs (default seed, 10-seed sweep, 12 sensitivity runs, 3× scale test), including 43 additional clean entities at 3× scale."],
  ["Scale", "127k alerts and 525k workflow records (48 entities) scored in about 27 seconds on one laptop; peak memory 0.85 GB."],
  ["Tamper-evident", "Hash-chained audit log, SHA-256 receipt for every submitted file, lineage to the source row."],
  ["Privacy", "Analyst identities pseudonymised (keyed HMAC-SHA256); fully offline, with no external services or AI."],
  ["Accessibility", "WCAG 2 A/AA with 0 automated (axe-core) violations, light and dark."],
  ["Security-tested", "Injection and path-traversal attempts rejected; read-only API."],
  ["Standards", "MITRE ATT&CK Enterprise v19.2 (15 tactics); 12 indicators across 7 capability areas; 61 automated tests."],
];
const TRUST_SRC = "Source: docs/VALIDATION.md (verification log, 29 Sep 2026).";

/* ---------- formatters: every number on screen goes through one of these ---------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nil = (v) => v == null || Number.isNaN(Number(v));
const fmtIdx = (v) => (nil(v) ? "–" : Number(v).toFixed(1));                  // indices, z, concern detail: 1 decimal
const fmtPct = (v) => (nil(v) ? "–" : (100 * v).toFixed(1) + "%");           // shares: 1 decimal
const fmtInt = (v) => (nil(v) ? "–" : Number(v).toLocaleString("en-IN"));     // counts: en-IN separators
const fmtConcern = (v) => (nil(v) ? "–" : String(Math.round(v)));            // concern badges and heat cells: whole numbers
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad2 = (n) => String(n).padStart(2, "0");
const fmtDate = (iso) => { const d = new Date(iso); return iso && !isNaN(d) ? `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` : "–"; };
const fmtDateTime = (iso) => { const d = new Date(iso); return iso && !isNaN(d) ? `${fmtDate(iso)}, ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())} UTC` : "–"; };
const fmtPeriod = (p) => { const m = /^(\d{4})-(\d{2})$/.exec(p || ""); return m ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : String(p ?? "–"); };
function fmtDur(ms) {
  const min = Math.round(ms / 60000);
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60), d = Math.floor(h / 24);
  return d ? `${d} d ${h % 24} h` : `${h} h${min % 60 ? ` ${min % 60} min` : ""}`;
}
function fmtVal(iid, v) {            // indicator values in their own unit (same rules as before the redesign)
  if (v == null) return "–";
  if (iid === "EG-02") return Math.round(Math.pow(10, v)) + " min";
  if (iid === "NS-02") return String(Math.round(v));
  if (iid === "NS-05" || iid === "WL-01") return v.toFixed(2);
  return fmtPct(v);
}
const cap = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);

/* ---------- data access ---------- */
const STATIC = typeof window.SOCRIX_DATA === "object";
const AREAS = ["Threat Detection", "Investigation", "Escalation", "Incident Response", "Security Operations",
  "Governance and Oversight", "Operational Discipline", "Cyber Resilience"];
const ALERT_RE = /^[A-Z]{2,5}-\d{2}-\d{4}-\d{2}-AL\d+$/i;
const cache = {};
async function get(path) {
  if (STATIC) {
    const d = window.SOCRIX_DATA[path];
    if (d === undefined) throw new Error("This part is not included in the static report. Run `socrix serve` for the full drill-down.");
    return d;
  }
  if (cache[path]) return cache[path];
  let r;
  try { r = await fetch(path); } catch (e) { const err = new Error("offline"); err.offline = true; throw err; }
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) { /* not JSON */ }
    const err = new Error(msg); err.status = r.status; throw err;
  }
  return (cache[path] = await r.json());
}
const enc = encodeURIComponent;
// concern bins -> CSS classes (colour + text colour per theme live in style.css, validated for contrast)
const hcls = (c) => c == null ? "hna" : c < 20 ? "h0" : c < 35 ? "h1" : c < 50 ? "h2" : c < 75 ? "h3" : "h4";
const heat = (c) => c == null ? "var(--na)" : `var(--c${hcls(c).slice(1)})`;
let CAT = null, META = null;   // indicator catalogue + run metadata
const isRate = (iid) => !!(CAT && CAT[iid] && CAT[iid].rate);
const countText = (i) => isRate(i.indicator) ? `${fmtInt(i.k)}/${fmtInt(i.n)}` : i.indicator === "NS-05" ? `${fmtInt(i.k)} alerts / ${fmtInt(i.n)} assets`
  : i.indicator === "NS-02" ? `${i.k} of ${i.n} expected` : `n=${fmtInt(i.n)}`;
const indName = (code) => (CAT && CAT[code] ? CAT[code].name : code);

/* ---------- small DOM helpers ---------- */
const $ = (id) => document.getElementById(id);
const $app = $("app");
const ICON = {
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  print: '<path d="M6 9V3h12v6M6 18H4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2"/><path d="M6 14h12v7H6z"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  explain: '<path d="M4 5h16v11H8l-4 4z"/><path d="M8 9h8M8 12h5"/>',
  trace: '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M6 8.5v4a3 3 0 0 0 3 3h6.5"/>',
  chain: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  offline: '<rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
};
const icon = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICON[k]}</svg>`;
const announce = (t) => { $("announce").textContent = t; };
function parseHash() {
  const raw = location.hash.slice(1) || "/";
  const [path, qs] = raw.split("?");
  return { parts: decodeURIComponent(path).split("/").filter(Boolean), q: new URLSearchParams(qs || "") };
}
function replaceQuery(base, params) {         // keep filter state in the URL without re-rendering the view
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null && v !== false)).toString();
  history.replaceState(null, "", `#${base}${q ? "?" + q : ""}`);
}
const segmented = (name, label, options, value) => `<div class="seg" role="group" aria-label="${esc(label)}" data-seg="${esc(name)}">${options.map(([v, t]) =>
  `<button type="button" data-v="${esc(v)}" aria-pressed="${v === value}">${esc(t)}</button>`).join("")}</div>`;
const info = (id, text) => `<span class="info"><button type="button" aria-label="More information" aria-describedby="${id}">i</button><span role="tooltip" id="${id}">${esc(text)}</span></span>`;
const concernChip = (c, label) => `<span class="chip txt ${hcls(c)}">${label ? esc(label) + " " : ""}${c == null ? "insufficient" : fmtConcern(c)}</span>`;
const empty = (text) => `<p class="empty">${esc(text)}</p>`;
const coveredAreas = () => new Set(Object.values(CAT || {}).map((v) => v.area));
let tipN = 0;
const tipWord = (word, text) => { const id = `tw${++tipN}`; return `<span class="info"><button type="button" class="tword" aria-describedby="${id}">${esc(word)}</button><span role="tooltip" id="${id}">${esc(text)}</span></span>`; };
const trustList = (items) => `<ul class="trust">${items.map(([h, t]) => `<li>${icon("check")}<div><b>${esc(h)}</b><span>${esc(t)}</span></div></li>`).join("")}</ul><p class="src">${esc(TRUST_SRC)}</p>`;

/* ---------- shell: identity strip, sidebar, band, footer ---------- */
const NAV = [
  ["Assurance", [["overview", "Overview", "#/"], ["entities", "Entities", "#/entities"], ["indicators", "Indicators", "#/indicators"]]],
  ["Evidence", [["review-packs", "Review packs", "#/review-packs"], ["audit", "Audit & lineage", "#/audit"]]],
  ["Assessment quality", [["validation", "Validation", "#/validation"], ["method", "Method", "#/method"]]],
  [null, [["about", "About", "#/about"]]],
];
const teamWithId = () => `${SITE.team}${SITE.teamId ? ` (ID ${SITE.teamId})` : ""}`;
function renderShell() {
  $("idstrip").textContent = `${SITE.event} · ${SITE.psId} · ${teamWithId()} · ${SITE.institution}`;
  $("brand").innerHTML = `<a class="wordmark" href="#/">${esc(SITE.product)}</a>
    <p class="sub">${esc(SITE.psId)} · ${esc(SITE.psOwner)}</p><span class="badge">Prototype</span>
    <button class="btn sm closebtn" type="button" id="closeNav" aria-label="Close navigation">${icon("close")}</button>`;
  $("nav").innerHTML = NAV.map(([label, items], gi) => `<div class="navgroup">${label ? `<p class="label" id="ng${gi}">${esc(label)}</p>` : ""}
    <ul${label ? ` aria-labelledby="ng${gi}"` : ""}>${items.map(([k, t, h]) => `<li><a href="${h}" data-nav="${k}">${esc(t)}</a></li>`).join("")}</ul></div>`).join("");
  $("sidemeta").textContent = "Offline · Read-only · Air-gapped";
  renderFooter();
}
function renderFooter() {
  const m = META;
  $("foot").innerHTML = `<div class="wrap"><div class="cols">
    <div><h2 id="f1">About</h2><p>${esc(SITE.product)} (${esc(SITE.longName)}). ${esc(SITE.tagline)}.
      Built for ${esc(SITE.psId)}, “${esc(SITE.psTitle)}”, ${esc(SITE.psOwner)}.</p></div>
    <div><h2 id="f2">Team</h2><ul><li>© 2026 ${esc(SITE.team)}</li>${SITE.teamId ? `<li>Team ID ${esc(SITE.teamId)}</li>` : ""}
      <li>${esc(SITE.institution)}</li><li>${esc(SITE.event)}</li></ul></div>
    <div><h2 id="f3">Data &amp; method</h2><ul><li>${esc(SITE.data)}</li>
      <li>MITRE ATT&amp;CK Enterprise v${esc(m ? m.attack : "19.2")}</li>
      <li>Engine ${esc(m ? m.engine : "–")} · catalogue ${esc(m ? m.catalogue_version : "–")}</li>
      <li>Data as of ${esc(m ? fmtPeriod(m.latest) : "–")}</li></ul></div></div>
    <p class="bottom">${esc(SITE.disclosure)}</p></div>`;
}
function setNav(key) {
  document.querySelectorAll("#nav a").forEach((a) => (a.dataset.nav === key ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
}
const crumbsHtml = (parts) => `<nav class="crumbs" aria-label="Breadcrumb">${parts.map(([t, h]) => (h ? `<a href="${h}">${esc(t)}</a>` : `<span>${esc(t)}</span>`)).join('<span aria-hidden="true">›</span>')}</nav>`;
const bstats = (stats) => `<dl class="bstats">${stats.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>`;
/* one call per view: band (breadcrumb, title, description, hero/stats), page title, print header/footer, body */
function render(o, body) {
  document.title = `${o.page} · ${SITE.product} — ${SITE.psId}`;
  setNav(o.nav);
  $("band").innerHTML = `${crumbsHtml(o.crumbs)}<h1>${o.titleHtml || esc(o.title)}</h1>${o.sub ? `<p class="sub2">${esc(o.sub)}</p>` : ""}
    ${o.desc ? `<p class="desc">${esc(o.desc)}</p>` : ""}
    ${o.hero ? `<div class="hero"><div class="fig"><span class="big">${o.hero[0]}</span><span class="label">${esc(o.hero[1])}</span></div>${bstats(o.stats || [])}</div>` : o.stats ? bstats(o.stats) : ""}
    ${o.actions ? `<div class="bandactions">${o.actions}</div>` : ""}`;
  const asOf = META ? fmtPeriod(META.latest) : "–";
  $app.innerHTML = `<div class="print-only print-head"><p class="label">${esc(SITE.product)} · ${esc(SITE.longName)} · ${esc(SITE.psId)}</p><h1>${o.titleHtml || esc(o.title)}</h1>
      ${o.sub ? `<p>${esc(o.sub)}</p>` : ""}${o.stats ? `<p>${o.stats.map(([k, v]) => `${esc(k)}: ${v}`).join(" · ")}</p>` : ""}</div>
    ${body}
    <div class="print-only print-foot">${esc(SITE.product)} · ${esc(teamWithId())} · ${esc(SITE.psId)} · Data as of ${esc(asOf)} · Printed from ${esc(location.hash || "#/")}<br>${esc(SITE.disclosure)}</div>`;
  bindAll();
  announce(`${o.page} loaded`);
}
function skeleton() {
  $("band").innerHTML = `<div class="sk" style="width:180px;height:20px;margin-bottom:8px"></div><div class="sk" style="width:min(520px,80%);height:36px"></div>
    <div class="sk" style="width:min(640px,90%);height:24px;margin-top:8px"></div>`;
  $app.innerHTML = `<div class="grid g4">${'<div class="sk" style="height:120px"></div>'.repeat(4)}</div>
    <div class="sk section" style="height:480px"></div>`;
}
function errorView(err) {
  const offline = err && err.offline;
  document.title = `${offline ? "Unavailable" : "Not found"} · ${SITE.product} — ${SITE.psId}`;
  $("band").innerHTML = `${crumbsHtml([["Overview", "#/"]])}<h1>${offline ? "Can’t reach the SOCRIX API" : "This view could not be loaded"}</h1>`;
  $app.innerHTML = `<div class="notice" role="alert"><h2>${offline ? "The dashboard server is not running" : "Nothing to show here"}</h2>
    <p>${offline ? "Can’t reach the SOCRIX API. Start it with <code>socrix serve</code>, then reload this page." : esc(err && err.message)}</p>
    <p><a href="#/">Back to the overview</a></p></div>`;
}

/* ---------- interaction wiring ---------- */
function bindAll() {
  document.querySelectorAll("tr[data-href]").forEach((tr) => {
    if (tr.dataset.bound) return;
    tr.dataset.bound = "1"; tr.tabIndex = 0; tr.setAttribute("role", "link");
    tr.addEventListener("click", (ev) => { if (!ev.target.closest("a,button")) location.hash = tr.dataset.href; });
    tr.addEventListener("keydown", (ev) => { if ((ev.key === "Enter" || ev.key === " ") && ev.target === tr) { ev.preventDefault(); location.hash = tr.dataset.href; } });
  });
  document.querySelectorAll(".chart").forEach(bindChart);
}
function onSeg(root, fn) {
  root.querySelectorAll("[data-seg]").forEach((g) => g.addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-v]"); if (!b) return;
    g.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    fn(g.dataset.seg, b.dataset.v);
  }));
}

/* sortable table: cols = [{key, label, num, sort:false, val(r), cell(r), cls}] */
function tableHtml(cols, rows, st, opts = {}) {
  const head = cols.map((c) => {
    const on = st && st.sort === c.key, cls = [c.num ? "num" : "", c.sort === false || !st ? "" : "sort", c.cls || ""].join(" ").trim();
    if (c.sort === false || !st) return `<th scope="col"${cls ? ` class="${cls}"` : ""}>${esc(c.label)}</th>`;
    return `<th scope="col" class="${cls}"${on ? ` aria-sort="${st.dir === "asc" ? "ascending" : "descending"}"` : ""}><button type="button" data-sort="${c.key}">${esc(c.label)}<span class="arr" aria-hidden="true">${on ? (st.dir === "asc" ? "↑" : "↓") : ""}</span></button></th>`;
  }).join("");
  let rs = rows.slice();
  if (st && st.sort) {
    const c = cols.find((x) => x.key === st.sort), v = c.val || ((r) => r[c.key]);
    rs.sort((a, b) => { const x = v(a), y = v(b); const r = x == null ? 1 : y == null ? -1 : typeof x === "string" ? x.localeCompare(y, "en", { numeric: true }) : x - y; return st.dir === "asc" ? r : -r; });
  }
  const body = rs.length ? rs.map((r) => `<tr${opts.href ? ` class="click" data-href="${opts.href(r)}"` : ""}>${cols.map((c) => `<td${c.num ? ' class="num"' : ""}>${c.cell ? c.cell(r) : esc(r[c.key])}</td>`).join("")}</tr>`).join("")
    : `<tr><td colspan="${cols.length}">${empty(opts.empty || "Nothing to show.")}</td></tr>`;
  const tcls = [opts.cls, cols.length > 4 ? "wide" : ""].filter(Boolean).join(" ");
  return `<table${tcls ? ` class="${tcls}"` : ""}>${opts.caption ? `<caption class="sr-only">${esc(opts.caption)}</caption>` : ""}<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}
function mountTable(el, cols, rows, st, opts, onChange) {
  const draw = () => { el.innerHTML = tableHtml(cols, rows(), st, opts); bindAll(); };
  el.addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-sort]"); if (!b) return;
    const k = b.dataset.sort, c = cols.find((x) => x.key === k);
    st.dir = st.sort === k ? (st.dir === "asc" ? "desc" : "asc") : (c.num ? "desc" : "asc"); st.sort = k;
    draw(); onChange && onChange(); const nb = el.querySelector(`button[data-sort="${k}"]`); nb && nb.focus();
  });
  draw();
  return draw;
}

/* ---------- charts: inline SVG, one shared style, tooltip on hover and focus ---------- */
function bindChart(ch) {
  if (ch.dataset.bound) return;
  ch.dataset.bound = "1";
  const tip = document.createElement("div"); tip.className = "ctip"; tip.hidden = true; tip.setAttribute("aria-hidden", "true"); ch.appendChild(tip);
  const show = (el) => {
    const t = el.getAttribute("aria-label"); if (!t) return;
    const cr = ch.getBoundingClientRect(), r = el.getBoundingClientRect();
    tip.textContent = t; tip.hidden = false;
    const w = tip.offsetWidth, cx = r.left + r.width / 2 - cr.left;
    tip.style.left = Math.min(Math.max(cx, w / 2), cr.width - w / 2) + "px";
    tip.style.top = (r.top - cr.top) + "px";
  };
  const hide = () => { tip.hidden = true; };
  ch.querySelectorAll("circle[aria-label]").forEach((c) => {
    c.addEventListener("mouseenter", () => show(c)); c.addEventListener("focus", () => show(c));
    c.addEventListener("mouseleave", hide); c.addEventListener("blur", hide);
  });
}
function stripPlot(dist, selfId, iid, higherWorse, engineMedian) {
  const W = 560, H = 132, P = 32;
  const vals = dist.map((d) => d.value).filter((v) => v != null);
  if (!vals.length) return empty("No peer distribution for this period.");
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { hi = lo + 1; }
  const x = (v) => P + ((v - lo) / (hi - lo)) * (W - 2 * P);
  const sorted = [...vals].sort((a, b) => a - b);
  // use the engine's baseline median (same sector/size, leave-one-out) so the chart matches the explanation text
  const med = engineMedian != null ? engineMedian : sorted[Math.floor((sorted.length - 1) / 2)] / 2 + sorted[Math.ceil((sorted.length - 1) / 2)] / 2;
  lo = Math.min(lo, med); hi = Math.max(hi, med);
  const pts = dist.filter((d) => d.value != null).map((d, i) => ({ ...d, self: d.entity_id === selfId, i }));
  const dots = pts.sort((a, b) => a.self - b.self).map((d) => {
    const y = d.self ? 60 : 50 + ((d.i * 37) % 21);
    const lab = d.self ? `<text x="${x(d.value).toFixed(1)}" y="${y - 14}" text-anchor="middle" class="selflab">${esc(selfId)}</text>` : "";
    return lab + `<circle cx="${x(d.value).toFixed(1)}" cy="${y}" r="${d.self ? 7 : 5}" class="${d.self ? "self" : "peer"}" tabindex="0" role="img" aria-label="${esc(d.entity_id)}: ${esc(fmtVal(iid, d.value))} (concern ${fmtIdx(d.concern)})"></circle>`;
  }).join("");
  const alt = `Peer distribution: ${selfId} ${fmtVal(iid, dist.find((d) => d.entity_id === selfId)?.value)} vs baseline median ${fmtVal(iid, med)}; ${dist.length} entities from ${fmtVal(iid, lo)} to ${fmtVal(iid, hi)}`;
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" width="100%" role="group" aria-label="${esc(alt)}">
    <line x1="${P}" x2="${W - P}" y1="92" y2="92" class="axis"/>
    <line x1="${x(med).toFixed(1)}" x2="${x(med).toFixed(1)}" y1="24" y2="92" class="med"/>
    <text x="${x(med).toFixed(1)}" y="16" text-anchor="middle">baseline median ${esc(fmtVal(iid, med))}</text>
    ${dots}
    <text x="${P}" y="110">${esc(fmtVal(iid, lo))}</text><text x="${W - P}" y="110" text-anchor="end">${esc(fmtVal(iid, hi))}</text>
    <text x="${W / 2}" y="128" text-anchor="middle">${higherWorse ? "Higher values are worse →" : "← Lower values are worse"}</text></svg>
    <div class="clegend"><span><i style="background:var(--bad)"></i>${esc(selfId)} (this entity)</span><span><i style="background:var(--primary);opacity:.55"></i>Other entities</span><span><i class="dash"></i>Baseline median</span></div></div>`;
}
function lineChart(points, key, opts = {}) {
  const W = opts.w || 320, H = opts.h || 150, PL = 32, PR = 16, PT = 12, PB = 28;
  const pts = points.filter((p) => p[key] != null);
  if (pts.length < 1) return empty("No history for this indicator yet.");
  const ys = pts.map((p) => p[key]);
  const lo = opts.min ?? Math.min(...ys), hi = opts.max ?? Math.max(...ys, lo + 1e-9);
  const x = (i) => PL + (pts.length === 1 ? (W - PL - PR) / 2 : (i / (pts.length - 1)) * (W - PL - PR));
  const y = (v) => H - PB - ((v - lo) / (hi - lo || 1)) * (H - PT - PB);
  const f = opts.fmt || fmtIdx;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const ticks = (opts.ticks || [lo, hi]).map((t) => `<line x1="${PL}" x2="${W - PR}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="grid"/>
    <text x="${PL - 6}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end">${esc(Math.round(t))}</text>`).join("");
  const thr = opts.thr != null ? `<line x1="${PL}" x2="${W - PR}" y1="${y(opts.thr).toFixed(1)}" y2="${y(opts.thr).toFixed(1)}" class="thr"/>` : "";
  const dots = pts.map((p, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(p[key]).toFixed(1)}" r="4.5" class="pt" tabindex="0" role="img" aria-label="${esc(fmtPeriod(p.period))}: ${esc(f(p[key]))}"></circle>
    <text x="${x(i).toFixed(1)}" y="${H - 6}" text-anchor="middle">${esc(fmtPeriod(p.period))}</text>`).join("");
  const alt = (opts.label || "Trend") + ": " + pts.map((p) => `${fmtPeriod(p.period)} ${f(p[key])}`).join(", ");
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" width="100%" role="group" aria-label="${esc(alt)}">${ticks}${thr}<path d="${d}" class="line"/>${dots}</svg>
    ${opts.legend ? `<div class="clegend"><span><i style="background:var(--primary)"></i>${esc(opts.legend)}</span>${opts.thr != null ? `<span><i class="dash" style="color:var(--bad)"></i>Finding threshold (${opts.thr})</span>` : ""}</div>` : ""}</div>`;
}

/* ---------- shared components ---------- */
const concernKey = () => `<div class="key" role="group" aria-label="Concern scale"><span class="klabel">Concern</span>
  <span class="kstep"><i style="background:var(--c0);box-shadow:inset 0 0 0 1px var(--border)"></i><span class="kt">0–19</span></span><span class="kstep"><i style="background:var(--c1)"></i><span class="kt">20–34</span></span>
  <span class="kstep"><i style="background:var(--c2)"></i><span class="kt">35–49</span></span><span class="kstep"><i style="background:var(--c3)"></i><b class="kt">50–74 finding</b></span>
  <span class="kstep last"><i style="background:var(--c4)"></i><b class="kt">75–100 severe finding</b></span><span class="kna"><i style="background:var(--na)"></i>not assessed</span></div>`;
const findingChips = (codes, e) => codes.length ? codes.map((f) => e ? `<a class="chip bad" href="#/e/${enc(e)}/i/${enc(f)}">${esc(f)}</a>` : `<span class="chip bad">${esc(f)}</span>`).join("")
  : '<span class="chip ok txt">none</span>';
function packCsv(e, pack) {                   // same columns as /api/entity/{e}/review-pack.csv (static report has no server)
  const q = (v) => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v ?? "");
  const rows = [["entity_id", "alert_id", "reason", "concern", "reviewer_verdict", "reviewer_notes"]];
  pack.items.forEach((it) => rows.push([e, it.alert_id, it.reason, it.concern ?? "", "", ""]));
  (pack.checklist || []).forEach((ck) => ck.items.forEach((item) => rows.push([e, item, `checklist:${ck.indicator}`, "", "", ""])));
  return rows.map((r) => r.map(q).join(",")).join("\r\n") + "\r\n";
}
function packHtml(e, pack, ctl) {
  const dl = STATIC ? `<button class="btn noprint" type="button" data-csv="${esc(e)}">${icon("download")}Download CSV</button>`
    : `<a class="btn noprint" href="/api/entity/${enc(e)}/review-pack.csv" download>${icon("download")}Download CSV</a>`;
  const items = pack.items.length ? `<div class="scroll"><table><caption class="sr-only">Review pack for ${esc(e)}</caption><thead><tr><th scope="col">Alert</th><th scope="col">Why selected</th><th scope="col" class="num">Concern</th></tr></thead><tbody>
      ${pack.items.map((it) => `<tr class="click" data-href="#/case/${enc(it.alert_id)}"><td class="id">${esc(it.alert_id)}</td>
        <td>${it.reason === "random-control" ? '<span class="chip txt">Random control</span>' : `<span class="chip bad">${esc(it.reason.replace("targeted:", ""))}</span> <span class="note hide-sm">${esc(indName(it.reason.replace("targeted:", "")))}</span>`}</td>
        <td class="num">${it.concern == null ? "–" : fmtIdx(it.concern)}</td></tr>`).join("")}</tbody></table></div>`
    : empty("No cases selected: this entity has no findings and no control sample for this period.");
  return `<div class="card"><div class="cardhead"><h2>Review pack · ${fmtInt(pack.items.length)} cases</h2>${dl}</div>
      <p class="note">${fmtInt(pack.targeted)} targeted at findings, ${fmtInt(pack.control)} random controls, so reviewers also check the engine’s blind spots. Record a verdict per case in the CSV.</p>
      ${items}
      ${(pack.checklist || []).map((c) => `<h3 class="section">Checklist · <span class="id">${esc(c.indicator)}</span> ${esc(c.name)}</h3><div>${c.items.map((v) => `<span class="chip">${esc(v)}</span>`).join("")}</div>`).join("")}
    </div>
    <div class="card"><h2>Detectors with the weakest handling</h2>
      <p class="note">Share of each detector’s alerts closed with no investigation or no enrichment. Points at the rules whose alerts analysts skip.</p>
      ${ctl.length ? `<div class="scroll"><table><caption class="sr-only">Detectors with the weakest handling</caption><thead><tr><th scope="col">Detector</th><th scope="col" class="num">Alerts</th><th scope="col" class="num">Weak handling</th><th scope="col" class="num">Share</th></tr></thead><tbody>
      ${ctl.map((c) => `<tr><td class="id">${esc(c.detector_id)}</td><td class="num">${fmtInt(c.alerts)}</td><td class="num">${fmtInt(c.weak_handling)}</td><td class="num">${fmtPct(c.share)}</td></tr>`).join("")}
      </tbody></table></div>` : empty("No detector handled its alerts noticeably worse than the others.")}</div>`;
}
function bindCsv(root, e, pack) {
  root.querySelectorAll("[data-csv]").forEach((b) => b.addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([packCsv(e, pack)], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = `socrix_review_pack_${e}.csv`; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000); announce("Review pack CSV downloaded");
  }));
}

/* ---------- D0 overview ---------- */
async function viewOverview(q) {
  const [ov, bench, au] = await Promise.all([get("/api/overview"), get("/api/benchmark").catch(() => null), get("/api/audit/verify").catch(() => null)]);
  const ents = ov.entities, m = ov.meta;
  const findings = ents.reduce((s, e) => s + e.findings.length, 0);
  const withF = ents.filter((e) => e.findings.length).length;
  const st = { sector: q.get("sector") || "all", sort: q.get("sort") || "sai" };
  const sectors = [...new Set(ents.map((e) => e.sector))];
  const queue = ents.filter((e) => e.findings.length).slice(0, 5);
  const bySector = sectors.map((s) => { const g = ents.filter((e) => e.sector === s); const top = g[0];
    return { s, n: g.length, withF: g.filter((e) => e.findings.length).length, f: g.reduce((a, e) => a + e.findings.length, 0), top }; });
  render({
    page: "Overview", nav: "overview", crumbs: [["Assurance"], ["Overview"]],
    title: "National SOC assurance overview",
    desc: `Where should NCIIPC look first? ${ents.length} critical-sector entities, assessed from their submitted SOC records for ${fmtPeriod(m.latest)}.`,
    hero: [fmtInt(findings), `Findings (concern ≥ ${m.finding_threshold})`],
    stats: [["Entities assessed", fmtInt(ents.length)], ["Entities with findings", fmtInt(withF)],
      ["Planted weaknesses detected", bench ? `<a href="#/validation">${fmtInt(bench.detected)}/${fmtInt(bench.planted)}</a>` : "–"],
      ["Audit chain", au ? `<span class="status ${au.intact ? "ok" : "bad"}">${au.intact ? "Intact" : "Broken"}</span>` : "–"]],
  }, `
    <ul class="caps" aria-label="Capabilities">
      <li>${icon("explain")}<span><b>Explainable</b> — every finding in one sentence</span></li>
      <li>${icon("trace")}<span><b>Traceable</b> — drill down to the source row</span></li>
      <li>${icon("chain")}<span><b>Tamper-evident</b> audit trail</span></li>
      <li>${icon("offline")}<span><b>Runs fully offline</b></span></li></ul>
    <div class="grid g2 section">
      <section class="card" aria-labelledby="pq"><div class="cardhead"><h2 id="pq">Priority review queue</h2><a href="#/entities?f=1">All entities with findings</a></div>
        <p class="note">Highest SOC Assurance Index first (higher means more concern). Open an entity for its findings and review pack.</p>
        <div class="scroll"><table class="queue"><caption class="sr-only">Priority review queue</caption><thead><tr><th scope="col" class="num">#</th><th scope="col">Entity</th><th scope="col">Findings</th><th scope="col" class="num">SAI</th></tr></thead><tbody>
        ${queue.map((e, k) => `<tr class="click" data-href="#/e/${enc(e.entity_id)}"><td class="num note">${k + 1}</td>
          <td><span class="id"><b>${esc(e.entity_id)}</b></span><span class="sub">${esc(e.sector)} · ${esc(e.size_band)}</span></td>
          <td class="what">${e.findings.map((f) => `${esc(indName(f))} (<span class="id">${esc(f)}</span>)`).join("; ")}</td>
          <td class="num"><b>${fmtIdx(e.sai)}</b><span class="sub">rank ${e.rank_min}–${e.rank_max}</span></td></tr>`).join("")}</tbody></table></div>
      </section>
      <section class="card" aria-labelledby="ss"><h2 id="ss">By sector</h2>
        <div class="scroll"><table class="sector"><caption class="sr-only">Findings by sector</caption><thead><tr><th scope="col">Sector</th><th scope="col" class="num">Entities</th><th scope="col" class="num">With findings</th><th scope="col" class="num">Findings</th><th scope="col" class="hide-sm">Highest SAI</th></tr></thead><tbody>
        ${bySector.map((r) => `<tr class="click" data-href="#/entities?sector=${enc(r.s)}"><td><b>${esc(r.s)}</b></td><td class="num">${fmtInt(r.n)}</td><td class="num">${fmtInt(r.withF)}</td><td class="num">${fmtInt(r.f)}</td>
          <td class="hide-sm"><span class="id">${esc(r.top.entity_id)}</span> <span class="note tnum">${fmtIdx(r.top.sai)}</span></td></tr>`).join("")}</tbody></table></div>
        <h3 class="section">Entities with a finding, by capability area</h3>
        ${AREAS.map((a) => { const n = ents.filter((e) => e.findings.some((f) => CAT[f] && CAT[f].area === a)).length;
          if (!coveredAreas().has(a)) return `<div class="arow"><span>${esc(a)}</span><span class="v nyc">Not yet covered</span><div class="track na" role="img" aria-label="${esc(a)}: not yet covered by an indicator"></div></div>`;
          return `<div class="arow"><span>${esc(a)}</span><span class="v">${n}</span><div class="track" role="img" aria-label="${esc(a)}: ${n} of ${ents.length} entities"><i style="width:${(100 * n) / ents.length}%;background:var(--primary)"></i></div></div>`; }).join("")}
        ${m.counts ? `<p class="note section">Evidence base: ${fmtInt(m.counts.alerts)} alerts and ${fmtInt(m.counts.cases)} cases from ${m.periods.length} monthly submissions per entity (${esc(fmtPeriod(m.periods[0]))} – ${esc(fmtPeriod(m.latest))}).</p>` : ""}
      </section>
    </div>
    <section class="card section" aria-labelledby="hm">
      <div class="cardhead"><h2 id="hm">Capability-area concern${info("rtip", "Rank range = best and worst rank under weighting uncertainty. Overlapping ranges mean the ordering is not decisive: read the findings, not just the rank.")}</h2>
        <div class="toolbar" style="margin:0">${segmented("sector", "Sector", [["all", "All"], ...sectors.map((s) => [s, s])], st.sector)}
          <span class="note" aria-hidden="true">Sort by</span>${segmented("sort", "Sort by", [["sai", "SAI"], ["name", "Name"], ["findings", "Findings"]], st.sort)}</div></div>
      ${concernKey()}
      <div class="scroll" id="heat"></div>
      <details class="section"><summary>About rank ranges</summary><div>Rank range = best/worst rank under weighting uncertainty (${fmtInt(m.uncertainty_draws)} Dirichlet draws) and aggregation exponent p ∈ {1, 2, 3, 6}. Overlapping ranges mean the ordering is not decisive — read the findings, not just the rank.</div></details>
    </section>`);
  const draw = () => {
    let rows = ents.filter((e) => st.sector === "all" || e.sector === st.sector);
    if (st.sort === "name") rows = rows.slice().sort((a, b) => a.entity_id.localeCompare(b.entity_id));
    else if (st.sort === "findings") rows = rows.slice().sort((a, b) => b.findings.length - a.findings.length || (b.sai || 0) - (a.sai || 0));
    $("heat").innerHTML = `<table class="heat"><caption class="sr-only">Concern by capability area for each entity</caption><thead><tr><th scope="col">Entity</th><th scope="col" class="num">SAI · rank</th>${AREAS.map((a) => `<th scope="col" title="${esc(a)}"><abbr title="${esc(a)}">${esc(a.split(" ")[0])}</abbr></th>`).join("")}<th scope="col" class="l">Findings</th><th scope="col" class="num">Coverage</th></tr></thead><tbody>
      ${rows.map((e) => `<tr class="click" data-href="#/e/${enc(e.entity_id)}">
        <td><span class="id"><b>${esc(e.entity_id)}</b></span><span class="sub">${esc(e.sector)} · ${esc(e.size_band)}</span></td>
        <td class="num"><b>${fmtIdx(e.sai)}</b><span class="sub">rank ${e.rank_min}–${e.rank_max}</span></td>
        ${AREAS.map((a) => { const c = e.areas[a]; return `<td class="cell ${hcls(c)}" title="${esc(a)}: ${c == null ? (coveredAreas().has(a) ? "not assessed (insufficient evidence)" : "not yet covered (planned indicator area)") : "concern " + fmtIdx(c)}">${c == null ? '<span class="sr-only">not assessed</span>' : fmtConcern(c)}</td>`; }).join("")}
        <td class="l">${findingChips(e.findings)}</td><td class="num">${e.coverage}/8</td></tr>`).join("")}</tbody></table>`;
    bindAll();
  };
  draw();
  onSeg($app, (k, v) => { st[k] = v; draw(); replaceQuery("/", { sector: st.sector === "all" ? "" : st.sector, sort: st.sort === "sai" ? "" : st.sort }); });
}

/* ---------- entities ---------- */
async function viewEntities(q) {
  const ov = await get("/api/overview");
  const ents = ov.entities;
  const sectors = [...new Set(ents.map((e) => e.sector))];
  const st = { sector: q.get("sector") || "all", f: q.get("f") === "1", q: q.get("q") || "", sort: q.get("sort") || "sai", dir: q.get("dir") || "desc" };
  render({
    page: "Entities", nav: "entities", crumbs: [["Assurance"], ["Entities"]], title: "Entities",
    desc: `Every assessed critical-sector entity for ${fmtPeriod(ov.meta.latest)}. Search, filter by sector and open an entity for its findings and evidence.`,
    stats: [["Entities", fmtInt(ents.length)], ...sectors.map((s) => [s, fmtInt(ents.filter((e) => e.sector === s).length)]), ["With findings", fmtInt(ents.filter((e) => e.findings.length).length)]],
  }, `<section class="card" aria-labelledby="et"><h2 id="et" class="sr-only">Entity list</h2>
      <div class="toolbar"><label class="field grow"><span>Search</span><input type="search" id="eq" placeholder="Entity ID, e.g. PWR-03" value="${esc(st.q)}"></label>
        <div class="field"><span id="secl">Sector</span>${segmented("sector", "Sector", [["all", "All"], ...sectors.map((s) => [s, s])], st.sector)}</div>
        <label class="check"><input type="checkbox" id="ef"${st.f ? " checked" : ""}>Only entities with findings</label></div>
      <p class="note" id="ecount" aria-live="polite"></p>
      <div class="scroll" id="etable"></div></section>`);
  const cols = [
    { key: "entity_id", label: "Entity", cell: (e) => `<span class="id"><b>${esc(e.entity_id)}</b></span>` },
    { key: "sector", label: "Sector · size", cell: (e) => `${esc(e.sector)} <span class="note">· ${esc(e.size_band)}</span>` },
    { key: "sai", label: "SAI", num: true, cell: (e) => `<b>${fmtIdx(e.sai)}</b>` },
    { key: "rank", label: "Rank range", num: true, val: (e) => e.rank_min, cell: (e) => `${e.rank_min}–${e.rank_max}` },
    { key: "findings", label: "Findings", val: (e) => e.findings.length, cell: (e) => `<span class="tnum" style="display:inline-block;min-width:20px">${e.findings.length}</span> ${e.findings.length ? findingChips(e.findings) : ""}` },
    { key: "coverage", label: "Coverage", num: true, cell: (e) => `${e.coverage}/8` },
  ];
  const rows = () => {
    const needle = st.q.trim().toLowerCase();
    const r = ents.filter((e) => (st.sector === "all" || e.sector === st.sector) && (!st.f || e.findings.length) && (!needle || e.entity_id.toLowerCase().includes(needle) || e.sector.toLowerCase().includes(needle)));
    $("ecount").textContent = `Showing ${r.length} of ${ents.length} entities`;
    return r;
  };
  const sync = () => replaceQuery("/entities", { sector: st.sector === "all" ? "" : st.sector, f: st.f ? "1" : "", q: st.q, sort: st.sort === "sai" ? "" : st.sort, dir: st.dir === "desc" ? "" : st.dir });
  const draw = mountTable($("etable"), cols, rows, st, { href: (e) => `#/e/${enc(e.entity_id)}`, caption: "Entities", empty: "No entities match these filters. Clear the search or choose All sectors." }, sync);
  $("eq").addEventListener("input", (ev) => { st.q = ev.target.value; draw(); sync(); });
  $("ef").addEventListener("change", (ev) => { st.f = ev.target.checked; draw(); sync(); });
  onSeg($app, (k, v) => { st[k] = v; draw(); sync(); });
}

/* ---------- indicators ---------- */
async function viewIndicators() {
  const [m, ov] = await Promise.all([get("/api/meta"), get("/api/overview")]);
  const flagged = {};
  ov.entities.forEach((e) => e.findings.forEach((f) => (flagged[f] = flagged[f] || []).push(e.entity_id)));
  const rows = Object.entries(m.indicators).map(([code, v]) => ({ code, ...v, flagged: flagged[code] || [] }));
  const areas = new Set(rows.map((r) => r.area));
  const st = { sort: "code", dir: "asc" };
  render({
    page: "Indicators", nav: "indicators", crumbs: [["Assurance"], ["Indicators"]], title: "Indicator catalogue",
    desc: "The 12 indicators SOCRIX computes from submitted records, each mapped to a capability area in the problem statement and judged against peers or policy.",
    stats: [["Indicators", fmtInt(rows.length)], ["Capability areas covered", `${areas.size} of ${AREAS.length}`], ["Flagged this period", fmtInt(rows.filter((r) => r.flagged.length).length)], ["Catalogue", `<span class="id">${esc(m.catalogue_version)}</span>`]],
  }, `<section class="card" aria-labelledby="ic"><h2 id="ic">Catalogue · ${esc(fmtPeriod(m.latest))}</h2>
      <p class="note">“Entities flagged” counts entities where the indicator is a finding (concern ≥ ${m.finding_threshold}) in ${esc(fmtPeriod(m.latest))}. Select an entity code to open the indicator for that entity.</p>
      <div class="scroll" id="itable"></div></section>`);
  mountTable($("itable"), [
    { key: "code", label: "Code", cell: (r) => `<span class="id">${esc(r.code)}</span>` },
    { key: "name", label: "Indicator", cell: (r) => `${esc(r.name)}<span class="sub">${esc(cap(String(r.gap || "").replace("_", " ")))} gap · ${esc(r.unit)}</span>` },
    { key: "area", label: "Capability area" },
    { key: "higher_is_worse", label: "Worse when", val: (r) => (r.higher_is_worse ? 1 : 0), cell: (r) => (r.higher_is_worse ? "Higher" : "Lower") },
    { key: "min_n", label: "Min n", num: true, cell: (r) => fmtInt(r.min_n) },
    { key: "track", label: "Track", cell: (r) => esc(cap(r.track)) },
    { key: "brief", label: "Brief ref" },
    { key: "flagged", label: "Entities flagged", val: (r) => r.flagged.length, cell: (r) => `<span class="tnum" style="display:inline-block;min-width:20px">${r.flagged.length}</span> ${r.flagged.map((e) => `<a class="chip bad" href="#/e/${enc(e)}/i/${enc(r.code)}">${esc(e)}</a>`).join("")}` },
  ], () => rows, st, { caption: "Indicator catalogue" });
}

/* ---------- D1 entity ---------- */
async function viewEntity(e) {
  const x = await get(`/api/entity/${enc(e)}`);
  const inds = Object.values(x.indicators);
  const fnd = inds.filter((i) => i.status === "assessed" && i.concern >= 50).sort((a, b) => b.concern - a.concern);
  const near = inds.filter((i) => i.status === "assessed" && i.concern >= 35 && i.concern < 50).sort((a, b) => b.concern - a.concern);
  const areaRows = AREAS.map((a) => { const c = x.areas[a]; return `<div class="arow"><span>${esc(a)}</span><span class="v">${c == null ? tipWord("n/a", coveredAreas().has(a) ? "Insufficient evidence this period" : "Planned indicator area") : fmtConcern(c)}</span>
    <div class="track${c == null && !coveredAreas().has(a) ? " na" : ""}" role="img" aria-label="${esc(a)}: ${c == null ? (coveredAreas().has(a) ? "not assessed" : "planned indicator area") : "concern " + fmtConcern(c) + " of 100"}"><i style="width:${c == null ? 0 : Math.max(2, c)}%;background:${heat(c)}"></i></div></div>`; }).join("");
  const stats = [["SAI (0–100)", fmtIdx(x.sai)], ["Findings", fmtInt(x.findings.length)], ["Rank range", `${x.rank_min}–${x.rank_max}`], ["P(top 3)", fmtPct(x.p_top3)], ["Coverage", `${x.coverage}/8 areas`]];
  render({
    page: e, nav: "entities", crumbs: [["Entities", "#/entities"], [e]],
    titleHtml: `<span class="id">${esc(e)}</span>`, title: e, sub: `${x.sector} · ${x.size_band}`, stats,
    actions: `<button class="btn" type="button" id="printBtn">${icon("print")}Print / Save as PDF</button><a class="btn" href="#/review-packs/${enc(e)}">Open review pack</a>`,
  }, `
    <div class="grid g3">
      <section class="card" aria-labelledby="fh"><h2 id="fh">Findings — what went wrong, in plain words</h2>
        ${fnd.length ? `<div class="fcards">${fnd.map((i) => `<article class="fcard"><div class="h"><span class="chip">${esc(i.indicator)}</span><h3>${esc(i.name)}</h3>${concernChip(i.concern, "Concern")}</div>
          <p>${esc(i.explanation)}</p>
          <div class="foot2"><a href="#/e/${enc(e)}/i/${enc(i.indicator)}">Peers · History · ${fmtInt(i.evidence_count)} evidence rows →</a><span class="note">${esc(cap(i.track))} track · brief ref ${esc(i.brief)}</span></div></article>`).join("")}</div>`
          : empty("No indicator crossed the finding threshold for this period.")}
        ${near.length ? `<h3 class="section">Near threshold — worth a look, not a finding</h3>
          <p class="note">Concern 35–49: unusual, but within what chance or normal variation can explain. Shown so nothing is hidden.</p>
          <ul class="near">${near.map((i) => `<li><a href="#/e/${enc(e)}/i/${enc(i.indicator)}"><span class="id">${esc(i.indicator)}</span> ${esc(i.name)}</a>${concernChip(i.concern)}</li>`).join("")}</ul>` : ""}
      </section>
      <section class="card" aria-labelledby="ah"><h2 id="ah">Capability areas</h2>${areaRows}
        <h2 class="section">SAI trend</h2>${lineChart(x.trend, "sai", { min: 0, max: 100, thr: 50, ticks: [0, 50, 100], label: "SAI by period", legend: "SAI" })}
      </section>
    </div>
    <section class="card section pbreak" aria-labelledby="ih"><h2 id="ih">All indicators</h2><div class="scroll" id="itable"></div>
      <p class="note section">“Insufficient” means too few records to judge; it is never scored as zero. Rates use the Wilson 95% lower bound, so small samples are treated conservatively.</p></section>
    <div class="grid g2 section pbreak" id="d45"><div class="sk" style="height:480px"></div><div class="sk" style="height:480px"></div></div>`);
  $("printBtn").addEventListener("click", () => window.print());
  mountTable($("itable"), [
    { key: "indicator", label: "Code", cell: (i) => `<span class="id">${esc(i.indicator)}</span>` },
    { key: "name", label: "Indicator", cell: (i) => `${esc(i.name)}<span class="sub">${esc(i.area)}</span>` },
    { key: "n", label: "Count", num: true, cell: (i) => (i.status === "assessed" ? esc(countText(i)) : `<span class="chip warn txt">n=${fmtInt(i.n)}</span>`) },
    { key: "value", label: "Value", num: true, cell: (i) => (i.status === "assessed" ? esc(i.display || fmtVal(i.indicator, i.value)) : "–") },
    { key: "median", label: "Peer median", num: true, cell: (i) => (i.status === "assessed" ? esc(fmtVal(i.indicator, i.median)) : "–") },
    { key: "concern", label: "Concern", num: true, val: (i) => (i.status === "assessed" ? i.concern : null), cell: (i) => concernChip(i.status === "assessed" ? i.concern : null) },
    { key: "track", label: "Track", cell: (i) => esc(cap(i.track || "")) },
  ], () => inds, { sort: "indicator", dir: "asc" }, { href: (i) => `#/e/${enc(e)}/i/${enc(i.indicator)}`, caption: `Indicators for ${e}` });
  const [pack, ctl] = await Promise.all([get(`/api/entity/${enc(e)}/review-pack`), get(`/api/entity/${enc(e)}/controls`)]);
  if (!$("d45")) return;
  $("d45").innerHTML = packHtml(e, pack, ctl);
  bindCsv($("d45"), e, pack);
  bindAll();
}

/* ---------- D2 + D3 indicator & evidence ---------- */
async function viewIndicator(e, iid, offset = 0) {
  const d = await get(`/api/entity/${enc(e)}/indicator/${enc(iid)}`);
  const i = d.detail, m = d.method;
  const assessed = i.status === "assessed";
  render({
    page: `${iid} · ${e}`, nav: "entities", crumbs: [["Entities", "#/entities"], [e, `#/e/${enc(e)}`], [iid]],
    titleHtml: esc(m.name), title: m.name, sub: `${iid} · ${m.area} · ${cap(m.gap.replace("_", " "))} gap · brief ref ${m.brief}`,
    stats: [["Count", esc(countText(i))], ["Value", esc(assessed ? i.display || fmtVal(iid, i.value) : "–")], ["Peer median", esc(fmtVal(iid, i.median))],
      ["Modified z", fmtIdx(i.modz)], ["Concern", assessed ? fmtIdx(i.concern) : "Insufficient evidence"]],
  }, `
    <div class="grid g3">
      <section class="card" aria-labelledby="xh"><h2 id="xh">Explanation</h2><blockquote>${esc(i.explanation || "Too few records to judge this indicator for this period.")}</blockquote>
        <h2 class="section">Where ${esc(e)} sits among comparable peers</h2>${stripPlot(d.distribution, e, iid, m.higher_is_worse, i.median)}
        <details class="section"><summary>How to read this</summary><div>Each dot is one entity this period; the red dot is ${esc(e)}. The dashed line is the median of the comparison baseline (${esc(i.baseline || "–")}), the same number used in the explanation. Distance from the line is measured with the modified z-score, 0.6745·(x − median)/MAD (NIST/SEMATECH); a score of 3.5 maps to concern 50, the finding threshold.</div></details></section>
      <section class="card" aria-labelledby="nh"><h2 id="nh">Numbers</h2><dl class="kv">
        <dt>Status</dt><dd>${esc(cap(i.status))}</dd>
        <dt>Count</dt><dd>${esc(countText(i))}</dd>
        <dt>Value</dt><dd>${esc(i.display || fmtVal(iid, i.value))}</dd>
        <dt>Peer median</dt><dd>${esc(fmtVal(iid, i.median))}</dd>
        <dt>Modified z</dt><dd>${fmtIdx(i.modz)}</dd>
        <dt>Peer concern</dt><dd>${fmtIdx(i.peer_concern)}</dd>
        <dt>Policy concern</dt><dd>${fmtIdx(i.policy_concern)}</dd>
        <dt>Concern</dt><dd><b>${fmtIdx(i.concern)}</b> (${esc(i.track || "–")})</dd>
        ${i.policy_reason ? `<dt>Policy rule</dt><dd>${esc(i.policy_reason)}</dd>` : ""}
        <dt>Unit</dt><dd>${esc(m.unit)}</dd>
        <dt>Minimum n</dt><dd>${fmtInt(m.min_n)}</dd></dl>
        <h2 class="section">History (concern)</h2>${lineChart(d.history, "concern", { min: 0, max: 100, thr: 50, ticks: [0, 50, 100], label: "Concern by period", legend: "Concern" })}</section>
    </div>
    <section class="card section" id="ev" aria-labelledby="evh"><h2 id="evh">Evidence</h2><div class="sk" style="height:360px"></div></section>`);
  const path = `/api/entity/${enc(e)}/indicator/${enc(iid)}/evidence` + (STATIC ? "" : `?offset=${offset}&limit=50`);
  let ev;
  try { ev = await get(path); } catch (err) { $("ev").innerHTML = `<h2 id="evh">Evidence</h2>${empty(err.offline ? "Can’t reach the SOCRIX API. Start it with socrix serve." : err.message)}`; return; }
  if (!$("ev")) return;
  const alertRows = ev.rows.length && ev.rows[0].alert_id;
  const body = !ev.rows.length ? empty("No evidence rows: this indicator was not triggered for this period.") : alertRows
    ? `<div class="scroll tall"><table class="wide"><caption class="sr-only">Evidence rows for ${esc(iid)}</caption><thead><tr><th scope="col">Alert</th><th scope="col">Severity</th><th scope="col">Technique</th><th scope="col">Asset</th><th scope="col">Disposition</th><th scope="col" class="num">Minutes to close</th><th scope="col">Case note</th></tr></thead><tbody>
      ${ev.rows.map((r) => `<tr class="click" data-href="#/case/${enc(r.alert_id)}"><td class="id">${esc(r.alert_id)}</td><td>${esc(cap(r.severity))}</td><td class="id">${esc(r.technique_id)}</td><td class="id">${esc(r.asset_id)}</td><td>${esc(r.disposition)}</td><td class="num">${fmtIdx(r.minutes_to_close)}</td><td class="note">${esc((r.note || "").slice(0, 90))}</td></tr>`).join("")}
      </tbody></table></div>`
    : `<div>${ev.rows.map((r) => `<span class="chip">${esc(r.item)}</span>`).join("")}</div>`;
  const pager = STATIC ? (ev.total > ev.rows.length ? `<p class="note section">This static report shows the first ${fmtInt(ev.rows.length)} of ${fmtInt(ev.total)} rows; the server shows all of them.</p>` : "")
    : `<div class="toolbar section pager">${offset > 0 ? `<a class="btn" href="#/e/${enc(e)}/i/${enc(iid)}/${Math.max(0, offset - 50)}" aria-label="Previous 50 evidence rows">← Previous</a>` : ""}${offset + 50 < ev.total ? `<a class="btn" href="#/e/${enc(e)}/i/${enc(iid)}/${offset + 50}" aria-label="Next 50 evidence rows">Next →</a>` : ""}</div>`;
  $("ev").innerHTML = `<h2 id="evh">Evidence — ${fmtInt(ev.total)} rows behind this number${ev.total ? ` <span class="note">(showing ${fmtInt(offset + 1)}–${fmtInt(offset + ev.rows.length)})</span>` : ""}</h2>${body}${pager}`;
  bindAll();
}

/* ---------- D6 + D7 case & lineage ---------- */
async function viewCase(aid) {
  const [c, l] = await Promise.all([get(`/api/case/${enc(aid)}`), get(`/api/lineage/${enc(aid)}`)]);
  const a = c.alert, e = a.entity_id;
  const cls = (ev) => (ev === "alert closed" ? "closed" : ev === "escalated" ? "esc" : "");
  const t0 = c.timeline.length ? new Date(c.timeline[0].ts) : null;
  const toClose = a.closed_ts ? new Date(a.closed_ts) - new Date(a.created_ts) : null;
  const receipt = l.receipts.filter((r) => r.file === l.record.source_file);
  render({
    page: `Alert ${aid}`, nav: "audit", crumbs: [["Entities", "#/entities"], [e, `#/e/${enc(e)}`], ["Alert"]],
    titleHtml: `<span class="id">${esc(aid)}</span>`, title: aid, sub: `${cap(a.severity)} alert · ${a.technique_id} on ${a.asset_id}`,
    stats: [["Severity", esc(cap(a.severity))], ["Disposition", esc(a.disposition)], ["Detector", `<span class="id">${esc(a.detector_id)}</span>`],
      ["Created", esc(fmtDateTime(a.created_ts))], ["Time to close", toClose == null ? "Open" : esc(fmtDur(toClose))]],
  }, `
    <section class="card" aria-labelledby="wh"><h2 id="wh">Why this alert is in view</h2>
      <p>${c.flagged_by.length ? "Part of finding " + c.flagged_by.map((f) => `<a class="chip bad" href="#/e/${enc(e)}/i/${enc(f)}">${esc(f)}</a> <span class="note">${esc(indName(f))}</span>`).join(" ") : '<span class="chip ok txt">Not part of any finding</span>'}</p>
      ${c.also_in_evidence_of && c.also_in_evidence_of.length ? `<p class="note">Also counted in (below threshold): ${c.also_in_evidence_of.map((f) => `<a class="chip" href="#/e/${enc(e)}/i/${enc(f)}">${esc(f)}</a>`).join("")}</p>` : ""}</section>
    <div class="grid g2 section">
      <section class="card" aria-labelledby="th"><h2 id="th">Timeline</h2><ol class="tl">${c.timeline.map((t, k) => {
        const dt = k && t0 ? new Date(t.ts) - new Date(c.timeline[k - 1].ts) : null;
        return `<li class="${cls(t.event)}"><b>${esc(cap(t.event))}</b>${dt != null ? `<span class="dur">+${esc(fmtDur(dt))}</span>` : ""}<div class="when">${esc(fmtDateTime(t.ts))}</div><div class="note">${esc(t.detail)}</div></li>`; }).join("")}</ol>
        ${c.case ? `<h2 class="section">Case note</h2><blockquote>${esc(c.case.note || "(empty)")}</blockquote><p class="note">Case <span class="id">${esc(c.case.case_id)}</span> · root cause: ${esc(c.case.root_cause_code || "none recorded")}</p>` : empty("No case record was submitted for this alert.")}</section>
      <section class="card" aria-labelledby="alh"><h2 id="alh">Alert</h2><dl class="kv">
        <dt>Severity</dt><dd>${esc(cap(a.severity))}</dd><dt>Technique (ATT&amp;CK)</dt><dd class="id">${esc(a.technique_id)}</dd>
        <dt>Detector</dt><dd class="id">${esc(a.detector_id)}</dd><dt>Asset</dt><dd><span class="id">${esc(a.asset_id)}</span> ${c.asset ? `<span class="note">(${esc(c.asset.criticality)}, ${esc(c.asset.environment)}, ${esc(c.asset.asset_type)})</span>` : ""}</dd>
        <dt>Disposition</dt><dd>${esc(a.disposition)}</dd><dt>Analyst (pseudonym)</dt><dd class="id">${esc(a.analyst)}</dd></dl>
        <h2 class="section">Lineage — where this record came from</h2><dl class="kv">
        <dt>Submission</dt><dd class="id">${esc(l.record.submission_id)}</dd>
        <dt>Source file · row</dt><dd><span class="id">${esc(l.record.source_file)}</span> · row ${fmtInt(l.record.source_row)}</dd>
        ${receipt.map((r) => `<dt>SHA-256 receipt</dt><dd><div class="hash"><code id="sha">${esc(r.sha256)}</code><button class="btn sm" type="button" id="copySha" aria-label="Copy SHA-256 hash">${icon("copy")}Copy</button></div></dd>
          <dt>Received</dt><dd>${esc(fmtDateTime(r.received_at))} · ${fmtInt(r.rows)} rows</dd>`).join("")}
        <dt>Rejected rows in submission</dt><dd>${fmtInt(l.rejected_rows_in_submission)}</dd>
        <dt>Audit chain</dt><dd><span class="status ${l.audit_chain.intact ? "ok" : "bad"}">${l.audit_chain.intact ? "Intact" : "Broken"}</span> · ${fmtInt(l.audit_chain.entries)} entries</dd>
        <dt>Engine · catalogue</dt><dd class="id">${esc(l.engine)} · ${esc(l.catalogue)}</dd></dl></section>
    </div>`);
  const cb = $("copySha");
  if (cb) cb.addEventListener("click", async () => {
    const txt = $("sha").textContent;
    try { await navigator.clipboard.writeText(txt); } catch (err) { const r = document.createRange(); r.selectNodeContents($("sha")); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
    cb.lastChild.textContent = "Copied"; announce("SHA-256 hash copied"); setTimeout(() => { cb.lastChild.textContent = "Copy"; }, 1500);
  });
}

/* ---------- evidence: review packs, audit & lineage ---------- */
async function viewReviewPacks(sel) {
  const ov = await get("/api/overview");
  const ents = ov.entities;
  const e = sel && ents.some((x) => x.entity_id === sel) ? sel : ents[0].entity_id;
  render({
    page: "Review packs", nav: "review-packs", crumbs: [["Evidence"], ["Review packs"]], title: "Review packs",
    desc: "For each entity, the cases an auditor should open next: 80% targeted at findings, 20% random controls. Download the CSV to record a verdict per case.",
    stats: [["Entities", fmtInt(ents.length)], ["Cases per pack", "20"], ["Targeted · control", "80% · 20%"]],
  }, `<div class="toolbar"><label class="field"><span>Entity</span><select id="packSel">${ents.map((x) => `<option value="${esc(x.entity_id)}"${x.entity_id === e ? " selected" : ""}>${esc(x.entity_id)} — ${x.findings.length} finding${x.findings.length === 1 ? "" : "s"}, SAI ${fmtIdx(x.sai)}</option>`).join("")}</select></label>
      <span class="grow"></span><a class="btn" id="packEnt" href="#/e/${enc(e)}">Open entity page</a></div>
    <div class="grid g2" id="packBody"><div class="sk" style="height:480px"></div><div class="sk" style="height:480px"></div></div>`);
  const load = async (id) => {
    const [pack, ctl] = await Promise.all([get(`/api/entity/${enc(id)}/review-pack`), get(`/api/entity/${enc(id)}/controls`)]);
    $("packBody").innerHTML = packHtml(id, pack, ctl); bindCsv($("packBody"), id, pack); bindAll();
    $("packEnt").href = `#/e/${enc(id)}`;
  };
  $("packSel").addEventListener("change", (ev) => { replaceQuery(`/review-packs/${ev.target.value}`, {}); load(ev.target.value); });
  await load(e);
}
async function viewAudit() {
  const [au, m, rj] = await Promise.all([get("/api/audit/verify"), get("/api/meta"), get("/api/rejects")]);
  const c = m.counts || {};
  const byEnt = {};
  rj.forEach((r) => { byEnt[r.entity_id] = (byEnt[r.entity_id] || 0) + r.rows; });
  const store = [["Alerts", c.alerts], ["Cases", c.cases], ["Workflow steps", c.workflow], ["Escalations", c.escalations], ["Asset records", c.assets],
    ["Entity profiles", c.profiles], ["Submission receipts (files)", c.receipts], ["Rejected rows (logged)", c.rejects]].filter(([, v]) => v != null);
  render({
    page: "Audit & lineage", nav: "audit", crumbs: [["Evidence"], ["Audit & lineage"]], title: "Audit & lineage",
    desc: "Every number traces back to a submitted file, a row and a SHA-256 receipt. Every ingest, score run and export is written to a hash-chained log.",
    stats: [["Audit chain", `<span class="status ${au.intact ? "ok" : "bad"}">${au.intact ? "Intact" : "Broken"}</span>`], ["Log entries", fmtInt(au.entries)],
      ["Receipts", fmtInt(c.receipts)], ["Rejected rows", fmtInt(c.rejects)]],
  }, `
    <div class="grid g2">
      <section class="card" aria-labelledby="ach"><h2 id="ach">Tamper-evident audit log</h2>
        <p class="lead"><span class="status ${au.intact ? "ok" : "bad"}">${au.intact ? "Chain intact" : "Chain broken"}</span></p>
        <p class="note">${fmtInt(au.entries)} hash-chained entries (ingest, score runs, exports). Each entry stores the hash of the one before it, so editing any past entry breaks every later hash. Re-check at any time with <code>socrix verify</code>.</p></section>
      <section class="card" aria-labelledby="luh"><h2 id="luh">Look up an alert</h2>
        <form id="lookup" class="toolbar" novalidate><label class="field grow"><span>Alert ID</span><input type="text" id="aid" placeholder="e.g. PWR-03-2026-08-AL00011" autocomplete="off" spellcheck="false" aria-describedby="aidHelp"></label>
          <button class="btn primary" type="submit" style="align-self:flex-end">Open timeline and lineage</button></form>
        <p class="note" id="aidHelp">Shows the case timeline, the submission, file and row it came from, and the SHA-256 receipt of that file.${STATIC ? " The static report includes only alerts that appear in review packs or finding evidence." : ""}</p></section>
    </div>
    <section class="card section" aria-labelledby="lph"><h2 id="lph">How a number is traced</h2>
      <ol class="steps"><li><b>Submission received</b> — each file gets a SHA-256 receipt and a row count.</li><li><b>Validated</b> — bad rows go to the reject log with a reason; nothing is silently dropped.</li>
        <li><b>Stored</b> — every row keeps its submission ID, source file and row number.</li><li><b>Scored</b> — each indicator keeps the exact rows behind it as evidence.</li>
        <li><b>Explained</b> — findings link to evidence rows, and each row links to this lineage.</li></ol></section>
    <div class="grid g2 section">
      <section class="card" aria-labelledby="esh"><h2 id="esh">Evidence store</h2><div class="scroll"><table><caption class="sr-only">Records in the evidence store</caption><thead><tr><th scope="col">Record type</th><th scope="col" class="num">Rows</th></tr></thead><tbody>
        ${store.map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${fmtInt(v)}</td></tr>`).join("")}</tbody></table></div></section>
      <section class="card" aria-labelledby="rbh"><h2 id="rbh">Rejected rows by entity</h2><div class="scroll"><table><caption class="sr-only">Rejected rows by entity</caption><thead><tr><th scope="col">Entity</th><th scope="col" class="num">Rejected rows</th></tr></thead><tbody>
        ${Object.keys(byEnt).length ? Object.entries(byEnt).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr class="click" data-href="#/e/${enc(k)}"><td class="id">${esc(k)}</td><td class="num">${fmtInt(v)}</td></tr>`).join("")
          : `<tr><td colspan="2">${empty("No rows were rejected in any submission.")}</td></tr>`}</tbody></table></div>
        <p class="note section">Reasons are listed on the <a href="#/validation">Validation</a> page.</p></section>
    </div>`);
  $("lookup").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const v = $("aid").value.trim().toUpperCase();
    if (!v) { $("aidHelp").textContent = "Enter an alert ID, for example PWR-03-2026-08-AL00011."; $("aid").focus(); return; }
    location.hash = `#/case/${enc(v)}`;
  });
}

/* ---------- assessment quality: validation & method ---------- */
const DOSE = [   // docs/VALIDATION.md §5.2 (sensitivity profile); static, not served by the API
  ["A1 no-investigation closures", "1/9", "3/9", "9/9", "9/9"], ["A2 fast closures", "0/3", "0/3", "3/3", "3/3"], ["A3 no escalation", "0/9", "1/9", "4/9", "8/9"],
  ["A4 template notes", "9/9", "9/9", "9/9", "9/9"], ["A5 unremediated repeats", "1/9", "1/9", "2/9", "8/9"], ["A6 no enrichment", "9/9", "9/9", "9/9", "9/9"],
  ["A7 silent critical assets", "0/9", "0/9", "1/9", "1/9"], ["A8 missing tactics", "9/9", "9/9", "9/9", "9/9"], ["A9 no workflow", "9/9", "9/9", "9/9", "9/9"],
  ["A10 low activity", "0/9", "0/9", "0/9", "7/9"], ["A11 data quality", "0/9", "0/9", "9/9", "9/9"], ["A12 workload", "0/9", "4/9", "9/9", "9/9"]];
async function viewValidation() {
  const [b, rj, au] = await Promise.all([get("/api/benchmark").catch(() => null), get("/api/rejects"), get("/api/audit/verify")]);
  const rjAgg = {};
  rj.forEach((r) => { rjAgg[r.reason] = (rjAgg[r.reason] || 0) + r.rows; });
  const doseCell = (v) => { const [k, n] = v.split("/").map(Number); return `<td class="num"><span class="chip txt ${k === n ? "ok" : k === 0 ? "" : "warn"}">${v}</span></td>`; };
  render({
    page: "Validation & assurance", nav: "validation", crumbs: [["Assessment quality"], ["Validation"]], title: "Validation & assurance",
    desc: "Every finding is checked against known ground truth, re-computed by an independent implementation, and stress-tested for false alarms.",
    stats: b ? [["Detected", `${fmtInt(b.detected)}/${fmtInt(b.planted)}`], ["False alarms", fmtInt(b.false_positives)], ["Figures independently matched", "576/576"],
      ["Findings on clean entities", fmtInt(b.clean_entity_false_positives)]] : null,
  }, `
    <section class="card" aria-labelledby="wth"><h2 id="wth">Why these results can be trusted</h2>${trustList(TRUST)}</section>
    ${b ? `<div class="grid g2 section">
      <section class="card" aria-labelledby="pah"><h2 id="pah">Per archetype</h2><div class="scroll"><table><caption class="sr-only">Detection per planted archetype</caption><thead><tr><th scope="col">Planted weakness</th><th scope="col">Detected</th></tr></thead><tbody>
      ${b.archetypes.slice().sort((x, y) => x.archetype.localeCompare(y.archetype, "en", { numeric: true })).map((a) => `<tr><td>${esc(a.archetype)}</td><td><span class="inlinebar" aria-hidden="true"><i style="width:${a.expected ? (100 * a.detected) / a.expected : 0}%"></i></span><span class="tnum">${a.detected}/${a.expected}</span></td></tr>`).join("")}</tbody></table></div>
      ${b.missed_list.length ? `<p class="note section">Missed: ${b.missed_list.map((k) => esc(k.join("/"))).join(", ")}</p>` : ""}
      ${b.related_list.length ? `<details class="section"><summary>Related co-findings (${b.related_list.length})</summary><div>${b.related_list.map((k) => esc(k.join(" / "))).join(", ")}</div></details>` : ""}</section>
      <section class="card" aria-labelledby="dlh"><h2 id="dlh">Sensitivity profile</h2>
        <p class="note">Detection as planted signals are weakened to 15–75% strength — zero false alarms at every level. 3 test datasets per strength; cells show planted weaknesses detected.</p>
        <div class="scroll"><table><caption class="sr-only">Detection by plant strength</caption><thead><tr><th scope="col">Archetype</th><th scope="col" class="num">15%</th><th scope="col" class="num">25%</th><th scope="col" class="num">50%</th><th scope="col" class="num">75%</th></tr></thead><tbody>
        ${DOSE.map(([a, ...v]) => `<tr><td>${esc(a)}</td>${v.map(doseCell).join("")}</tr>`).join("")}</tbody></table></div>
        <p class="note section">Source: docs/VALIDATION.md §5.2 (static content, not served by the API).</p></section>
    </div>` : `<div class="notice"><h2>No benchmark run yet</h2><p>Run <code>socrix bench</code> to grade the last score run against the planted ground truth.</p></div>`}
    <div class="grid g2 section">
      <section class="card" aria-labelledby="rrh"><h2 id="rrh">Rejected rows (never silently dropped)</h2><div class="scroll"><table><caption class="sr-only">Rejected rows by reason</caption><thead><tr><th scope="col">Reason</th><th scope="col" class="num">Rows</th></tr></thead><tbody>
        ${Object.keys(rjAgg).length ? Object.entries(rjAgg).sort((x, y) => y[1] - x[1]).map(([k, v]) => `<tr><td class="id">${esc(k)}</td><td class="num">${fmtInt(v)}</td></tr>`).join("") : `<tr><td colspan="2">${empty("No rows were rejected.")}</td></tr>`}</tbody></table></div></section>
      <section class="card" aria-labelledby="tah"><h2 id="tah">Tamper-evident audit log</h2><p class="lead"><span class="status ${au.intact ? "ok" : "bad"}">${au.intact ? "Chain intact" : "Chain broken"}</span></p>
        <p class="note">${fmtInt(au.entries)} hash-chained entries (ingest, score runs, exports). Editing any past entry breaks every later hash. <a href="#/audit">Audit &amp; lineage</a></p></section>
    </div>`);
}
async function viewMethod() {
  const m = await get("/api/meta");
  const sec = (h, f, t) => `<section class="card"><h2>${h}</h2><code class="formula">${f}</code><p class="note">${t}</p></section>`;
  render({
    page: "Method", nav: "method", crumbs: [["Assessment quality"], ["Method"]], title: "Method",
    desc: "How submitted records become findings. Every step is deterministic and runs offline; no AI model and no external service is involved.",
    stats: [["Engine", `<span class="id">${esc(m.engine)}</span>`], ["Catalogue", `<span class="id">${esc(m.catalogue_version)}</span>`], ["ATT&CK", `Enterprise v${esc(m.attack)}`], ["Finding threshold", `concern ≥ ${m.finding_threshold}`]],
  }, `<div class="grid g2 method">
      ${sec("Rates", "rate = Wilson95_lower(k, n)", "Proportions use the lower end of the 95% Wilson interval, so a small sample never looks worse than the evidence supports.")}
      ${sec("Peer comparison", "M = 0.6745 · (x − median) / MAD", "Each entity is compared with same-sector, same-size peers, leaving itself out. The MAD is floored at the binomial sampling error.")}
      ${sec("Concern", "concern = max(100 · clip(M, 0, 7) / 7, policy)", "M = 3.5, the NIST outlier line, maps to concern 50, the finding threshold. Policy rules can raise concern, never lower it.")}
      ${sec("Aggregation", `area = (Σ wᵢ · cᵢ^p)^(1/p),  p = ${esc(m.power_mean_p)}`, "Indicators roll up into capability areas, and areas into the SAI, with a power mean, so one serious weakness is not diluted by clean areas.")}
      ${sec("Uncertainty", `${fmtInt(m.uncertainty_draws)} × Dirichlet(1) weights × p ∈ {1, 2, 3, 6}`, "Re-ranking under many plausible weightings gives each entity a rank range and a probability of being in the top 3.")}
      ${sec("Explanations", "template(k, n, value, median, M, baseline)", "Each finding sentence is filled from a fixed template with the numbers above, so it always matches the table.")}
    </div>
    <section class="card section"><h2>Reference</h2><dl class="kv">
      <dt>ATT&amp;CK reference</dt><dd>Enterprise v${esc(m.attack)} (offline, STIX-derived; tactics incl. TA0005 Stealth, TA0112 Defense Impairment)</dd>
      <dt>Missing data</dt><dd>Too few records gives “insufficient evidence”, never a score of zero</dd>
      <dt>Indicator definitions</dt><dd><a href="#/indicators">Indicator catalogue</a> (${fmtInt(Object.keys(m.indicators).length)} indicators)</dd></dl></section>`);
}
async function viewAbout() {
  render({
    page: "About", nav: "about", crumbs: [["About"]], title: `About ${SITE.product}`, desc: SITE.tagline + ".",
    stats: [["Problem statement", `<span class="id">${esc(SITE.psId)}</span>`], ["Owner", esc(SITE.psOwner)], ["Team", esc(SITE.team)], ["Indicators", fmtInt(Object.keys(CAT || {}).length)]],
  }, `<div class="grid g2">
      <section class="card" aria-labelledby="psh"><h2 id="psh">Problem statement</h2><dl class="kv">
        <dt>ID</dt><dd class="id">${esc(SITE.psId)}</dd><dt>Title</dt><dd>${esc(SITE.psTitle)}</dd><dt>Owner</dt><dd>${esc(SITE.psOwner)}</dd><dt>Event</dt><dd>${esc(SITE.event)}</dd></dl></section>
      <section class="card" aria-labelledby="wdh"><h2 id="wdh">What ${esc(SITE.product)} does</h2><ul class="steps">
        <li>Reads the records SOCs already keep (alerts, cases, workflow steps, escalations, asset lists) from periodic submissions — no live access and no SIEM.</li>
        <li>Finds where security operations are weak or silent, compared with peers and policy, and explains each finding in one plain sentence.</li>
        <li>Links every number to the exact rows behind it and tells auditors which cases to review next.</li></ul></section>
    </div>
    <section class="card section" aria-labelledby="mh"><h2 id="mh">Method in five steps</h2><ol class="steps">
      <li><b>Intake</b> — validate each submission, issue a SHA-256 receipt, log rejected rows, pseudonymise analysts.</li>
      <li><b>Evidence store</b> — every row keeps its submission, file and row number.</li>
      <li><b>12 indicators</b> — execution gaps, negative space and workload, mapped to 7 of the brief’s 8 capability areas.</li>
      <li><b>Peer &amp; policy scoring</b> — modified z against comparable peers, policy rules, power-mean aggregation with rank uncertainty.</li>
      <li><b>Findings &amp; review packs</b> — deterministic explanations, evidence drill-down and a 20-case review pack per entity.</li></ol>
      <p class="note"><a href="#/method">Full method</a> · <a href="#/indicators">Indicator catalogue</a></p></section>
    <div class="grid g2 section">
      <section class="card" aria-labelledby="hh"><h2 id="hh">Why these results can be trusted</h2>${trustList([TRUST[0], TRUST[1], TRUST[4], TRUST[5]])}
        <p class="note"><a href="#/validation">Full validation</a></p></section>
      <section class="card" aria-labelledby="teh"><h2 id="teh">Team</h2><dl class="kv">
        <dt>Team</dt><dd>${esc(SITE.team)}</dd>${SITE.teamId ? `<dt>Team ID</dt><dd class="tnum">${esc(SITE.teamId)}</dd>` : ""}<dt>Institution</dt><dd>${esc(SITE.institution)}</dd><dt>Product</dt><dd>${esc(SITE.product)} — ${esc(SITE.longName)}</dd></dl></section>
    </div>`);
}

/* ---------- theme toggle (persisted as socrix-theme) ---------- */
const sysDark = () => window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
const curTheme = () => document.documentElement.getAttribute("data-theme") || (sysDark() ? "dark" : "light");
function paintThemeBtn() {
  const dark = curTheme() === "dark", b = $("themeBtn");
  b.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  b.innerHTML = `${icon(dark ? "sun" : "moon")}<span class="txt">${dark ? "Light" : "Dark"}</span>`;
}
$("themeBtn").addEventListener("click", () => {
  const next = curTheme() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("socrix-theme", next); } catch (e) { /* storage blocked: theme still applies for this visit */ }
  paintThemeBtn();
});

/* ---------- mobile drawer with focus trap ---------- */
const side = $("sidebar"), scrim = $("scrim"), menuBtn = $("menuBtn");
const drawerOpen = () => side.classList.contains("open");
function openDrawer() {
  side.classList.add("open"); scrim.classList.add("open"); menuBtn.setAttribute("aria-expanded", "true");
  side.setAttribute("role", "dialog"); side.setAttribute("aria-modal", "true");
  (side.querySelector('[aria-current="page"]') || side.querySelector("a")).focus();
}
function closeDrawer(restore = true) {
  if (!drawerOpen()) return;
  side.classList.remove("open"); scrim.classList.remove("open"); menuBtn.setAttribute("aria-expanded", "false");
  side.removeAttribute("role"); side.removeAttribute("aria-modal");
  if (restore) menuBtn.focus();
}
menuBtn.addEventListener("click", () => (drawerOpen() ? closeDrawer() : openDrawer()));
scrim.addEventListener("click", () => closeDrawer());
side.addEventListener("click", (ev) => { if (ev.target.closest("#closeNav")) closeDrawer(); });
side.addEventListener("keydown", (ev) => {
  if (!drawerOpen()) return;
  if (ev.key === "Escape") { ev.preventDefault(); closeDrawer(); return; }
  if (ev.key !== "Tab") return;
  const f = [...side.querySelectorAll("a[href], button")].filter((x) => x.offsetParent !== null);
  if (!f.length) return;
  if (ev.shiftKey && document.activeElement === f[0]) { ev.preventDefault(); f[f.length - 1].focus(); }
  else if (!ev.shiftKey && document.activeElement === f[f.length - 1]) { ev.preventDefault(); f[0].focus(); }
});
matchMedia("(min-width: 768px)").addEventListener("change", (mq) => { if (mq.matches) closeDrawer(false); });

/* ---------- header quick search (ARIA combobox) ---------- */
const qsIn = $("qsInput"), qsList = $("qsList");
let qsItems = [], qsIdx = -1, qsEnts = null;
async function qsLoad() { if (!qsEnts) { try { qsEnts = (await get("/api/overview")).entities; } catch (e) { qsEnts = []; } } }
function qsRender() {
  const v = qsIn.value.trim(), up = v.toUpperCase();
  qsItems = [];
  if (v) {
    if (ALERT_RE.test(v)) qsItems.push({ href: `#/case/${enc(up)}`, label: up, note: "Alert timeline" });
    (qsEnts || []).filter((e) => e.entity_id.includes(up) || e.sector.toUpperCase().includes(up)).slice(0, 8)
      .forEach((e) => qsItems.push({ href: `#/e/${enc(e.entity_id)}`, label: e.entity_id, note: `${e.sector} · SAI ${fmtIdx(e.sai)}` }));
  }
  qsIdx = qsItems.length ? 0 : -1;
  const open = !!v;
  qsList.hidden = !open; qsIn.setAttribute("aria-expanded", String(open));
  qsList.innerHTML = qsItems.length ? qsItems.map((it, k) => `<li role="option" id="qso${k}" aria-selected="${k === qsIdx}" data-k="${k}"><span class="id">${esc(it.label)}</span><span class="note">${esc(it.note)}</span></li>`).join("")
    : `<li class="empty" role="option" aria-selected="false" aria-disabled="true">No entity matches. Alert IDs look like PWR-03-2026-08-AL00011.</li>`;
  qsActive();
}
function qsActive() {
  qsList.querySelectorAll("li[data-k]").forEach((li) => li.setAttribute("aria-selected", String(Number(li.dataset.k) === qsIdx)));
  if (qsIdx >= 0) { qsIn.setAttribute("aria-activedescendant", `qso${qsIdx}`); const a = $(`qso${qsIdx}`); a && a.scrollIntoView({ block: "nearest" }); }
  else qsIn.removeAttribute("aria-activedescendant");
}
function qsClose() { qsList.hidden = true; qsIn.setAttribute("aria-expanded", "false"); qsIn.removeAttribute("aria-activedescendant"); }
function qsGo(k) { const it = qsItems[k]; if (!it) return; qsClose(); qsIn.value = ""; location.hash = it.href; }
qsIn.addEventListener("focus", qsLoad);
qsIn.addEventListener("input", async () => { await qsLoad(); qsRender(); });
qsIn.addEventListener("keydown", (ev) => {
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
    ev.preventDefault(); if (qsList.hidden) { qsRender(); return; }
    if (qsItems.length) { qsIdx = (qsIdx + (ev.key === "ArrowDown" ? 1 : -1) + qsItems.length) % qsItems.length; qsActive(); }
  } else if (ev.key === "Enter") {
    ev.preventDefault();
    if (qsIdx >= 0) qsGo(qsIdx); else if (qsIn.value.trim()) { qsClose(); location.hash = `#/case/${enc(qsIn.value.trim().toUpperCase())}`; qsIn.value = ""; }
  } else if (ev.key === "Escape") { if (!qsList.hidden) { ev.preventDefault(); qsClose(); } else qsIn.blur(); }
  else if (ev.key === "Tab") qsClose();
});
qsList.addEventListener("mousedown", (ev) => { const li = ev.target.closest("li[data-k]"); if (li) { ev.preventDefault(); qsGo(Number(li.dataset.k)); } });
qsIn.addEventListener("blur", () => setTimeout(qsClose, 100));
document.addEventListener("keydown", (ev) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
  if ((ev.key === "/" && !typing && !ev.metaKey && !ev.ctrlKey) || ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k")) {
    ev.preventDefault(); closeDrawer(false); qsIn.focus(); qsIn.select();
  }
});

/* ---------- router ---------- */
let first = true;
async function route() {
  const { parts: p, q } = parseHash();
  closeDrawer(false);
  const slow = STATIC ? null : setTimeout(skeleton, 120);
  try {
    if (!CAT) { try { META = await get("/api/meta"); CAT = META.indicators; renderFooter(); } catch (e) { if (e.offline) throw e; CAT = {}; } }
    if (!p.length) await viewOverview(q);
    else if (p[0] === "e" && p[2] === "i") await viewIndicator(p[1], p[3], Number(p[4] || 0));
    else if (p[0] === "e") await viewEntity(p[1]);
    else if (p[0] === "entities") await viewEntities(q);
    else if (p[0] === "indicators") await viewIndicators();
    else if (p[0] === "review-packs") await viewReviewPacks(p[1]);
    else if (p[0] === "audit") await viewAudit();
    else if (p[0] === "case") await viewCase(p[1]);
    else if (p[0] === "validation") await viewValidation();
    else if (p[0] === "method") await viewMethod();
    else if (p[0] === "about") await viewAbout();
    else await viewOverview(q);
  } catch (err) {
    errorView(err);
  } finally {
    clearTimeout(slow);
  }
  window.scrollTo(0, 0);
  document.documentElement.dataset.ready = location.hash || "#/";   // lets automated checks wait for a finished render
  if (!first) $("main").focus({ preventScroll: true });
  first = false;
}
window.addEventListener("hashchange", route);
document.querySelector(".skip").addEventListener("click", (ev) => { ev.preventDefault(); $("main").focus(); $("main").scrollIntoView(); });
renderShell();
paintThemeBtn();
route();
