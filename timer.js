// Χρονόμετρο συνεδρίας: τρέχει μια σειρά από διαστήματα με αντίστροφη μέτρηση, ήχο και δόνηση.
// Διάστημα: { name, sec, sub, rest }  ή  { name, reps, sub } (με κουμπί «Τέλος σετ»).
import { esc } from './util.js';

let ctx = null;
function beep(freq = 880, ms = 140) {
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.25, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + ms / 1000);
    o.connect(g).connect(ctx.destination);
    o.start();
    o.stop(ctx.currentTime + ms / 1000);
  } catch { /* χωρίς ήχο */ }
}
const buzz = (p) => { try { navigator.vibrate && navigator.vibrate(p); } catch { /* */ } };
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.max(0, s) % 60).padStart(2, '0')}`;

export function runSession(title, items) {
  if (!items.length) return;
  let i = 0, left = items[0].sec || 0, paused = false, tick = null, lock = null;
  const total = items.reduce((a, b) => a + (b.sec || 0), 0);
  const el = document.createElement('div');
  el.className = 'runner';
  el.setAttribute('role', 'dialog');
  el.setAttribute('aria-label', title);
  document.body.appendChild(el);
  document.body.classList.add('no-scroll');
  try { navigator.wakeLock?.request('screen').then((l) => { lock = l; }).catch(() => {}); } catch { /* */ }

  const close = () => {
    clearInterval(tick);
    try { lock && lock.release(); } catch { /* */ }
    el.remove();
    document.body.classList.remove('no-scroll');
  };

  const go = (n) => {
    i = n;
    if (i >= items.length) {
      beep(660, 200); setTimeout(() => beep(990, 300), 220); buzz([200, 100, 200]);
      el.innerHTML = `<div class="r-in"><p class="r-kicker">${esc(title)}</p><h2 class="r-name">Τέλος!</h2>
        <p class="r-sub">Μπράβο. Η συνεδρία ολοκληρώθηκε.</p><div class="r-btns"><button class="btn" data-a="close">Κλείσιμο</button></div></div>`;
      clearInterval(tick);
      return;
    }
    left = items[i].sec || 0;
    beep(items[i].rest ? 520 : 880, 180); buzz(150);
    draw();
  };

  const draw = () => {
    if (i >= items.length) return;
    const it = items[i];
    const nx = items[i + 1];
    const doneSec = items.slice(0, i).reduce((a, b) => a + (b.sec || 0), 0) + ((it.sec || 0) - left);
    const pct = total ? Math.min(100, (doneSec / total) * 100) : (i / items.length) * 100;
    el.innerHTML = `<div class="r-in${it.rest ? ' is-rest' : ''}">
      <div class="r-top"><p class="r-kicker">${esc(title)} · ${i + 1}/${items.length}</p><button class="r-x" data-a="close" aria-label="Κλείσιμο">✕</button></div>
      <div class="r-bar"><span style="width:${pct.toFixed(1)}%"></span></div>
      <p class="r-tag">${it.rest ? 'ΑΝΑΠΑΥΣΗ' : 'ΤΩΡΑ'}</p>
      <h2 class="r-name">${esc(it.name)}</h2>
      ${it.sub ? `<p class="r-sub">${esc(it.sub)}</p>` : ''}
      <p class="r-clock" aria-live="off">${it.sec ? mmss(left) : `${esc(it.reps)}`}</p>
      ${it.sec ? '' : '<p class="r-sub">επαναλήψεις</p>'}
      <p class="r-next">${nx ? `Μετά: <b>${esc(nx.name)}</b>${nx.sec ? ` · ${mmss(nx.sec)}` : ''}` : 'Τελευταίο'}</p>
      <div class="r-btns">
        <button class="btn ghost" data-a="prev" ${i === 0 ? 'disabled' : ''}>‹ Πίσω</button>
        ${it.sec ? `<button class="btn" data-a="pause">${paused ? '▶ Συνέχεια' : 'Ⅱ Παύση'}</button>` : '<button class="btn" data-a="next">Τέλος σετ ✓</button>'}
        <button class="btn ghost" data-a="next">Επόμενο ›</button>
      </div></div>`;
  };

  el.addEventListener('click', (e) => {
    const a = e.target.closest('[data-a]')?.dataset.a;
    if (!a) return;
    beep(1, 1); // ξεκλειδώνει τον ήχο σε iOS
    if (a === 'close') close();
    if (a === 'pause') { paused = !paused; draw(); }
    if (a === 'next') go(i + 1);
    if (a === 'prev') go(Math.max(0, i - 1));
  });

  tick = setInterval(() => {
    if (paused || i >= items.length || !items[i].sec) return;
    left -= 1;
    if (left <= 3 && left > 0) beep(660, 90);
    if (left <= 0) go(i + 1); else {
      const c = el.querySelector('.r-clock'); if (c) c.textContent = mmss(left);
      const doneSec = items.slice(0, i).reduce((a, b) => a + (b.sec || 0), 0) + (items[i].sec - left);
      const bar = el.querySelector('.r-bar span'); if (bar && total) bar.style.width = `${Math.min(100, (doneSec / total) * 100).toFixed(1)}%`;
    }
  }, 1000);
  go(0);
}

// Δομημένη προπόνηση τρεξίματος → διαστήματα.
export function stepsToItems(steps) {
  const out = [];
  const walk = (ss, tag = '') => {
    for (const s of ss) {
      if (s.repeat) { for (let k = 1; k <= s.repeat; k++) walk(s.steps, ` (${k}/${s.repeat})`); continue; }
      const sub = [s.hr ? `${s.hr[0]}–${s.hr[1]} bpm` : '', s.zone || s.note || ''].filter(Boolean).join(' · ');
      out.push({ name: s.name + tag, sec: s.sec, sub, rest: (s.lvl || 0) < 0.7 && /Εύκολο|Χαλαρά|Αποψύχρανση/.test(s.name) && !!tag });
    }
  };
  walk(steps);
  return out;
}
