/* SOCRIX dashboard — vanilla JS, no external libraries, works fully offline.
   Server mode: reads /api/*.  Static-report mode: reads window.SOCRIX_DATA (embedded by `socrix export`). */
"use strict";
const STATIC = typeof window.SOCRIX_DATA === "object";
const AREAS = ["Threat Detection", "Investigation", "Escalation", "Incident Response", "Security Operations",
  "Governance and Oversight", "Operational Discipline", "Cyber Resilience"];
const $app = document.getElementById("app");
const cache = {};

async function get(path) {
  if (STATIC) {
    const d = window.SOCRIX_DATA[path];
    if (d === undefined) throw new Error("Not included in this static report: " + path + " (run the server for full drill-down)");
    return d;
  }
  if (cache[path]) return cache[path];
  const r = await fetch(path);
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return (cache[path] = await r.json());
}
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n1 = (v) => (v == null || Number.isNaN(v) ? "–" : Number(v).toFixed(1));
const pct = (v) => (v == null ? "–" : (100 * v).toFixed(1) + "%");
// concern bins -> CSS classes (colour + text colour per theme live in style.css, validated for contrast)
const hcls = (c) => c == null ? "hna" : c < 20 ? "h0" : c < 35 ? "h1" : c < 50 ? "h2" : c < 75 ? "h3" : "h4";
const heat = (c) => c == null ? "var(--na)" : `var(--c${hcls(c).slice(1)})`;
const enc = encodeURIComponent;
let CAT = null;   // indicator catalogue (for rate vs non-rate display)
const isRate = (iid) => !!(CAT && CAT[iid] && CAT[iid].rate);
const countText = (i) => isRate(i.indicator) ? `${i.k}/${i.n}` : i.indicator === "NS-05" ? `${i.k} alerts / ${i.n} assets`
  : i.indicator === "NS-02" ? `${i.k} of ${i.n} expected` : `n=${i.n}`;

function fmtVal(iid, v) {
  if (v == null) return "–";
  if (iid === "EG-02") return Math.round(Math.pow(10, v)) + " min";
  if (iid === "NS-02") return String(Math.round(v));
  if (iid === "NS-05" || iid === "WL-01") return v.toFixed(2);
  return pct(v);
}
function crumbs(parts) {
  return `<div class="crumbs">${parts.map(([t, h]) => (h ? `<a href="${h}">${esc(t)}</a>` : esc(t))).join(" › ")}</div>`;
}
function navOn(name) {
  document.querySelectorAll("nav a").forEach((a) => a.classList.toggle("on", a.dataset.nav === name));
}

/* ---------- tiny SVG charts ---------- */
function stripPlot(dist, selfId, iid, higherWorse, engineMedian) {
  const W = 560, H = 110, P = 28;
  const vals = dist.map((d) => d.value).filter((v) => v != null);
  if (!vals.length) return '<p class="muted">No peer distribution.</p>';
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { hi = lo + 1; }
  const x = (v) => P + ((v - lo) / (hi - lo)) * (W - 2 * P);
  const sorted = [...vals].sort((a, b) => a - b);
  // use the engine's baseline median (same sector/size, leave-one-out) so the chart matches the explanation text
  const med = engineMedian != null ? engineMedian : sorted[Math.floor((sorted.length - 1) / 2)] / 2 + sorted[Math.ceil((sorted.length - 1) / 2)] / 2;
  lo = Math.min(lo, med); hi = Math.max(hi, med);
  const dots = dist.map((d, i) => {
    const self = d.entity_id === selfId;
    const y = self ? 48 : 40 + ((i * 37) % 21);
    const lab = self ? `<text x="${x(d.value).toFixed(1)}" y="${y - 12}" text-anchor="middle" class="selflab">${esc(selfId)}</text>` : "";
    return lab + `<circle cx="${x(d.value).toFixed(1)}" cy="${y}" r="${self ? 7 : 5}" class="${self ? "self" : "peer"}"><title>${esc(d.entity_id)}: ${esc(fmtVal(iid, d.value))} (concern ${n1(d.concern)})</title></circle>`;
  }).join("");
  const alt = `Peer distribution: ${selfId} ${fmtVal(iid, dist.find((d) => d.entity_id === selfId)?.value)} vs baseline median ${fmtVal(iid, med)}; ${dist.length} entities from ${fmtVal(iid, lo)} to ${fmtVal(iid, hi)}`;
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(alt)}">
    <line x1="${P}" x2="${W - P}" y1="78" y2="78" class="axis"/>
    <line x1="${x(med)}" x2="${x(med)}" y1="20" y2="78" class="med"/>
    <text x="${x(med)}" y="14" text-anchor="middle">peer median ${esc(fmtVal(iid, med))}</text>
    ${dots}
    <text x="${P}" y="96">${esc(fmtVal(iid, lo))}</text><text x="${W - P}" y="96" text-anchor="end">${esc(fmtVal(iid, hi))}</text>
    <text x="${W / 2}" y="108" text-anchor="middle">${higherWorse ? "→ worse" : "← worse"}</text></svg>`;
}
function lineChart(points, key, opts = {}) {
  const W = opts.w || 300, H = opts.h || 90, P = 24;
  const pts = points.filter((p) => p[key] != null);
  if (pts.length < 1) return '<p class="muted">No history.</p>';
  const ys = pts.map((p) => p[key]);
  const lo = opts.min ?? Math.min(...ys), hi = opts.max ?? Math.max(...ys, lo + 1e-9);
  const x = (i) => P + (pts.length === 1 ? (W - 2 * P) / 2 : (i / (pts.length - 1)) * (W - 2 * P));
  const y = (v) => H - P - ((v - lo) / (hi - lo || 1)) * (H - 2 * P);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const thr = opts.thr != null ? `<line x1="${P}" x2="${W - P}" y1="${y(opts.thr)}" y2="${y(opts.thr)}" class="thr"/>` : "";
  const lab = pts.map((p, i) => `<circle cx="${x(i)}" cy="${y(p[key])}" r="3.5" fill="var(--accent)"><title>${esc(p.period)}: ${esc(opts.fmt ? opts.fmt(p[key]) : n1(p[key]))}</title></circle>
    <text x="${x(i)}" y="${H - 6}" text-anchor="middle">${esc(p.period)}</text>`).join("");
  const alt = (opts.label || "Trend") + ": " + pts.map((p) => `${p.period} ${opts.fmt ? opts.fmt(p[key]) : n1(p[key])}`).join(", ");
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(alt)}">${thr}<path d="${d}" class="line"/>${lab}</svg>`;
}

/* ---------- D0 overview ---------- */
async function viewOverview() {
  navOn("overview");
  const [ov, bench, au] = await Promise.all([get("/api/overview"), get("/api/benchmark").catch(() => null), get("/api/audit/verify").catch(() => null)]);
  const ents = ov.entities, m = ov.meta;
  const findings = ents.reduce((s, e) => s + e.findings.length, 0);
  const withF = ents.filter((e) => e.findings.length).length;
  document.getElementById("runtag").textContent = `period ${m.latest} · engine ${m.engine} · ATT&CK v${m.attack}`;
  const rows = ents.map((e) => `<tr class="click" data-href="#/e/${enc(e.entity_id)}">
      <td><b>${esc(e.entity_id)}</b><div class="note">${esc(e.sector)} · ${esc(e.size_band)}</div></td>
      <td class="num"><b>${n1(e.sai)}</b><div class="note">rank ${e.rank_min}–${e.rank_max}</div></td>
      ${AREAS.map((a) => { const c = e.areas[a]; return `<td class="cell ${hcls(c)}" title="${esc(a)}: ${c == null ? "not assessed (no indicator or insufficient evidence)" : "concern " + n1(c)}">${c == null ? '<span class="sr-only">not assessed</span>' : Math.round(c)}</td>`; }).join("")}
      <td>${e.findings.length ? e.findings.map((f) => `<span class="chip bad">${esc(f)}</span>`).join("") : '<span class="chip ok">none</span>'}</td>
      <td class="num">${e.coverage}/8</td></tr>`).join("");
  $app.innerHTML = `
    <h1>National SOC assurance overview</h1>
    <p class="muted">Where should NCIIPC look first? Entities sorted by SOC Assurance Index (higher = more concern). Click any row to drill down.</p>
    <div class="grid g4">
      <div class="card kpi"><div class="v">${ents.length}</div><div class="l">entities assessed · ${esc(m.latest)}</div></div>
      <div class="card kpi"><div class="v">${findings}</div><div class="l">findings across ${withF} entities (concern ≥ ${m.finding_threshold})</div></div>
      <div class="card kpi"><div class="v">${bench ? pct(bench.recall) + " / " + pct(bench.precision) : "–"}</div><div class="l">validation recall / precision (synthetic ground truth)</div></div>
      <div class="card kpi"><div class="v" style="color:${au && au.intact ? "var(--ok)" : "var(--bad)"}">${au ? (au.intact ? "Intact" : "BROKEN") : "–"}</div><div class="l">audit chain · ${au ? au.entries : 0} entries</div></div>
    </div>
    <div class="card section">
      <h2>Capability-area concern heatmap</h2>
      <div class="legend" aria-label="Concern scale"><span>Concern:</span><span><i style="background:var(--c0);box-shadow:inset 0 0 0 1px var(--line)"></i>0–19</span><span><i style="background:var(--c1)"></i>20–34</span><span><i style="background:var(--c2)"></i>35–49</span><span><i style="background:var(--c3)"></i><b>50–74 finding</b></span><span><i style="background:var(--c4)"></i><b>75–100 severe finding</b></span><span><i style="background:var(--na);box-shadow:inset 0 0 0 1px var(--line)"></i>not assessed</span></div>
      <div class="scroll"><table class="heat"><thead><tr><th>Entity</th><th class="num">SAI</th>${AREAS.map((a) => `<th title="${esc(a)}">${esc(a.split(" ")[0])}</th>`).join("")}<th>Findings</th><th class="num">Coverage</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="note">Rank range = best/worst rank under weighting uncertainty (2,000 Dirichlet draws) and aggregation exponent p ∈ {1,2,3,6}. Overlapping ranges mean the ordering is not decisive — read the findings, not just the rank.</p>
    </div>`;
  bindRows();
}

/* ---------- D1 entity ---------- */
async function viewEntity(e) {
  navOn("overview");
  const x = await get(`/api/entity/${enc(e)}`);
  const inds = Object.values(x.indicators);
  const fnd = inds.filter((i) => i.status === "assessed" && i.concern >= 50).sort((a, b) => b.concern - a.concern);
  const near = inds.filter((i) => i.status === "assessed" && i.concern >= 35 && i.concern < 50).sort((a, b) => b.concern - a.concern);
  const areaRows = AREAS.map((a) => { const c = x.areas[a]; return `<div class="arow"><span>${esc(a)}</span><div class="bar"><i style="width:${c == null ? 0 : Math.max(2, c)}%;background:${heat(c)}"></i></div><span class="num mono">${c == null ? "n/a" : Math.round(c)}</span></div>`; }).join("");
  const indRows = inds.sort((a, b) => a.indicator.localeCompare(b.indicator)).map((i) => `<tr class="click" data-href="#/e/${enc(e)}/i/${enc(i.indicator)}">
      <td class="mono">${esc(i.indicator)}</td><td>${esc(i.name)}<div class="note">${esc(i.area)}</div></td>
      <td class="num">${i.status === "assessed" ? esc(countText(i)) : `<span class="chip warn">n=${i.n}</span>`}</td>
      <td class="num">${i.status === "assessed" ? esc(i.display || fmtVal(i.indicator, i.value)) : "–"}</td>
      <td class="num">${i.status === "assessed" ? esc(fmtVal(i.indicator, i.median)) : "–"}</td>
      <td class="num"><span class="chip ${hcls(i.status === "assessed" ? i.concern : null)}">${i.status === "assessed" ? Math.round(i.concern) : "insufficient"}</span></td>
      <td>${esc(i.track || "")}</td></tr>`).join("");
  $app.innerHTML = `${crumbs([["Overview", "#/"], [e]])}
    <h1>${esc(e)} <span class="muted" style="font-weight:400;font-size:15px">${esc(x.sector)} · ${esc(x.size_band)}</span></h1>
    <div class="grid g4 section">
      <div class="card kpi"><div class="v">${n1(x.sai)}</div><div class="l">SOC Assurance Index (0–100, higher = more concern)</div></div>
      <div class="card kpi"><div class="v">${x.findings.length}</div><div class="l">findings</div></div>
      <div class="card kpi"><div class="v">${x.rank_min}–${x.rank_max}</div><div class="l">rank range · P(top 3) ${pct(x.p_top3)}</div></div>
      <div class="card kpi"><div class="v">${x.coverage}/8</div><div class="l">capability areas with evidence</div></div>
    </div>
    <div class="grid g3 section">
      <div class="card"><h2>Findings — what went wrong, in plain words</h2>
        ${fnd.length ? fnd.map((i) => `<div class="finding"><div class="h"><b>${esc(i.indicator)}</b><span>${esc(i.name)}</span><span class="chip bad">concern ${Math.round(i.concern)}</span><span class="chip">${esc(i.track)}</span></div>
          <div>${esc(i.explanation)}</div><div class="note"><a href="#/e/${enc(e)}/i/${enc(i.indicator)}">See peers, history and the ${i.evidence_count} evidence rows →</a> · brief ref ${esc(i.brief)}</div></div>`).join("")
          : '<p class="muted">No indicator crossed the finding threshold for this period.</p>'}
        ${near.length ? `<h2 class="section">Near threshold — worth a look, not a finding</h2>
          <p class="note">Concern 35–49: unusual but within what chance or normal variation can explain. Shown so nothing is hidden.</p>
          ${near.map((i) => `<div class="note"><a href="#/e/${enc(e)}/i/${enc(i.indicator)}"><b>${esc(i.indicator)}</b> ${esc(i.name)}</a> · concern ${Math.round(i.concern)}</div>`).join("")}` : ""}
      </div>
      <div class="card"><h2>Capability areas</h2>${areaRows}
        <h2 class="section">SAI trend</h2>${lineChart(x.trend, "sai", { min: 0, max: 100, thr: 50, label: "SAI by period" })}
      </div>
    </div>
    <div class="card section"><h2>All indicators</h2><div class="scroll"><table><thead><tr><th>ID</th><th>Indicator</th><th class="num">Count</th><th class="num">Value</th><th class="num">Peer median</th><th class="num">Concern</th><th>Track</th></tr></thead><tbody>${indRows}</tbody></table></div>
      <p class="note">"insufficient" = too few records to judge (never scored as zero). Rates use the Wilson 95% lower bound, so small samples are treated conservatively.</p></div>
    <div class="grid g2 section" id="d45"><div class="card"><p class="muted">Loading review pack…</p></div><div class="card"></div></div>`;
  bindRows();
  const [pack, ctl] = await Promise.all([get(`/api/entity/${enc(e)}/review-pack`), get(`/api/entity/${enc(e)}/controls`)]);
  document.getElementById("d45").innerHTML = `
    <div class="card"><h2>Review pack — what to inspect next (${pack.items.length} cases)</h2>
      <p class="note">${pack.targeted} targeted at findings, ${pack.control} random controls (so reviewers also check the engine's blind spots).
      ${STATIC ? "" : `<a class="btn" href="/api/entity/${enc(e)}/review-pack.csv">Download CSV</a>`}</p>
      <div class="scroll"><table><thead><tr><th>Alert</th><th>Why selected</th></tr></thead><tbody>
      ${pack.items.map((it) => `<tr class="click" data-href="#/case/${enc(it.alert_id)}"><td class="mono">${esc(it.alert_id)}</td><td>${it.reason === "random-control" ? '<span class="chip">random control</span>' : `<span class="chip bad">${esc(it.reason.replace("targeted:", ""))}</span>`}</td></tr>`).join("")}
      </tbody></table></div>
      ${(pack.checklist || []).map((c) => `<h2 class="section">Checklist · ${esc(c.indicator)} ${esc(c.name)}</h2><div>${c.items.map((v) => `<span class="chip">${esc(v)}</span>`).join("")}</div>`).join("")}
    </div>
    <div class="card"><h2>Detectors with the weakest handling</h2>
      <p class="note">Share of each detector's alerts closed with no investigation or no enrichment — points at the rules whose alerts analysts skip.</p>
      <table><thead><tr><th>Detector</th><th class="num">Alerts</th><th class="num">Weak</th><th class="num">Share</th></tr></thead><tbody>
      ${ctl.map((c) => `<tr><td class="mono">${esc(c.detector_id)}</td><td class="num">${c.alerts}</td><td class="num">${c.weak_handling}</td><td class="num">${pct(c.share)}</td></tr>`).join("")}
      </tbody></table></div>`;
  bindRows();
}

/* ---------- D2 + D3 indicator & evidence ---------- */
async function viewIndicator(e, iid, offset = 0) {
  navOn("overview");
  const d = await get(`/api/entity/${enc(e)}/indicator/${enc(iid)}`);
  const i = d.detail, m = d.method;
  $app.innerHTML = `${crumbs([["Overview", "#/"], [e, `#/e/${enc(e)}`], [iid]])}
    <h1>${esc(iid)} · ${esc(m.name)}</h1>
    <p class="muted">${esc(m.area)} · ${esc(m.gap.replace("_", " "))} gap · brief ${esc(m.brief)}</p>
    <div class="grid g3 section">
      <div class="card"><h2>Explanation</h2><blockquote>${esc(i.explanation)}</blockquote>
        <h2 class="section">Where ${esc(e)} sits among comparable peers</h2>${stripPlot(d.distribution, e, iid, m.higher_is_worse, i.median)}
        <p class="note">Red = ${esc(e)}; dots = all entities this period; dashed line = median of the comparison baseline. Baseline: ${esc(i.baseline || "–")}. Modified z = 0.6745·(x − median)/MAD (NIST/SEMATECH); 3.5 ↦ concern 50.</p></div>
      <div class="card"><h2>Numbers</h2><div class="kv">
        <div>Status</div><div>${esc(i.status)}</div>
        <div>Count</div><div>${esc(countText(i))}</div>
        <div>Value</div><div>${esc(i.display || fmtVal(iid, i.value))}</div>
        <div>Peer median</div><div>${esc(fmtVal(iid, i.median))}</div>
        <div>Modified z</div><div>${n1(i.modz)}</div>
        <div>Peer concern</div><div>${n1(i.peer_concern)}</div>
        <div>Policy concern</div><div>${n1(i.policy_concern)}</div>
        <div>Concern</div><div><b>${n1(i.concern)}</b> (${esc(i.track || "–")})</div>
        ${i.policy_reason ? `<div>Policy rule</div><div>${esc(i.policy_reason)}</div>` : ""}
        <div>Unit</div><div>${esc(m.unit)}</div>
        <div>Minimum n</div><div>${m.min_n}</div></div>
        <h2 class="section">History (concern)</h2>${lineChart(d.history, "concern", { min: 0, max: 100, thr: 50, label: "Concern by period" })}</div>
    </div>
    <div class="card section" id="ev"><p class="muted">Loading evidence…</p></div>`;
  const path = `/api/entity/${enc(e)}/indicator/${enc(iid)}/evidence` + (STATIC ? "" : `?offset=${offset}&limit=50`);
  let ev;
  try { ev = await get(path); } catch (err) { document.getElementById("ev").innerHTML = `<p class="muted">${esc(err.message)}</p>`; return; }
  const alertRows = ev.rows.length && ev.rows[0].alert_id;
  const body = !ev.rows.length ? '<p class="muted">No evidence rows (indicator not triggered).</p>' : alertRows
    ? `<div class="scroll"><table><thead><tr><th>Alert</th><th>Sev</th><th>Technique</th><th>Asset</th><th>Disp.</th><th class="num">Min to close</th><th>Note</th></tr></thead><tbody>
      ${ev.rows.map((r) => `<tr class="click" data-href="#/case/${enc(r.alert_id)}"><td class="mono">${esc(r.alert_id)}</td><td>${esc(r.severity)}</td><td class="mono">${esc(r.technique_id)}</td><td class="mono">${esc(r.asset_id)}</td><td>${esc(r.disposition)}</td><td class="num">${n1(r.minutes_to_close)}</td><td class="note">${esc((r.note || "").slice(0, 90))}</td></tr>`).join("")}
      </tbody></table></div>`
    : `<div>${ev.rows.map((r) => `<span class="chip">${esc(r.item)}</span>`).join("")}</div>`;
  const pager = STATIC ? (ev.total > ev.rows.length ? `<p class="note">Static report shows the first ${ev.rows.length} of ${ev.total}; the server shows all.</p>` : "")
    : `<p>${offset > 0 ? `<a class="btn" href="#/e/${enc(e)}/i/${enc(iid)}/${Math.max(0, offset - 50)}">← previous</a> ` : ""}${offset + 50 < ev.total ? `<a class="btn" href="#/e/${enc(e)}/i/${enc(iid)}/${offset + 50}">next →</a>` : ""}</p>`;
  document.getElementById("ev").innerHTML = `<h2>Evidence — ${ev.total} rows behind this number${ev.total ? ` (showing ${offset + 1}–${offset + ev.rows.length})` : ""}</h2>${body}${pager}`;
  bindRows();
}

/* ---------- D6 + D7 case & lineage ---------- */
async function viewCase(aid) {
  navOn("overview");
  const [c, l] = await Promise.all([get(`/api/case/${enc(aid)}`), get(`/api/lineage/${enc(aid)}`)]);
  const a = c.alert, e = a.entity_id;
  const cls = (ev) => (ev === "alert closed" ? "closed" : ev === "escalated" ? "esc" : "");
  $app.innerHTML = `${crumbs([["Overview", "#/"], [e, `#/e/${enc(e)}`], [aid]])}
    <h1 class="mono" style="font-size:18px">${esc(aid)}</h1>
    <p>${c.flagged_by.length ? "Part of finding " + c.flagged_by.map((f) => `<a class="chip bad" href="#/e/${enc(e)}/i/${enc(f)}">${esc(f)}</a>`).join("") : '<span class="chip ok">not part of any finding</span>'}
      ${c.also_in_evidence_of && c.also_in_evidence_of.length ? `<span class="note"> · also counted in (below threshold): ${c.also_in_evidence_of.map((f) => `<a class="chip" href="#/e/${enc(e)}/i/${enc(f)}">${esc(f)}</a>`).join("")}</span>` : ""}</p>
    <div class="grid g2 section">
      <div class="card"><h2>Timeline</h2><ul class="tl">${c.timeline.map((t) => `<li class="${cls(t.event)}"><b>${esc(t.event)}</b> <span class="note">${esc(t.ts)}</span><div class="note">${esc(t.detail)}</div></li>`).join("")}</ul>
        ${c.case ? `<h2 class="section">Case note</h2><blockquote>${esc(c.case.note || "(empty)")}</blockquote><div class="note">root cause: ${esc(c.case.root_cause_code || "none recorded")}</div>` : '<p class="muted">No case record.</p>'}</div>
      <div class="card"><h2>Alert</h2><div class="kv">
        <div>Severity</div><div>${esc(a.severity)}</div><div>Technique</div><div class="mono">${esc(a.technique_id)}</div>
        <div>Detector</div><div class="mono">${esc(a.detector_id)}</div><div>Asset</div><div class="mono">${esc(a.asset_id)} ${c.asset ? `(${esc(c.asset.criticality)}, ${esc(c.asset.environment)})` : ""}</div>
        <div>Disposition</div><div>${esc(a.disposition)}</div><div>Analyst (pseudonym)</div><div class="mono">${esc(a.analyst)}</div></div>
        <h2 class="section">Lineage — where this number came from</h2><div class="kv">
        <div>Submission</div><div class="mono">${esc(l.record.submission_id)}</div>
        <div>Source file · row</div><div class="mono">${esc(l.record.source_file)} · row ${l.record.source_row}</div>
        ${l.receipts.filter((r) => r.file === l.record.source_file).map((r) => `<div>SHA-256 receipt</div><div class="mono" style="word-break:break-all">${esc(r.sha256)}</div><div>Received</div><div>${esc(r.received_at)} · ${r.rows} rows</div>`).join("")}
        <div>Rejected rows in submission</div><div>${l.rejected_rows_in_submission}</div>
        <div>Audit chain</div><div style="color:${l.audit_chain.intact ? "var(--ok)" : "var(--bad)"}">${l.audit_chain.intact ? "intact" : "BROKEN"} · ${l.audit_chain.entries} entries</div>
        <div>Engine · catalogue</div><div class="mono">${esc(l.engine)} · ${esc(l.catalogue)}</div></div></div>
    </div>`;
}

/* ---------- validation & method ---------- */
async function viewValidation() {
  navOn("validation");
  const [b, rj, au] = await Promise.all([get("/api/benchmark").catch(() => null), get("/api/rejects"), get("/api/audit/verify")]);
  const rjAgg = {};
  rj.forEach((r) => { rjAgg[r.reason] = (rjAgg[r.reason] || 0) + r.rows; });
  $app.innerHTML = `<h1>Validation & data quality</h1>
    <p class="muted">The brief asks for validation against expert manual review. On synthetic data the "expert" is the planted ground truth, which the detection code never reads.</p>
    ${b ? `<div class="grid g4 section">
      <div class="card kpi"><div class="v">${pct(b.recall)}</div><div class="l">recall · ${b.detected}/${b.planted} planted weaknesses</div></div>
      <div class="card kpi"><div class="v">${pct(b.precision)}</div><div class="l">precision · ${b.false_positives} false positives</div></div>
      <div class="card kpi"><div class="v">${b.clean_entity_false_positives}</div><div class="l">findings on clean entities (${b.clean_entities.length})</div></div>
      <div class="card kpi"><div class="v">${b.related}</div><div class="l">related co-findings (same behaviour, other lens)</div></div></div>
      <div class="card section"><h2>Per archetype</h2><table><thead><tr><th>Planted weakness</th><th class="num">Detected</th></tr></thead><tbody>
      ${b.archetypes.map((a) => `<tr><td>${esc(a.archetype)}</td><td class="num">${a.detected}/${a.expected}</td></tr>`).join("")}</tbody></table>
      ${b.missed_list.length ? `<p class="note">Missed: ${b.missed_list.map((k) => esc(k.join("/"))).join(", ")}</p>` : ""}
      ${b.related_list.length ? `<p class="note">Related: ${b.related_list.map((k) => esc(k.join("/"))).join(", ")}</p>` : ""}</div>` : '<p class="muted">No benchmark run yet.</p>'}
    <div class="grid g2 section">
      <div class="card"><h2>Rejected rows (never silently dropped)</h2><table><thead><tr><th>Reason</th><th class="num">Rows</th></tr></thead><tbody>
        ${Object.entries(rjAgg).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td class="num">${v}</td></tr>`).join("")}</tbody></table></div>
      <div class="card"><h2>Tamper-evident audit log</h2><p style="color:${au.intact ? "var(--ok)" : "var(--bad)"};font-size:18px"><b>${au.intact ? "Chain intact" : "Chain BROKEN"}</b></p>
        <p class="note">${au.entries} hash-chained entries (ingest, score runs, exports). Editing any past entry breaks every later hash.</p></div>
    </div>`;
}
async function viewMethod() {
  navOn("method");
  const m = await get("/api/meta");
  const cat = m.indicators;
  $app.innerHTML = `<h1>Method</h1>
    <div class="card section"><div class="kv">
      <div>Engine · catalogue</div><div class="mono">${esc(m.engine)} · ${esc(m.catalogue_version)}</div>
      <div>ATT&CK reference</div><div>Enterprise v${esc(m.attack)} (offline STIX-derived; tactics incl. TA0005 Stealth, TA0112 Defense Impairment)</div>
      <div>Rates</div><div>Wilson 95% lower bound (conservative for small n)</div>
      <div>Peer comparison</div><div>Modified z = 0.6745·(x − median)/MAD vs same sector & size, leave-one-out; MAD floored at the binomial sampling error</div>
      <div>Concern</div><div>100·clip(M,0,7)/7 → M = 3.5 (NIST outlier line) ↦ 50; policy rules can raise it; concern = max(peer, policy)</div>
      <div>Aggregation</div><div>Power mean p = ${m.power_mean_p} (areas, then SAI) — one serious weakness is not diluted by clean areas</div>
      <div>Uncertainty</div><div>${m.uncertainty_draws} Dirichlet(1) weight draws + p ∈ {1,2,3,6} → rank range, P(top 3)</div>
      <div>Explanations</div><div>Deterministic templates; no AI model, no external service</div></div></div>
    <div class="card section"><h2>Indicator catalogue</h2><div class="scroll"><table><thead><tr><th>ID</th><th>Name</th><th>Area</th><th>Worse</th><th class="num">min n</th><th>Track</th><th>Brief</th></tr></thead><tbody>
      ${Object.entries(cat).map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td>${esc(v.name)}</td><td>${esc(v.area)}</td><td>${v.higher_is_worse ? "higher" : "lower"}</td><td class="num">${v.min_n}</td><td>${esc(v.track)}</td><td>${esc(v.brief)}</td></tr>`).join("")}
    </tbody></table></div></div>`;
}

/* ---------- router ---------- */
function bindRows() {
  document.querySelectorAll("tr[data-href]").forEach((tr) => {
    tr.tabIndex = 0; tr.setAttribute("role", "link");
    tr.onclick = () => (location.hash = tr.dataset.href);
    tr.onkeydown = (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); location.hash = tr.dataset.href; } };
  });
}
async function route() {
  if (!CAT) { try { CAT = (await get("/api/meta")).indicators; } catch (e) { CAT = {}; } }
  const h = decodeURIComponent(location.hash.slice(1) || "/");
  const p = h.split("/").filter(Boolean);
  try {
    if (!p.length) await viewOverview();
    else if (p[0] === "e" && p[2] === "i") await viewIndicator(p[1], p[3], Number(p[4] || 0));
    else if (p[0] === "e") await viewEntity(p[1]);
    else if (p[0] === "case") await viewCase(p[1]);
    else if (p[0] === "validation") await viewValidation();
    else if (p[0] === "method") await viewMethod();
    else await viewOverview();
    window.scrollTo(0, 0);
  } catch (err) {
    $app.innerHTML = `<div class="card"><h2>Could not load this view</h2><p class="muted">${esc(err.message)}</p><p><a href="#/">Back to overview</a></p></div>`;
  }
}
window.addEventListener("hashchange", route);
if (!STATIC) get("/api/meta").then((m) => (document.getElementById("runtag").textContent = `period ${m.latest} · engine ${m.engine} · ATT&CK v${m.attack}`)).catch(() => {});
route();
