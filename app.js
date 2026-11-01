import { decryptVault } from './vault.js';

const app = document.getElementById('app');
const tabs = document.getElementById('tabs');
const PW_KEY = 'monopati.pw';
const TABS = [['today', 'Σήμερα'], ['plan', 'Πρόγραμμα'], ['progress', 'Πρόοδος']];

let data = null;
let view = 'today';
let played = false;

// --- Βοηθητικά --------------------------------------------------------------
const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* αγνοείται */ } },
  del: (k) => { try { localStorage.removeItem(k); } catch { /* αγνοείται */ } },
};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nf1 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 0 });
const km = (n) => nf1.format(n);
const mt = (n) => nf0.format(n);
const dur = (m) => {
  const h = Math.floor(m / 60);
  const mm = Math.round(m % 60);
  return h ? `${h} ώρ ${String(mm).padStart(2, '0')} λ` : `${mm} λ`;
};
const localISO = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const atNoon = (iso) => new Date(`${iso}T12:00:00`);
const longDate = (iso) => atNoon(iso).toLocaleDateString('el-GR', { weekday: 'long', day: 'numeric', month: 'long' });
const shortDate = (iso) => atNoon(iso).toLocaleDateString('el-GR', { day: 'numeric', month: 'short' });
const dayDiff = (a, b) => Math.round((atNoon(a) - atNoon(b)) / 86400000);

// --- Εκκίνηση ----------------------------------------------------------------
async function fetchBlob() {
  let res;
  try { res = await fetch('data.enc', { cache: 'no-store' }); } catch { throw new Error('offline'); }
  if (!res.ok) throw new Error('missing');
  return res.json();
}

async function boot() {
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
  let blob;
  try { blob = await fetchBlob(); } catch (e) { return renderProblem(e.message); }
  const saved = store.get(PW_KEY);
  if (saved) {
    try { data = await decryptVault(blob, saved); return renderApp(); } catch { store.del(PW_KEY); }
  }
  renderLock(blob);
}

function renderProblem(kind) {
  tabs.hidden = true;
  const text = kind === 'offline'
    ? '<p>Δεν υπάρχει σύνδεση και δεν έχει αποθηκευτεί προηγούμενη ενημέρωση. Άνοιξε ξανά την εφαρμογή όταν συνδεθείς.</p>'
    : '<p>Δεν υπάρχουν δεδομένα ακόμα. Στο GitHub άνοιξε Actions, διάλεξε «Daily update» και πάτα Run workflow. Σε ένα λεπτό θα είναι έτοιμα.</p>';
  app.innerHTML = `<section class="problem"><h1>Μονοπάτι</h1>${text}<button class="btn" id="retry">Δοκίμασε ξανά</button></section>`;
  document.getElementById('retry').onclick = () => location.reload();
}

function renderLock(blob, msg = '') {
  tabs.hidden = true;
  app.innerHTML = `
    <form class="lock" id="lock">
      <h1>Μονοπάτι</h1>
      <p>Το πρόγραμμα τρεξίματος για τον αγώνα σου. Γράψε τον κωδικό για να ανοίξει.</p>
      <label for="pw">Κωδικός</label>
      <input id="pw" type="password" autocomplete="current-password" required>
      <label class="check"><input type="checkbox" id="rem" checked> Να με θυμάσαι σε αυτή τη συσκευή</label>
      <p class="error" id="err" role="alert">${esc(msg)}</p>
      <button class="btn" type="submit">Άνοιγμα</button>
    </form>`;
  const form = document.getElementById('lock');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button');
    const pw = document.getElementById('pw').value;
    btn.disabled = true;
    btn.textContent = 'Άνοιγμα…';
    try {
      data = await decryptVault(blob, pw);
      if (document.getElementById('rem').checked) store.set(PW_KEY, pw);
      renderApp();
    } catch {
      document.getElementById('err').textContent = 'Ο κωδικός δεν είναι σωστός. Δοκίμασε ξανά.';
      btn.disabled = false;
      btn.textContent = 'Άνοιγμα';
    }
  });
  document.getElementById('pw').focus();
}

// --- Κύρια εφαρμογή -------------------------------------------------------------
function renderApp() {
  tabs.hidden = false;
  tabs.innerHTML = TABS.map(([id, label]) =>
    `<button data-view="${id}"${view === id ? ' aria-current="page"' : ''}>${label}</button>`).join('');
  const views = { today: viewToday, plan: viewPlan, progress: viewProgress };
  app.innerHTML = banners() + views[view]();
  window.scrollTo(0, 0);
}

tabs.addEventListener('click', (e) => {
  const b = e.target.closest('button[data-view]');
  if (!b) return;
  view = b.dataset.view;
  renderApp();
});
app.addEventListener('click', (e) => {
  if (e.target.id === 'forget') { store.del(PW_KEY); location.reload(); }
});

function banners() {
  let out = '';
  const ageH = (Date.now() - new Date(data.generated_at).getTime()) / 3600000;
  if (ageH > 36) {
    out += `<p class="banner">Το πρόγραμμα δεν έχει ενημερωθεί από ${esc(longDate(data.generated_at.slice(0, 10)))}. Έλεγξε στο GitHub (Actions) αν η καθημερινή ενημέρωση απέτυχε.</p>`;
  }
  if (data.demo) out += '<p class="banner info">Αυτά είναι δοκιμαστικά δεδομένα, όχι δικά σου.</p>';
  return out;
}

function currentWeek(today) {
  return data.plan.find((w) => w.days.some((d) => d.date === today));
}

function dayStatus(day, today) {
  if (day.done && day.km > 0) return { cls: 'done', text: 'Έγινε' };
  if (day.done) return { cls: 'extra', text: 'Έτρεξες' };
  if (day.date === today) return { cls: 'today', text: 'Σήμερα' };
  if (day.date < today && day.km > 0) return { cls: 'missed', text: 'Δεν έγινε' };
  return { cls: '', text: '' };
}

const doneText = (d) => `Έγινε: ${km(d.km)} km, +${mt(d.gain)} m, ${dur(d.minutes)}`;

// Η εβδομάδα σαν κορφογραμμή: ύψος = θετική υψομετρική, πλάτος = απόσταση.
function ridge(week, today, animate) {
  const W = 700, base = 104;
  const maxG = Math.max(300, ...week.days.map((d) => d.gain));
  let peaks = '', labels = '';
  week.days.forEach((d, i) => {
    const cx = 50 + i * 100;
    const isToday = d.date === today;
    if (d.km > 0) {
      const h = 14 + (d.gain / maxG) * 74;
      const hw = 22 + Math.min(26, d.km * 1.3);
      const missed = d.date < today && !d.done && d.kind !== 'race';
      const cls = ['peak', d.done ? 'done' : '', missed ? 'missed' : '', isToday ? 'today' : ''].join(' ').trim();
      peaks += `<path class="${cls}" style="--i:${i}" d="M${cx - hw},${base} Q${cx - hw * 0.35},${base} ${cx},${base - h} Q${cx + hw * 0.35},${base} ${cx + hw},${base}Z"/>`;
    }
    if (isToday) labels += `<rect class="pill" x="${cx - 32}" y="118" width="64" height="30" rx="15"/>`;
    labels += `<text class="lbl${isToday ? ' is-today' : ''}" x="${cx}" y="140" text-anchor="middle">${esc(d.dow.slice(0, 3))}</text>`;
  });
  const summary = week.days.filter((d) => d.km > 0).map((d) => `${d.dow} ${km(d.km)} χλμ`).join(', ');
  return `<svg class="ridge${animate ? ' play' : ''}" viewBox="0 0 ${W} 156" role="img" aria-label="Η εβδομάδα: ${esc(summary)}">
    <line class="ground" x1="0" x2="${W}" y1="${base}" y2="${base}"/>${peaks}${labels}</svg>`;
}

function viewToday() {
  const today = localISO();
  const week = currentWeek(today);
  const day = week && week.days.find((d) => d.date === today);
  const race = data.race;
  let sub = '';
  if (race) {
    const n = dayDiff(race.date, today);
    sub = n > 0 ? `${esc(race.name)}, σε ${n} ${n === 1 ? 'ημέρα' : 'ημέρες'}` : n === 0 ? `${esc(race.name)}: σήμερα!` : '';
  }
  let html = `<header class="top"><h1>Μονοπάτι</h1><p class="sub">${sub}</p></header>`;

  if (!week || !day) {
    return html + '<p>Δεν υπάρχει πρόγραμμα για σήμερα. Τα δεδομένα είναι παλιά, οπότε περίμενε την επόμενη ενημέρωση.</p>';
  }

  html += `<section><p class="when">${esc(longDate(today))}</p><h2>${esc(day.title)}</h2>`;
  if (day.km > 0) {
    html += `<p class="figures"><span><b>${km(day.km)}</b> km</span><span><b>+${mt(day.gain)}</b> m</span><span><b>${dur(day.minutes)}</b></span></p>`;
  } else if (day.minutes > 0) {
    html += `<p class="figures"><span><b>${dur(day.minutes)}</b></span></p>`;
  } else {
    html += '<p class="figures"></p>';
  }
  html += `<p class="desc">${esc(day.desc)}</p>`;
  if (day.adjust) html += `<p class="adjust">${esc(day.adjust)}</p>`;
  if (day.done) html += `<p class="done-note">${esc(doneText(day.done))}</p>`;
  html += '</section>';

  html += `<section class="week-now"><h3>Η εβδομάδα σου</h3>
    <p class="meta">${esc(week.label)}: ${km(week.km)} km, +${mt(week.gain)} m</p>${ridge(week, today, !played)}</section>`;
  played = true;

  const w = data.wellness || {};
  const vit = [];
  if (w.readiness != null) vit.push(['Ετοιμότητα', `${nf0.format(w.readiness)}`, 'από 100']);
  if (w.sleep_score != null) vit.push(['Ύπνος', `${nf0.format(w.sleep_score)}`, 'από 100']);
  if (w.resting_hr != null) vit.push(['Παλμοί ηρεμίας', `${nf0.format(w.resting_hr)}`, 'bpm']);
  if (w.hrv != null) vit.push(['HRV τη νύχτα', `${nf0.format(w.hrv)}`, 'ms']);
  if (vit.length) {
    html += `<dl class="vitals">${vit.map(([k, v, u]) => `<div><dt>${k}</dt><dd>${v} <small>${u}</small></dd></div>`).join('')}</dl>`;
  }

  const advice = (data.status && data.status.advice) || [];
  if (advice.length) {
    html += `<section class="notes"><h3>Προσαρμογές του προγράμματος</h3><ul>${advice.map((a) => `<li>${esc(a)}</li>`).join('')}</ul></section>`;
  }
  return html;
}

function viewPlan() {
  const today = localISO();
  const cur = currentWeek(today);
  const weeks = data.plan.map((w) => {
    const isCur = cur && w.week_start === cur.week_start;
    const days = w.days.map((d) => {
      const st = dayStatus(d, today);
      const nums = d.km > 0 ? `${km(d.km)} km, +${mt(d.gain)} m` : d.minutes > 0 ? dur(d.minutes) : '';
      return `<details class="day ${st.cls}"><summary>
          <span class="d">${esc(d.dow.slice(0, 3))}</span><span class="t">${esc(d.title)}</span><span class="n">${nums}</span>
          ${st.text ? `<span class="s">${st.text}</span>` : ''}
        </summary><div class="body"><p>${esc(d.desc)}</p>
        ${d.km > 0 ? `<p class="muted">Περίπου ${dur(d.minutes)}</p>` : ''}
        ${d.done ? `<p class="done-note">${esc(doneText(d.done))}</p>` : ''}</div></details>`;
    }).join('');
    return `<details class="week${isCur ? ' current' : ''}"${isCur ? ' open' : ''}>
      <summary><span class="wk">Εβδομάδα ${esc(shortDate(w.week_start))}</span><span class="wt">${km(w.km)} km</span>
      <span class="wl">${esc(w.label)}</span><span class="wt">+${mt(w.gain)} m</span></summary>
      <div class="days">${days}</div></details>`;
  }).join('');
  return `<header class="top page-title"><h1>Πρόγραμμα</h1></header>${weeks}`;
}

function barChart(items, key, title) {
  const W = 700, H = 200, top = 24, bottom = 44, plotH = H - top - bottom;
  const actual = (it) => (it.future ? 0 : it[key]);
  const planned = (it) => (it.plan ? it.plan[key] : 0);
  const max = Math.max(1, ...items.map((it) => Math.max(actual(it), planned(it))));
  const slot = W / items.length, bw = slot * 0.58;
  const y = (v) => top + plotH * (1 - v / max);
  let bars = '', texts = '';
  items.forEach((it, i) => {
    const x = i * slot + (slot - bw) / 2, cx = i * slot + slot / 2;
    const p = planned(it), a = actual(it);
    if (p > 0 && (it.future || it.current)) bars += `<rect class="plan" x="${x}" y="${y(p)}" width="${bw}" height="${plotH * (p / max)}"/>`;
    if (a > 0) bars += `<rect class="act" x="${x}" y="${y(a)}" width="${bw}" height="${plotH * (a / max)}"/>`;
    const shown = it.future || it.current ? p || a : a;
    if (shown > 0) texts += `<text class="val" x="${cx}" y="${y(Math.max(a, p)) - 5}">${mt(shown)}</text>`;
    if (i % 2 === 0 || it.current) texts += `<text class="lbl" x="${cx}" y="${H - 18}">${esc(shortDate(it.start))}</text>`;
    if (it.current) texts += `<rect class="pill" x="${cx - 24}" y="${H - 10}" width="48" height="5" rx="2"/>`;
  });
  const desc = items.map((it) => `${shortDate(it.start)}: ${mt(it.future ? planned(it) : actual(it))}`).join(', ');
  return `<div class="chart"><h3>${title}</h3>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}. ${esc(desc)}">${bars}${texts}</svg></div>`;
}

function viewProgress() {
  const hist = data.history.slice(-6);
  const curStart = hist[hist.length - 1].week_start;
  const byStart = Object.fromEntries(data.plan.map((w) => [w.week_start, w]));
  const items = hist.map((h) => ({ start: h.week_start, km: h.km, gain: h.gain, plan: byStart[h.week_start], current: h.week_start === curStart }))
    .concat(data.plan.filter((w) => w.week_start > curStart).slice(0, 6).map((w) => ({ start: w.week_start, plan: w, future: true })));

  const p = data.profile || {};
  let html = `<header class="top page-title"><h1>Πρόοδος</h1>
    <p class="sub">Μέσος όρος 4 εβδομάδων: ${km(p.base_km || 0)} km, +${mt(p.base_gain || 0)} m</p></header>`;
  html += barChart(items, 'km', 'Χιλιόμετρα ανά εβδομάδα');
  html += barChart(items, 'gain', 'Θετική υψομετρική ανά εβδομάδα (μέτρα)');
  html += '<p class="legend">Συμπαγείς στήλες: όσα έτρεξες. Διακεκομμένες: το πρόγραμμα.</p>';

  const recent = (data.recent || []).map((r) => `<li><span class="dt">${esc(shortDate(r.date))}</span>
    <span class="nm">${esc(r.name || 'Τρέξιμο')}</span>
    <span class="nu">${km(r.km)} km, +${mt(r.gain)} m${r.avg_hr ? `, ${r.avg_hr} bpm` : ''}</span></li>`).join('');
  html += `<section class="recent"><h3>Τελευταία τρεξίματα</h3>${recent ? `<ul>${recent}</ul>` : '<p class="muted">Δεν βρέθηκαν τρεξίματα.</p>'}</section>`;

  const upd = new Date(data.generated_at).toLocaleString('el-GR', { dateStyle: 'long', timeStyle: 'short' });
  html += `<footer class="foot"><p>Τελευταία ενημέρωση: ${esc(upd)}</p>
    <p>Γενικό πρόγραμμα προπόνησης, όχι ιατρική συμβουλή. Αν νιώσεις πόνο ή ασυνήθιστη κούραση, σταμάτα και ξεκουράσου.</p>
    <button class="link" id="forget">Κλείδωμα εφαρμογής</button></footer>`;
  return html;
}

boot();
