// Ανάλυση GPX αγώνα: προφίλ, ανηφόρες/κατηφόρες, εκτίμηση χρόνου και πλάνο διατροφής.
// Όλα γίνονται στο κινητό. Το GPX αποθηκεύεται απλοποιημένο (ανά 50 m) μόνο σε αυτή τη συσκευή.
import { esc, nf1, mt, clock, store } from './util.js';

const KEY = 'monopati.race';
const STEP = 50; // μέτρα δειγματοληψίας

export const loadRace = () => store.json(KEY, null);
export const saveRace = (r) => store.put(KEY, r);
export const clearRace = () => store.del(KEY);

function hav(a, b) {
  const R = 6371000, toR = Math.PI / 180;
  const dLat = (b[0] - a[0]) * toR, dLon = (b[1] - a[1]) * toR;
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * toR) * Math.cos(b[0] * toR) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

export function parseGPX(text, fileName = '') {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  if (doc.querySelector('parsererror')) throw new Error('Το αρχείο δεν είναι έγκυρο GPX.');
  let pts = [...doc.getElementsByTagName('trkpt')];
  if (pts.length < 2) pts = [...doc.getElementsByTagName('rtept')];
  const raw = pts.map((p) => {
    const e = p.getElementsByTagName('ele')[0];
    return [Number(p.getAttribute('lat')), Number(p.getAttribute('lon')), e ? Number(e.textContent) : NaN];
  }).filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
  if (raw.length < 2) throw new Error('Δεν βρέθηκαν σημεία διαδρομής στο GPX.');
  if (!raw.some((p) => Number.isFinite(p[2]))) throw new Error('Το GPX δεν έχει υψόμετρο. Κατέβασε έκδοση με υψομετρικά (π.χ. από το site του αγώνα ή από Strava/Garmin).');
  // Συμπλήρωση κενών υψομέτρου.
  let last = raw.find((p) => Number.isFinite(p[2]))[2];
  for (const p of raw) { if (Number.isFinite(p[2])) last = p[2]; else p[2] = last; }
  // Αθροιστική απόσταση και επαναδειγματοληψία ανά 50 m.
  const dist = [0];
  for (let i = 1; i < raw.length; i++) dist.push(dist[i - 1] + hav(raw[i - 1], raw[i]));
  const total = dist[dist.length - 1];
  const prof = [];
  let j = 0;
  for (let d = 0; d <= total; d += STEP) {
    while (j < dist.length - 2 && dist[j + 1] < d) j++;
    const span = dist[j + 1] - dist[j] || 1;
    const t = Math.min(1, Math.max(0, (d - dist[j]) / span));
    prof.push(raw[j][2] + (raw[j + 1][2] - raw[j][2]) * t);
  }
  // Εξομάλυνση (κινητός μέσος 250 m) για να μη μετρά ο θόρυβος του GPS ως υψομετρικά.
  const sm = prof.map((_, i) => {
    let s = 0, n = 0;
    for (let k = Math.max(0, i - 2); k <= Math.min(prof.length - 1, i + 2); k++) { s += prof[k]; n++; }
    return Math.round(s / n);
  });
  const name = doc.querySelector('metadata > name, trk > name')?.textContent?.trim() || fileName.replace(/\.gpx$/i, '') || 'Αγώνας';
  return { name, ele: sm, step: STEP, saved: new Date().toISOString(), aid: [], carbs: 70, heat: 'mild' };
}

// Τμήματα: εναλλαγές ανηφόρας/κατηφόρας με υστέρηση 40 m, ώστε τα μικρά κυματάκια να μη σπάνε τα τμήματα.
function legs(ele) {
  const H = 40;
  const ext = [0];
  let trend = 0, piv = 0, hi = 0, lo = 0;
  for (let i = 1; i < ele.length; i++) {
    if (trend === 0) {
      if (ele[i] > ele[hi]) hi = i;
      if (ele[i] < ele[lo]) lo = i;
      if (ele[hi] - ele[lo] >= H) {
        if (hi > lo) { if (lo > 0) ext.push(lo); trend = 1; piv = hi; } else { if (hi > 0) ext.push(hi); trend = -1; piv = lo; }
      }
    } else if (trend === 1) {
      if (ele[i] >= ele[piv]) piv = i;
      else if (ele[piv] - ele[i] >= H) { ext.push(piv); trend = -1; piv = i; }
    } else {
      if (ele[i] <= ele[piv]) piv = i;
      else if (ele[i] - ele[piv] >= H) { ext.push(piv); trend = 1; piv = i; }
    }
  }
  if (ext[ext.length - 1] !== ele.length - 1) ext.push(ele.length - 1);
  return ext;
}

// Κόστος (σε «km προσπάθειας») για κάθε βήμα 50 m, ώστε χρόνος = κόστος × ρυθμός προσπάθειας.
function stepCost(dz, dx) {
  const g = dz / dx;
  const km = dx / 1000;
  if (dz >= 0) return km + dz / 100;
  const a = -g;
  if (a <= 0.1) return km * (1 - 3 * a); // ήπια κατηφόρα: πιο γρήγορα
  return km * (0.7 + Math.max(0, a - 0.1) * 3); // απότομη: φρενάρισμα, πιο αργά
}

export function analyse(race, pace) {
  const { ele, step } = race;
  const n = ele.length;
  const cum = [0]; // λεπτά
  let gain = 0, loss = 0, t = 0;
  for (let i = 1; i < n; i++) {
    const dz = ele[i] - ele[i - 1];
    if (dz > 0) gain += dz; else loss -= dz;
    const fatigue = 1 + 0.04 * Math.max(0, t / 60 - 2); // επιβράδυνση μετά τις 2 ώρες
    t += stepCost(dz, step) * pace * fatigue;
    cum.push(t);
  }
  const km = ((n - 1) * step) / 1000;
  const ext = legs(ele);
  const segs = [];
  for (let k = 1; k < ext.length; k++) {
    const a = ext[k - 1], b = ext[k];
    let g = 0, l = 0;
    for (let i = a + 1; i <= b; i++) { const dz = ele[i] - ele[i - 1]; if (dz > 0) g += dz; else l -= dz; }
    const len = ((b - a) * step) / 1000;
    const net = ele[b] - ele[a];
    const grade = len ? net / (len * 10) : 0;
    const type = Math.abs(grade) < 3 ? 'flat' : net > 0 ? 'up' : 'down';
    segs.push({ a, b, from: (a * step) / 1000, to: (b * step) / 1000, km: len, gain: g, loss: l, grade, type, min: cum[b] - cum[a], at: cum[b] });
  }
  const climbs = segs.filter((s) => s.type === 'up' && s.gain >= 100);
  return { km, gain, loss, minutes: t, cum, segs, climbs, top: Math.max(...ele), low: Math.min(...ele) };
}

const HEAT = { cool: ['Δροσερό (<15°)', 450, 350], mild: ['Ήπιο (15–25°)', 600, 500], hot: ['Ζεστό (>25°)', 800, 700] };

function fuelSectors(race, an) {
  const step = race.step;
  const idx = (km) => Math.min(race.ele.length - 1, Math.max(0, Math.round((km * 1000) / step)));
  const marks = [0, ...race.aid.filter((k) => k > 0 && k < an.km).sort((a, b) => a - b), an.km];
  const [, ml, na] = HEAT[race.heat] || HEAT.mild;
  const out = [];
  for (let k = 1; k < marks.length; k++) {
    const a = idx(marks[k - 1]), b = idx(marks[k]);
    let g = 0, l = 0;
    for (let i = a + 1; i <= b; i++) { const dz = race.ele[i] - race.ele[i - 1]; if (dz > 0) g += dz; else l -= dz; }
    const min = an.cum[b] - an.cum[a];
    const h = min / 60;
    out.push({ from: marks[k - 1], to: marks[k], gain: g, loss: l, min, at: an.cum[b],
      carbs: race.carbs * h, gels: (race.carbs * h) / 25, ml: ml * h, na: na * h });
  }
  return out;
}

function profileSvg(race, an) {
  const W = 700, H = 190, top = 14, bot = 30;
  const { ele, step } = race;
  const lo = an.low - 30, hi = an.top + 30;
  const x = (i) => (i / (ele.length - 1)) * W;
  const y = (e) => top + (H - top - bot) * (1 - (e - lo) / (hi - lo || 1));
  const every = Math.max(1, Math.floor(ele.length / 350));
  let d = `M0,${H - bot}`;
  for (let i = 0; i < ele.length; i += every) d += ` L${x(i).toFixed(1)},${y(ele[i]).toFixed(1)}`;
  d += ` L${W},${y(ele[ele.length - 1]).toFixed(1)} L${W},${H - bot} Z`;
  const climbs = an.climbs.map((c) => {
    let p = `M${x(c.a).toFixed(1)},${H - bot}`;
    for (let i = c.a; i <= c.b; i += every) p += ` L${x(i).toFixed(1)},${y(ele[i]).toFixed(1)}`;
    p += ` L${x(c.b).toFixed(1)},${y(ele[c.b]).toFixed(1)} L${x(c.b).toFixed(1)},${H - bot} Z`;
    return `<path class="climb" d="${p}"/>`;
  }).join('');
  const tickEvery = an.km > 60 ? 10 : 5;
  let ticks = '';
  for (let k = tickEvery; k < an.km; k += tickEvery) {
    const xi = x((k * 1000) / step);
    ticks += `<line class="tick" x1="${xi}" x2="${xi}" y1="${H - bot}" y2="${H - bot + 5}"/><text class="lbl" x="${xi}" y="${H - 8}">${k}</text>`;
  }
  const aid = race.aid.filter((k) => k > 0 && k < an.km).map((k) => {
    const i = Math.round((k * 1000) / step);
    return `<line class="aid" x1="${x(i)}" x2="${x(i)}" y1="${y(ele[i])}" y2="${H - bot}"/><circle class="aid-dot" cx="${x(i)}" cy="${y(ele[i])}" r="5"/>`;
  }).join('');
  return `<svg class="profile" viewBox="0 0 ${W} ${H}" role="img" aria-label="Υψομετρικό προφίλ: ${nf1.format(an.km)} km, +${mt(an.gain)} m, υψηλότερο σημείο ${mt(an.top)} m">
    <path class="area" d="${d}"/>${climbs}${aid}<line class="base" x1="0" x2="${W}" y1="${H - bot}" y2="${H - bot}"/>${ticks}
    <text class="lbl l" x="2" y="${y(an.top) - 4}">${mt(an.top)} m</text></svg>`;
}

export function viewRaceAnalysis(race, pace, planRace) {
  if (!race) {
    return `<section class="card upload"><h3>Ανάλυση διαδρομής (GPX)</h3>
      <p class="muted">Ανέβασε το GPX του αγώνα για υψομετρικό προφίλ, ανηφόρες, εκτίμηση χρόνου ανά τμήμα και πλάνο διατροφής.</p>
      <label class="btn file">Επιλογή αρχείου GPX<input type="file" id="gpx" accept=".gpx,application/gpx+xml,application/xml,text/xml" hidden></label>
      <p class="error" id="gpx-err" role="alert"></p></section>`;
  }
  const an = analyse(race, pace);
  const sectors = fuelSectors(race, an);
  const tot = sectors.reduce((a, s) => ({ carbs: a.carbs + s.carbs, ml: a.ml + s.ml, na: a.na + s.na }), { carbs: 0, ml: 0, na: 0 });
  const mismatch = planRace && (Math.abs(an.km - planRace.km) / planRace.km > 0.15 || Math.abs(an.gain - planRace.gain) / planRace.gain > 0.25);
  const segRows = an.segs.map((s) => `<tr class="${s.type}"><td>${nf1.format(s.from)}–${nf1.format(s.to)}</td>
      <td>${s.type === 'up' ? '▲' : s.type === 'down' ? '▼' : '–'} ${s.type === 'up' ? `+${mt(s.gain)}` : s.type === 'down' ? `−${mt(s.loss)}` : `${mt(s.gain)}/${mt(s.loss)}`} m</td>
      <td>${nf1.format(Math.abs(s.grade))}%</td><td>${clock(s.min)}</td><td>${clock(s.at)}</td></tr>`).join('');
  const secRows = sectors.map((s) => `<tr><td>${nf1.format(s.from)}–${nf1.format(s.to)}</td><td>+${mt(s.gain)}/−${mt(s.loss)}</td>
      <td>${clock(s.min)}</td><td>${mt(s.carbs)} g <small>(${nf1.format(s.gels)} τζελ)</small></td><td>${nf1.format(s.ml / 1000)} L</td></tr>`).join('');
  const heatOpts = Object.entries(HEAT).map(([k, [l]]) => `<option value="${k}"${race.heat === k ? ' selected' : ''}>${l}</option>`).join('');
  const carbOpts = [40, 50, 60, 70, 80, 90].map((c) => `<option value="${c}"${race.carbs === c ? ' selected' : ''}>${c} g/ώρα</option>`).join('');
  return `<section class="card">
    <div class="sec-h"><h3>${esc(race.name)}</h3><button class="link" id="gpx-clear">Αφαίρεση</button></div>
    <div class="stats4"><div><b>${nf1.format(an.km)}</b><span>km</span></div><div><b>+${mt(an.gain)}</b><span>m</span></div>
      <div><b>−${mt(an.loss)}</b><span>m</span></div><div><b>${clock(an.minutes)}</b><span>εκτίμηση</span></div></div>
    ${profileSvg(race, an)}
    ${mismatch ? `<p class="banner info">Το GPX διαφέρει αρκετά από τον αγώνα του προγράμματος (${planRace.km} km, +${planRace.gain} m). Αν άλλαξε η διαδρομή, ενημέρωσε το config.json.</p>` : ''}
    <p class="muted small">Ο χρόνος βγαίνει από τον ρυθμό προσπάθειας των προπονήσεών σου (${nf1.format(pace)} λ ανά km προσπάθειας), με επιβράδυνση στις απότομες κατηφόρες και κόπωση μετά τις 2 ώρες. Είναι εκτίμηση, όχι στόχος.</p>
    <p class="kpi-line"><b>${an.climbs.length}</b> μεγάλες ανηφόρες (πάνω από 100 m)${an.climbs.length ? `: ${an.climbs.map((c) => `km ${nf1.format(c.from)} (+${mt(c.gain)} m, ${nf1.format(c.grade)}%)`).join(' · ')}` : ''}</p>
    <details class="tbl"><summary>Τμήματα διαδρομής (${an.segs.length})</summary>
      <div class="scroll"><table><thead><tr><th>km</th><th>Υψομ.</th><th>Κλίση</th><th>Χρόνος</th><th>Άφιξη</th></tr></thead><tbody>${segRows}</tbody></table></div></details>
  </section>
  <section class="card">
    <h3>Πλάνο διατροφής αγώνα</h3>
    <div class="form-row">
      <label>Υδατάνθρακες<select id="f-carbs">${carbOpts}</select></label>
      <label>Καιρός<select id="f-heat">${heatOpts}</select></label>
    </div>
    <label class="full">Σταθμοί ανεφοδιασμού (km, χωρισμένα με κόμμα)
      <input id="f-aid" inputmode="decimal" value="${esc(race.aid.join(', '))}" placeholder="π.χ. 8.5, 17, 26, 33"></label>
    <div class="stats4"><div><b>${mt(tot.carbs)}</b><span>g υδατ.</span></div><div><b>${mt(tot.carbs / 25)}</b><span>τζελ (25 g)</span></div>
      <div><b>${nf1.format(tot.ml / 1000)}</b><span>L υγρά</span></div><div><b>${mt(tot.na)}</b><span>mg νάτριο</span></div></div>
    <div class="scroll"><table><thead><tr><th>${race.aid.length ? 'Από σταθμό σε σταθμό (km)' : 'km'}</th><th>Υψομ.</th><th>Χρόνος</th><th>Φάε</th><th>Πιες</th></tr></thead><tbody>${secRows}</tbody></table></div>
    <p class="muted small">Τρώγε μικρές δόσεις κάθε 20–30 λεπτά από το πρώτο μισάωρο. Τα υγρά και το νάτριο εξαρτώνται πολύ από τον ιδρώτα σου. Δοκίμασε το πλάνο στα μακριά τρεξίματα.</p>
  </section>`;
}

export function bindRaceAnalysis(root, rerender) {
  const inp = root.querySelector('#gpx');
  if (inp) {
    inp.onchange = async () => {
      const f = inp.files[0];
      if (!f) return;
      try {
        const r = parseGPX(await f.text(), f.name);
        saveRace(r);
        rerender();
      } catch (e) {
        root.querySelector('#gpx-err').textContent = e.message || 'Δεν διαβάστηκε το αρχείο.';
      }
    };
  }
  const race = loadRace();
  if (!race) return;
  const upd = (fn) => { fn(race); saveRace(race); rerender(); };
  const clr = root.querySelector('#gpx-clear');
  if (clr) clr.onclick = () => { clearRace(); rerender(); };
  const c = root.querySelector('#f-carbs');
  if (c) c.onchange = () => upd((r) => { r.carbs = Number(c.value); });
  const h = root.querySelector('#f-heat');
  if (h) h.onchange = () => upd((r) => { r.heat = h.value; });
  const a = root.querySelector('#f-aid');
  if (a) a.onchange = () => upd((r) => { r.aid = a.value.split(/[,;\s]+/).map((x) => Number(x.replace(',', '.'))).filter((x) => x > 0); });
}
