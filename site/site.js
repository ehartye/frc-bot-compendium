// Flip bumpers, hide pictures whose host no longer serves them, and search design examples.
const root = document.documentElement;
const flip = document.querySelector(".flip");
function setAlliance(a) {
  root.dataset.alliance = a;
  if (flip) flip.textContent = a === "red" ? "Flip bumpers to blue" : "Flip bumpers to red";
  try { localStorage.setItem("alliance", a); } catch { /* private window */ }
}
setAlliance(root.dataset.alliance || "red");
flip?.addEventListener("click", () => setAlliance(root.dataset.alliance === "red" ? "blue" : "red"));

for (const img of document.querySelectorAll("img[data-hot]")) {
  const gone = () => { const f = img.closest("figure"); if (f && !f.classList.contains("keep")) f.classList.add("broken"); else img.remove(); };
  if (img.complete && !img.naturalWidth) gone(); else img.addEventListener("error", gone);
}

const form = document.querySelector(".finder");
if (form) {
  const out = document.querySelector(".hits"), base = form.dataset.base;
  const stop = new Set("a an the of to and or in for without with while from at on by how it its is".split(" "));
  let all = null;
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const run = async () => {
    const text = form.q.value.trim().toLowerCase(), fn = form.fn.value, season = form.season.value;
    if (!text && !fn && !season) { out.innerHTML = ""; return; }
    all ??= await (await fetch(`${base}data/examples.json`)).json();
    const words = [...new Set(text.match(/[a-z0-9]+/g) || [])].filter((w) => !stop.has(w));
    const rx = words.map((w) => { let x = w; for (const e of ["ing", "ed", "es", "s", "e"]) if (w.endsWith(e) && w.length - e.length >= 3) { x = w.slice(0, -e.length); break; } return new RegExp(`\\b${x}(?:s|es|ed|ing|e|er|ers|ning|ming)?\\b`); });
    const docs = all.map((e) => [e, [e.name, e.type, ...(e.solves || [])].join(" ").toLowerCase(), [...(e.facts || []), ...(e.cost || []), e.instead_of].join(" ").toLowerCase()]);
    const idf = rx.map((r) => Math.log(1 + docs.length / (1 + docs.filter(([, a, b]) => r.test(a) || r.test(b)).length)));
    const hits = docs.filter(([e]) => (!fn || e.functions.includes(fn)) && (!season || String(e.season) === season)).map(([e, a, b]) => {
      let score = 0, n = 0;
      rx.forEach((r, i) => { const s = r.test(a), w = s || r.test(b); if (w) { n += 1; score += idf[i] * (r.test(`${e.name} ${e.type || ""}`.toLowerCase()) ? 4 : s ? 3 : 1); } });
      if (rx.length > 1 && `${a} ${b}`.includes(text.replace(/\s+/g, " "))) score *= 3;
      return [rx.length ? score * n / rx.length : 1, e];
    }).filter(([n]) => n > 0).sort((x, y) => y[0] - x[0] || (y[1].cost?.length || 0) - (x[1].cost?.length || 0)).slice(0, 12);
    out.innerHTML = hits.length ? hits.map(([, e]) => `<li class="sheet"><a class="t" href="${base}${e.season}/${e.team}/#${e.id.split("/")[1]}">${esc(e.name)}</a> <span class="muted">${e.team} ${esc(e.robot || e.team_name)}, ${e.season}</span><p>${esc((e.claims[0] || {}).text || "")}${e.claims[0] && e.claims[0].basis !== "team" ? ` <span class="tag">${({ observer: "observer says", record: "on record", inference: "our reading" })[e.claims[0].basis]}</span>` : ""}</p></li>`).join("")
      : `<li class="sheet">No example matches. Try fewer words, or pick only a job.</li>`;
  };
  form.addEventListener("input", run);
  form.addEventListener("submit", (ev) => { ev.preventDefault(); run(); });
}
