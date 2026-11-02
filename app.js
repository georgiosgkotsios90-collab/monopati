import { decryptVault } from './vault.js';
import { esc, nf1, nf0, mt, dur, clock, localISO, longDate, shortDate, dayDiff, store, atNoon } from './util.js';
import { loadEdits, applyEdits, swapDays, toggleSkip, setExtra, setScale, resetEdits, hasEdits } from './edits.js';
import { runSession, stepsToItems } from './timer.js';
import { viewLibrary, bindLibrary, startSession, fuelForRun } from './library.js';
import { viewRaceAnalysis, bindRaceAnalysis, loadRace } from './gpx.js';

const app = document.getElementById('app');
const tabs = document.getElementById('tabs');
const PW_KEY = 'monopati.pw';
const ICON = {
  today: '<path d="M4 18 L9 9 L13 14 L16 10 L20 18 Z"/>',
  plan: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
  race: '<path d="M6 21V4M6 4h11l-2 4 2 4H6"/>',
  form: '<path d="M3 17l5-6 4 3 4-7 5 5"/>',
  lib: '<path d="M6 9v6M18 9v6M3 11v2M21 11v2M6 12h12"/>',
};
const TABS = [['today', 'Σήμερα'], ['plan', 'Πρόγραμμα'], ['race', 'Αγώνας'], ['form', 'Φόρμα'], ['lib', 'Εργαλεία']];
const KIND_TAG = {
  easy: 'ΕΥΚΟΛΟ', easy2: 'ΕΥΚΟΛΟ + STRIDES', quality: 'ΠΟΙΟΤΙΚΗ', long: 'ΜΑΚΡΥ', medium: 'ΜΕΤΡΙΟ',
  strength: 'ΔΥΝΑΜΗ', rest: 'ΞΕΚΟΥΡΑΣΗ', recover: 'ΑΝΑΚΑΜΨΗ', prerace: 'ΠΡΙΝ ΤΟΝ ΑΓΩΝΑ', shakeout: 'ΞΕΜΟΥΔΙΑΣΜΑ', race: 'ΑΓΩΝΑΣ',
};

let data = null;
let view = store.get('monopati.view') || 'today';
let played = false;
const edits = loadEdits();
let plan = [];

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
  app.innerHTML = `<section class="problem"><h1 class="brand">ΜΟΝΟΠΑΤΙ</h1>${text}<button class="btn" id="retry">Δοκίμασε ξανά</button></section>`;
  document.getElementById('retry').onclick = () => location.reload();
}

function renderLock(blob, msg = '') {
  tabs.hidden = true;
  app.innerHTML = `
    <form class="lock" id="lock">
      <svg class="lock-art" viewBox="0 0 200 80" aria-hidden="true"><path d="M0 80 L45 30 L70 52 L110 8 L150 46 L170 32 L200 60 L200 80 Z"/></svg>
      <h1 class="brand">ΜΟΝΟΠΑΤΙ</h1>
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
function renderApp(keepScroll = false) {
  plan = applyEdits(data.plan, edits, data.lthr || 155);
  tabs.hidden = false;
  tabs.innerHTML = TABS.map(([id, label]) =>
    `<button data-view="${id}"${view === id ? ' aria-current="page"' : ''}><svg viewBox="0 0 24 24" aria-hidden="true">${ICON[id]}</svg><span>${label}</span></button>`).join('');
  const views = { today: viewToday, plan: viewPlan, race: viewRace, form: viewForm, lib: viewLibrary };
  if (!views[view]) view = 'today';
  const y = window.scrollY;
  const open = keepScroll ? [...app.querySelectorAll('details[open][data-k]')].map((d) => d.dataset.k) : [];
  app.innerHTML = banners() + views[view]();
  for (const k of open) { const d = app.querySelector(`details[data-k="${k}"]`); if (d) d.open = true; }
  if (view === 'lib') bindLibrary(app, () => renderApp(true));
  if (view === 'race') bindRaceAnalysis(app, () => renderApp(true));
  window.scrollTo(0, keepScroll ? y : 0);
}

tabs.addEventListener('click', (e) => {
  const b = e.target.closest('button[data-view]');
  if (!b) return;
  view = b.dataset.view;
  store.set('monopati.view', view);
  renderApp();
});

const findDay = (date) => { for (const w of plan) for (const d of w.days) if (d.date === date) return d; return null; };

app.addEventListener('click', (e) => {
  const t = e.target.closest('[data-act]');
  if (!t) { if (e.target.id === 'forget') { store.del(PW_KEY); location.reload(); } return; }
  const { act, date } = t.dataset;
  if (act === 'skip') { toggleSkip(edits, date); renderApp(true); }
  if (act === 'extra') { setExtra(edits, date, Number(t.dataset.min) || 0); renderApp(true); }
  if (act === 'scale') { setScale(edits, t.dataset.week, Number(t.dataset.f)); renderApp(true); }
  if (act === 'reset') { resetEdits(edits); renderApp(true); }
  if (act === 'timer') { const d = findDay(date); if (d && d.steps) runSession(d.title, stepsToItems(d.steps)); }
  if (act === 'session') startSession(t.dataset.key);
  if (act === 'goto') { view = t.dataset.view; store.set('monopati.view', view); renderApp(); }
});
app.addEventListener('change', (e) => {
  const s = e.target.closest('select[data-act="move"]');
  if (!s || !s.value) return;
  swapDays(edits, s.dataset.date, s.value);
  renderApp(true);
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

const currentWeek = (today) => plan.find((w) => w.days.some((d) => d.date === today));

function dayStatus(day, today) {
  if (day.done && day.km > 0) return { cls: 'done', text: 'Έγινε' };
  if (day.done) return { cls: 'extra', text: 'Έτρεξες' };
  if (day.skipped) return { cls: 'skipped', text: 'Παράλειψη' };
  if (day.date === today) return { cls: 'today', text: 'Σήμερα' };
  if (day.date < today && day.km > 0) return { cls: 'missed', text: 'Δεν έγινε' };
  return { cls: '', text: '' };
}

function formState(tsb) {
  if (tsb < -30) return ['alert', 'Υπερφόρτωση'];
  if (tsb < -10) return ['build', 'Χτίσιμο'];
  if (tsb <= 5) return ['ok', 'Ισορροπία'];
  if (tsb <= 25) return ['fresh', 'Φρέσκος'];
  return ['idle', 'Χαλάρωση'];
}

// --- Δομή προπόνησης ---------------------------------------------------------------
const fmtSec = (s) => (s < 60 ? `${s} δευτ.` : s % 60 === 0 ? `${s / 60} λ` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')} λ`);

function stepLi(s) {
  if (s.repeat) return `<li class="rep"><b>Επανάληψη ${s.repeat} φορές</b><ol>${s.steps.map(stepLi).join('')}</ol></li>`;
  const line = s.hr ? `${fmtSec(s.sec)} @ ${s.hr[0]}–${s.hr[1]} bpm` : fmtSec(s.sec);
  const sub = s.zone || s.note || '';
  return `<li><b>${esc(s.name)}</b><span>${esc(line)}</span>${sub ? `<small>${esc(sub)}</small>` : ''}</li>`;
}

const flatSteps = (steps) => steps.flatMap((s) => (s.repeat ? Array.from({ length: s.repeat }, () => flatSteps(s.steps)).flat() : [s]));

function stepChart(steps) {
  const bars = flatSteps(steps);
  const total = bars.reduce((a, b) => a + b.sec, 0) || 1;
  const W = 700, H = 80, gap = 1.5;
  let x = 0, out = '';
  for (const b of bars) {
    const w = Math.max(2, (b.sec / total) * W - gap);
    const lv = b.lvl ?? 0.62;
    const h = 10 + ((Math.min(1.2, Math.max(0.5, lv)) - 0.5) / 0.7) * (H - 14);
    const cls = lv >= 1.0 ? 'z5' : lv >= 0.95 ? 'z4' : lv >= 0.88 ? 'z3' : lv >= 0.75 ? 'z2' : 'z1';
    out += `<rect class="${cls}" x="${x.toFixed(1)}" y="${(H - h).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="2"/>`;
    x += (b.sec / total) * W;
  }
  return `<svg class="sgraph" viewBox="0 0 ${W} ${H}" role="img" aria-label="Δομή προπόνησης: ύψος ανάλογο της έντασης, πλάτος της διάρκειας">${out}</svg>`;
}

function structure(day) {
  if (!day.steps || !day.steps.length) return '';
  return `<div class="struct">${stepChart(day.steps)}<ol class="steps">${day.steps.map(stepLi).join('')}</ol></div>`;
}

const doneText = (d) => `Έγινε: ${dur(d.minutes)}, +${mt(d.gain)} m${d.impact ? ` · φορτίο ${mt(d.impact)}` : ''}`;

function flags(d) {
  const f = [];
  if (d.moved) f.push(`μετακινήθηκε από ${esc(d.moved)}`);
  if (d.scaled) f.push(`φορτίο εβδομάδας ${Math.round(d.scaled * 100)}%`);
  if (d.extra) f.push('έξτρα');
  return f.length ? `<p class="flags">${f.map((x) => `<span>${x}</span>`).join('')}</p>` : '';
}

// Κουμπιά ευέλικτου προγράμματος για μια ημέρα.
function dayActions(d, week, today) {
  if (d.date < today || d.done || d.kind === 'race') return '';
  const btns = [];
  if (d.steps) btns.push(`<button class="btn sm" data-act="timer" data-date="${d.date}">▶ Χρονόμετρο</button>`);
  if (d.kind === 'strength' && d.session) btns.push(`<button class="btn sm" data-act="session" data-key="${d.session}">▶ Συνεδρία</button>`);
  const others = week.days.filter((o) => o.date !== d.date && o.date >= today && !o.done && o.kind !== 'race');
  if (others.length && (d.km > 0 || d.kind === 'strength')) {
    btns.push(`<label class="sel sm"><span>Μετακίνηση</span><select data-act="move" data-date="${d.date}" aria-label="Μετακίνηση σε άλλη ημέρα">
      <option value="">σε…</option>${others.map((o) => `<option value="${o.date}">${esc(o.dow)}${o.km > 0 ? ` (${esc(o.title.slice(0, 18))})` : ''}</option>`).join('')}</select></label>`);
  }
  if (d.km > 0 && !d.extra) btns.push(`<button class="btn sm ghost" data-act="skip" data-date="${d.date}">${d.skipped ? 'Επαναφορά' : 'Παράλειψη'}</button>`);
  if (d.extra) btns.push(`<button class="btn sm ghost" data-act="extra" data-date="${d.date}" data-min="0">Αφαίρεση έξτρα</button>`);
  else if (!(d.km > 0) && !['prerace', 'recover'].includes(d.kind)) {
    btns.push(`<button class="btn sm ghost" data-act="extra" data-date="${d.date}" data-min="30">+ Έξτρα 30'</button>`);
    btns.push(`<button class="btn sm ghost" data-act="extra" data-date="${d.date}" data-min="45">+ 45'</button>`);
  }
  return btns.length ? `<div class="acts">${btns.join('')}</div>` : '';
}

// Η εβδομάδα σαν κορφογραμμή: ύψος = θετική υψομετρική, πλάτος = διάρκεια.
function ridge(week, today, animate) {
  const W = 700, base = 104;
  const maxG = Math.max(300, ...week.days.map((d) => d.gain));
  let peaks = '', labels = '';
  week.days.forEach((d, i) => {
    const cx = 50 + i * 100;
    const isToday = d.date === today;
    if (d.km > 0 && !d.skipped) {
      const h = 14 + (d.gain / maxG) * 74;
      const hw = 22 + Math.min(26, d.minutes / 7);
      const missed = d.date < today && !d.done && d.kind !== 'race';
      const cls = ['peak', d.done ? 'done' : '', missed ? 'missed' : '', isToday ? 'today' : ''].join(' ').trim();
      peaks += `<path class="${cls}" style="--i:${i}" d="M${cx - hw},${base} Q${cx - hw * 0.35},${base} ${cx},${base - h} Q${cx + hw * 0.35},${base} ${cx + hw},${base}Z"/>`;
    }
    if (isToday) labels += `<rect class="pill" x="${cx - 32}" y="118" width="64" height="30" rx="15"/>`;
    labels += `<text class="lbl${isToday ? ' is-today' : ''}" x="${cx}" y="140" text-anchor="middle">${esc(d.dow.slice(0, 3))}</text>`;
  });
  const summary = week.days.filter((d) => d.km > 0 && !d.skipped).map((d) => `${d.dow} ${dur(d.minutes)}`).join(', ');
  return `<svg class="ridge${animate ? ' play' : ''}" viewBox="0 0 ${W} 156" role="img" aria-label="Η εβδομάδα: ${esc(summary)}">
    <line class="ground" x1="0" x2="${W}" y1="${base}" y2="${base}"/>${peaks}${labels}</svg>`;
}

function raceChip(today) {
  const race = data.race;
  if (!race) return '';
  const n = dayDiff(race.date, today);
  if (n < 0) return '';
  return `<button class="chip" data-act="goto" data-view="race">${esc(race.name)} · ${n === 0 ? 'σήμερα!' : `σε ${n} ${n === 1 ? 'ημέρα' : 'ημέρες'}`}</button>`;
}

function formTiles(compact = false) {
  const im = data.impact;
  if (!im) return '';
  const { ctl, atl, tsb } = im.now;
  const [cls, label] = formState(tsb);
  const rd = im.readiness;
  return `<div class="tiles${compact ? ' compact' : ''}">
    <div class="tile"><span>Φόρμα</span><b>${nf0.format(ctl)}</b></div>
    <div class="tile"><span>Κούραση</span><b>${nf0.format(atl)}</b></div>
    <div class="tile st-${cls}"><span>Φρεσκάδα</span><b>${tsb > 0 ? '+' : ''}${nf0.format(tsb)}</b><small>${label}</small></div>
    ${rd && compact ? `<button class="tile ready" data-act="goto" data-view="race"><span>Ετοιμότητα αγώνα</span><b>${rd.score}<small>/100</small></b></button>` : ''}
  </div>`;
}

// --- Σήμερα ----------------------------------------------------------------------
function viewToday() {
  const today = localISO();
  const week = currentWeek(today);
  const day = week && week.days.find((d) => d.date === today);
  let html = `<header class="top"><div><p class="kicker">${esc(longDate(today))}</p><h1 class="brand">ΜΟΝΟΠΑΤΙ</h1></div>${raceChip(today)}</header>`;

  if (!week || !day) {
    return html + '<p class="card">Δεν υπάρχει πρόγραμμα για σήμερα. Τα δεδομένα είναι παλιά, οπότε περίμενε την επόμενη ενημέρωση.</p>';
  }

  html += `<section class="hero kind-${esc(day.kind)}${day.skipped ? ' is-skipped' : ''}"><p class="tag">${KIND_TAG[day.kind] || 'ΠΡΟΠΟΝΗΣΗ'}</p><h2>${esc(day.title)}</h2>`;
  if (day.km > 0) {
    html += `<p class="figures"><span><b>${dur(day.minutes)}</b></span><span><b>+${mt(day.gain)}</b> m</span>${day.impact ? `<span><b>${mt(day.impact)}</b> φορτίο</span>` : ''}</p>`;
  } else if (day.minutes > 0) {
    html += `<p class="figures"><span><b>${dur(day.minutes)}</b></span></p>`;
  }
  html += flags(day);
  html += `<p class="desc">${esc(day.desc)}</p>`;
  html += structure(day);
  if (day.adjust) html += `<p class="adjust">${esc(day.adjust)}</p>`;
  if (day.done) html += `<p class="done-note">${esc(doneText(day.done))}</p>`;
  html += dayActions(day, week, today);
  html += '</section>';

  const fuel = day.km > 0 && !day.skipped ? fuelForRun(day.minutes) : null;
  if (fuel) html += `<section class="card fuel"><p class="tag">ΔΙΑΤΡΟΦΗ</p><p>${esc(fuel)}</p></section>`;

  html += formTiles(true);

  html += `<section class="card week-now"><div class="sec-h"><h3>Η εβδομάδα σου</h3><span class="meta">${esc(week.label)}</span></div>
    <p class="meta">${dur(week.minutes || 0)} · +${mt(week.gain)} m · φορτίο ${mt(week.impact || 0)}</p>${ridge(week, today, !played)}</section>`;
  played = true;

  const w = data.wellness || {};
  const vit = [];
  if (w.readiness != null) vit.push(['Ετοιμότητα Garmin', `${nf0.format(w.readiness)}`, '/100']);
  if (w.sleep_score != null) vit.push(['Ύπνος', `${nf0.format(w.sleep_score)}`, '/100']);
  if (w.resting_hr != null) vit.push(['Παλμοί ηρεμίας', `${nf0.format(w.resting_hr)}`, 'bpm']);
  if (w.hrv != null) vit.push(['HRV νύχτας', `${nf0.format(w.hrv)}`, 'ms']);
  if (vit.length) {
    html += `<dl class="vitals">${vit.map(([k, v, u]) => `<div><dt>${k}</dt><dd>${v} <small>${u}</small></dd></div>`).join('')}</dl>`;
  }

  const advice = (data.status && data.status.advice) || [];
  if (advice.length) {
    html += `<section class="card notes"><h3>Προσαρμογές του προγράμματος</h3><ul>${advice.map((a) => `<li>${esc(a)}</li>`).join('')}</ul></section>`;
  }
  return html;
}

// --- Πρόγραμμα -------------------------------------------------------------------
function scaleControl(w, today) {
  const end = w.days[w.days.length - 1].date;
  if (end < today || w.mode === 'taper' || w.mode === 'recovery') return '';
  const opts = [0.8, 0.9, 1, 1.1];
  return `<div class="scale"><span>Φορτίο εβδομάδας</span><div class="seg" role="group" aria-label="Φορτίο εβδομάδας">${opts.map((f) =>
    `<button data-act="scale" data-week="${w.week_start}" data-f="${f}"${(w.scale || 1) === f ? ' aria-pressed="true"' : ''}>${Math.round(f * 100)}%</button>`).join('')}</div></div>`;
}

function viewPlan() {
  const today = localISO();
  const cur = currentWeek(today);
  const weeks = plan.map((w) => {
    const isCur = cur && w.week_start === cur.week_start;
    const days = w.days.map((d) => {
      const st = dayStatus(d, today);
      const nums = d.km > 0 ? `${dur(d.minutes)} · +${mt(d.gain)} m` : d.minutes > 0 ? dur(d.minutes) : '';
      return `<details class="day ${st.cls} k-${esc(d.kind)}" data-k="d${d.date}"><summary>
          <span class="d">${esc(d.dow.slice(0, 3))}<small>${atNoon(d.date).getDate()}</small></span><span class="t">${esc(d.title)}${d.moved || d.extra || d.scaled ? ' <i class="dot" aria-label="αλλαγμένη"></i>' : ''}</span><span class="n">${nums}</span>
          ${st.text ? `<span class="s">${st.text}</span>` : ''}
        </summary><div class="body">${flags(d)}<p>${esc(d.desc)}</p>${structure(d)}
        ${d.done ? `<p class="done-note">${esc(doneText(d.done))}</p>` : ''}${dayActions(d, w, today)}</div></details>`;
    }).join('');
    return `<details class="week${isCur ? ' current' : ''}" data-k="w${w.week_start}"${isCur ? ' open' : ''}>
      <summary><span class="wk">${esc(shortDate(w.week_start))}</span><span class="wl">${esc(w.label)}</span>
      <span class="wt">${dur(w.minutes || 0)}</span><span class="wt">+${mt(w.gain)} m</span><span class="wi">${mt(w.impact || 0)}</span></summary>
      ${scaleControl(w, today)}<div class="days">${days}</div></details>`;
  }).join('');
  const reset = hasEdits(edits) ? '<p class="edits-note">Έχεις κάνει αλλαγές στο πρόγραμμα σε αυτή τη συσκευή. <button class="link" data-act="reset">Επαναφορά όλων</button></p>' : '';
  return `<header class="top page-title"><h1>Πρόγραμμα</h1><p class="sub">Μετακίνησε, παράλειψε ή πρόσθεσε προπονήσεις. Η τελευταία στήλη είναι το φορτίο βουνού.</p></header>${reset}${weeks}`;
}

// --- Αγώνας ----------------------------------------------------------------------
function ring(score) {
  const r = 52, c = 2 * Math.PI * r;
  return `<svg class="ring" viewBox="0 0 130 130" role="img" aria-label="Ετοιμότητα αγώνα ${score} από 100">
    <circle class="rb" cx="65" cy="65" r="${r}"/><circle class="rf" cx="65" cy="65" r="${r}" stroke-dasharray="${(c * score) / 100} ${c}" transform="rotate(-90 65 65)"/>
    <text x="65" y="72" text-anchor="middle" class="rv">${score}</text></svg>`;
}

function viewRace() {
  const today = localISO();
  const race = data.race;
  const rd = data.impact && data.impact.readiness;
  let html = `<header class="top page-title"><h1>Αγώνας</h1>${race ? `<p class="sub">${esc(race.name)} · ${esc(longDate(race.date))} · ${race.km} km, +${mt(race.gain)} m</p>` : ''}</header>`;
  if (race) {
    const n = dayDiff(race.date, today);
    html += `<section class="card countdown"><div><b>${n}</b><span>ημέρες</span></div><div><b>${Math.floor(n / 7)}</b><span>εβδομάδες</span></div>
      ${rd ? `<div><b>${clock(rd.est_minutes)}</b><span>εκτίμηση χρόνου</span></div>` : ''}</section>`;
  }
  if (rd) {
    html += `<section class="card readiness"><div class="rd-head">${ring(rd.score)}<div><h3>Ετοιμότητα αγώνα</h3>
      <p class="muted small">Πού θα είσαι την ημέρα του αγώνα αν ακολουθήσεις το πρόγραμμα. Η φόρμα και η φρεσκάδα είναι πρόβλεψη. Τα υπόλοιπα δείχνουν πού είσαι σήμερα.</p></div></div>
      <ul class="parts">${rd.parts.map((p) => `<li><div class="pl"><span>${esc(p.label)}</span><b>${p.score}</b></div>
        <div class="bar"><i style="width:${p.score}%"></i></div><small>${esc(p.value)}</small></li>`).join('')}</ul></section>`;
    html += projectionCard(rd);
  }
  html += viewRaceAnalysis(loadRace(), (data.profile && data.profile.pace) || 7, race);
  return html;
}

function projectionCard(rd) {
  const pr = data.impact.projection || [];
  if (pr.length < 7) return '';
  const hist = data.impact.series.slice(-28);
  const pts = hist.concat(pr);
  const W = 700, H = 170, top = 16, bot = 26;
  const max = Math.max(rd.target_ctl * 1.15, ...pts.map((p) => p.ctl)) || 1;
  const x = (i) => (i / (pts.length - 1)) * W;
  const y = (v) => top + (H - top - bot) * (1 - v / max);
  const path = (arr, off) => arr.map((p, i) => `${i ? 'L' : 'M'}${x(i + off).toFixed(1)},${y(p.ctl).toFixed(1)}`).join(' ');
  const t = y(rd.target_ctl);
  const lbl = [];
  pts.forEach((p, i) => { if (p.date.endsWith('-01')) lbl.push(`<text class="lbl" x="${x(i)}" y="${H - 6}">${esc(atNoon(p.date).toLocaleDateString('el-GR', { month: 'short' }))}</text>`); });
  return `<section class="card"><h3>Πρόβλεψη φόρμας μέχρι τον αγώνα</h3>
    <svg class="lchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Η φόρμα σου ανεβαίνει από ${nf0.format(data.impact.now.ctl)} σε ${nf0.format(rd.race_ctl)} την ημέρα του αγώνα. Στόχος ${rd.target_ctl}.">
      <line class="target" x1="0" x2="${W}" y1="${t}" y2="${t}"/><text class="lbl t" x="${W - 4}" y="${t - 6}">στόχος ${rd.target_ctl}</text>
      <path class="ctl" d="${path(hist, 0)}"/><path class="ctl proj" d="M${x(hist.length - 1)},${y(hist[hist.length - 1].ctl)} ${path(pr, hist.length).replace(/^M/, 'L')}"/>
      <line class="now" x1="${x(hist.length - 1)}" x2="${x(hist.length - 1)}" y1="${top}" y2="${H - bot}"/>${lbl.join('')}</svg>
    <p class="legend"><i class="lg ctl"></i>Φόρμα μέχρι σήμερα <i class="lg proj"></i>Με το πρόγραμμα</p></section>`;
}

// --- Φόρμα -----------------------------------------------------------------------
function fitnessChart() {
  const s = data.impact.series;
  const W = 700, H = 200, top = 16, bot = 26;
  const max = Math.max(10, ...s.map((p) => Math.max(p.ctl, p.atl))) * 1.1;
  const x = (i) => (i / (s.length - 1)) * W;
  const y = (v) => top + (H - top - bot) * (1 - v / max);
  const line = (k) => s.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[k]).toFixed(1)}`).join(' ');
  const bw = W / s.length;
  const maxL = Math.max(1, ...s.map((p) => p.load));
  const bars = s.map((p, i) => (p.load ? `<rect class="ld" x="${(x(i) - bw * 0.35).toFixed(1)}" y="${(H - bot - (p.load / maxL) * 50).toFixed(1)}" width="${(bw * 0.7).toFixed(1)}" height="${((p.load / maxL) * 50).toFixed(1)}"/>` : '')).join('');
  const lbl = s.map((p, i) => (i % 14 === 0 ? `<text class="lbl" x="${x(i)}" y="${H - 6}">${esc(shortDate(p.date))}</text>` : '')).join('');
  return `<section class="card"><h3>Φόρμα και κούραση (12 εβδομάδες)</h3>
    <svg class="lchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Φόρμα ${nf0.format(data.impact.now.ctl)}, κούραση ${nf0.format(data.impact.now.atl)}">
    ${bars}<path class="atl" d="${line('atl')}"/><path class="ctl" d="${line('ctl')}"/>${lbl}</svg>
    <p class="legend"><i class="lg ctl"></i>Φόρμα (42 ημ.) <i class="lg atl"></i>Κούραση (7 ημ.) <i class="lg ld"></i>Φορτίο ημέρας</p></section>`;
}

function impactWeeks() {
  const hist = data.impact.weeks;
  const curStart = hist[hist.length - 1].week_start;
  const fut = plan.filter((w) => w.week_start > curStart).slice(0, 6);
  const curPlan = plan.find((w) => w.week_start === curStart);
  const items = hist.map((h) => ({ start: h.week_start, a: h.impact, c: h.cardio, p: h.week_start === curStart && curPlan ? curPlan.impact : 0, cur: h.week_start === curStart }))
    .concat(fut.map((w) => ({ start: w.week_start, a: 0, c: 0, p: w.impact, fut: true })));
  const W = 700, H = 200, top = 22, bot = 40, plotH = H - top - bot;
  const max = Math.max(1, ...items.map((it) => Math.max(it.a + it.c, it.p)));
  const slot = W / items.length, bw = slot * 0.6;
  const y = (v) => top + plotH * (1 - v / max);
  let out = '';
  items.forEach((it, i) => {
    const x = i * slot + (slot - bw) / 2, cx = i * slot + slot / 2;
    if (it.p) out += `<rect class="plan" x="${x}" y="${y(it.p)}" width="${bw}" height="${plotH * (it.p / max)}" rx="3"/>`;
    if (it.a) out += `<rect class="act" x="${x}" y="${y(it.a)}" width="${bw}" height="${plotH * (it.a / max)}" rx="3"/>`;
    if (it.c) out += `<rect class="cardio" x="${x}" y="${y(it.a + it.c)}" width="${bw}" height="${plotH * (it.c / max)}" rx="3"/>`;
    const v = it.fut ? it.p : it.a;
    if (v && (i % 2 === 0 || it.cur)) out += `<text class="val" x="${cx}" y="${y(Math.max(it.a + it.c, it.p)) - 5}">${mt(v)}</text>`;
    if (i % 3 === 0) out += `<text class="lbl" x="${cx}" y="${H - 18}">${esc(shortDate(it.start))}</text>`;
    if (it.cur) out += `<rect class="pill" x="${cx - 18}" y="${H - 10}" width="36" height="5" rx="2"/>`;
  });
  return `<section class="card chart"><h3>Φορτίο βουνού ανά εβδομάδα</h3>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Φορτίο βουνού ανά εβδομάδα, πραγματικό και προγραμματισμένο">${out}</svg>
    <p class="legend"><i class="lg act"></i>Τρέξιμο <i class="lg cardio"></i>Άλλη αερόβια <i class="lg plan"></i>Πρόγραμμα</p></section>`;
}

function barChart(items, key, title, fmt = mt) {
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
    if (p > 0 && (it.future || it.current)) bars += `<rect class="plan" x="${x}" y="${y(p)}" width="${bw}" height="${plotH * (p / max)}" rx="3"/>`;
    if (a > 0) bars += `<rect class="act" x="${x}" y="${y(a)}" width="${bw}" height="${plotH * (a / max)}" rx="3"/>`;
    const shown = it.future || it.current ? p || a : a;
    if (shown > 0) texts += `<text class="val" x="${cx}" y="${y(Math.max(a, p)) - 5}">${fmt(shown)}</text>`;
    if (i % 2 === 0 || it.current) texts += `<text class="lbl" x="${cx}" y="${H - 18}">${esc(shortDate(it.start))}</text>`;
    if (it.current) texts += `<rect class="pill" x="${cx - 24}" y="${H - 10}" width="48" height="5" rx="2"/>`;
  });
  const desc = items.map((it) => `${shortDate(it.start)}: ${mt(it.future ? planned(it) : actual(it))}`).join(', ');
  return `<section class="card chart"><h3>${title}</h3>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}. ${esc(desc)}">${bars}${texts}</svg></section>`;
}

function viewForm() {
  const hist = data.history.slice(-6);
  const curStart = hist[hist.length - 1].week_start;
  const byStart = Object.fromEntries(plan.map((w) => [w.week_start, { hours: (w.minutes || 0) / 60, gain: w.gain }]));
  const items = hist.map((h) => ({ start: h.week_start, hours: (h.minutes || 0) / 60, gain: h.gain, plan: byStart[h.week_start], current: h.week_start === curStart }))
    .concat(plan.filter((w) => w.week_start > curStart).slice(0, 6).map((w) => ({ start: w.week_start, plan: byStart[w.week_start], future: true })));

  const p = data.profile || {};
  let html = `<header class="top page-title"><h1>Φόρμα</h1>
    <p class="sub">Μέσος όρος 4 εβδομάδων: ${dur(p.base_minutes || 0)}, +${mt(p.base_gain || 0)} m</p></header>`;
  if (data.impact) {
    html += formTiles();
    html += fitnessChart();
    html += impactWeeks();
  }
  html += barChart(items, 'hours', 'Ώρες τρεξίματος ανά εβδομάδα', (v) => nf1.format(v));
  html += barChart(items, 'gain', 'Θετική υψομετρική ανά εβδομάδα (m)');
  html += '<p class="legend"><i class="lg act"></i>Όσα έτρεξες <i class="lg plan"></i>Πρόγραμμα</p>';

  const recent = (data.recent || []).map((r) => `<li><span class="dt">${esc(shortDate(r.date))}</span>
    <span class="nm">${esc(r.name || 'Τρέξιμο')}</span>
    <span class="nu">${dur(r.minutes)} · +${mt(r.gain)} m${r.avg_hr ? ` · ${r.avg_hr} bpm` : ''}</span>${r.impact ? `<span class="im">${mt(r.impact)}</span>` : ''}</li>`).join('');
  html += `<section class="card recent"><h3>Τελευταία τρεξίματα</h3>${recent ? `<ul>${recent}</ul>` : '<p class="muted">Δεν βρέθηκαν τρεξίματα.</p>'}</section>`;

  html += `<details class="card explain"><summary>Τι είναι το φορτίο βουνού;</summary>
    <p>Ένας αριθμός για το πόσο σε κούρασε κάθε τρέξιμο, όχι μόνο πόσα χιλιόμετρα έκανες. Μετράει δύο πράγματα:</p>
    <ul class="bul"><li><b>Καρδιά:</b> διάρκεια × ένταση από τους παλμούς σε σχέση με το όριο γαλακτικού σου (${data.lthr || 155} bpm). Μία ώρα στο κατώφλι = 100. Οι ανηφόρες ανεβάζουν τους παλμούς, άρα μετρούν εδώ.</li>
    <li><b>Πόδια:</b> 2,5 μονάδες για κάθε 100 m κατηφόρας, επειδή η κατηφόρα κουράζει τους μύες χωρίς να ανεβάζει τους παλμούς.</li></ul>
    <p><b>Φόρμα</b> είναι ο μέσος όρος των 42 ημερών, <b>κούραση</b> των 7 ημερών και <b>φρεσκάδα</b> η διαφορά τους. Ποδήλατο και άλλη αερόβια μετρούν χωριστά.</p></details>`;

  const upd = new Date(data.generated_at).toLocaleString('el-GR', { dateStyle: 'long', timeStyle: 'short' });
  html += `<footer class="foot"><p>Τελευταία ενημέρωση: ${esc(upd)}</p>
    <p>Γενικό πρόγραμμα προπόνησης, όχι ιατρική συμβουλή. Αν νιώσεις πόνο ή ασυνήθιστη κούραση, σταμάτα και ξεκουράσου.</p>
    <button class="link" id="forget">Κλείδωμα εφαρμογής</button></footer>`;
  return html;
}

boot();
