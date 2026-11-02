// Ευέλικτο πρόγραμμα: αλλαγές που κάνεις στο κινητό (μετακίνηση, παράλειψη, έξτρα, φορτίο εβδομάδας).
// Αποθηκεύονται μόνο σε αυτή τη συσκευή και εφαρμόζονται πάνω στο πρόγραμμα κάθε φορά που ανοίγει.
import { store, localISO, addDays, hrLoad } from './util.js';

const KEY = 'monopati.edits';
const empty = () => ({ moves: {}, skips: {}, extras: {}, scale: {} });

export function loadEdits() {
  const e = Object.assign(empty(), store.json(KEY, {}));
  // Καθαρισμός: ό,τι αφορά ημέρες πριν από 3 εβδομάδες δεν χρειάζεται πια.
  const old = addDays(localISO(), -21);
  for (const k of ['moves', 'skips', 'extras', 'scale']) {
    for (const d of Object.keys(e[k])) if (d < old) delete e[k][d];
  }
  return e;
}
const save = (e) => store.put(KEY, e);

export function hasEdits(e) {
  return ['moves', 'skips', 'extras', 'scale'].some((k) => Object.keys(e[k]).length);
}

export function swapDays(e, a, b) {
  const A = e.moves[a] || a;
  const B = e.moves[b] || b;
  if (B === a) delete e.moves[a]; else e.moves[a] = B;
  if (A === b) delete e.moves[b]; else e.moves[b] = A;
  save(e);
}
export function toggleSkip(e, d) { if (e.skips[d]) delete e.skips[d]; else e.skips[d] = true; save(e); }
export function setExtra(e, d, minutes) { if (minutes) e.extras[d] = { minutes }; else delete e.extras[d]; save(e); }
export function setScale(e, weekStart, f) { if (f === 1) delete e.scale[weekStart]; else e.scale[weekStart] = f; save(e); }
export function resetEdits(e) { Object.assign(e, empty()); save(e); }

const CONTENT = ['kind', 'title', 'desc', 'km', 'gain', 'minutes', 'steps', 'impact', 'session', 'adjust'];
const KEEP_FULL = /^(Ζέσταμα|Αποψύχρανση)$/;

function scaleSteps(steps, f) {
  return steps.map((s) => (s.repeat ? s : KEEP_FULL.test(s.name) ? s : { ...s, sec: Math.max(60, Math.round((s.sec * f) / 30) * 30) }));
}

function extraDay(minutes, lthr) {
  const hr = (lo, hi) => [Math.round(lo * lthr), Math.round(hi * lthr)];
  return {
    kind: 'easy', title: `Έξτρα: εύκολο τρέξιμο ${minutes}'`, km: 1, gain: 0, minutes,
    desc: 'Πρόσθετη εύκολη προπόνηση που πρόσθεσες εσύ. Άνετος ρυθμός, να μπορείς να μιλάς.',
    impact: Math.round(hrLoad(minutes, 0.76)),
    steps: [
      { name: 'Ζέσταμα', sec: 300, hr: hr(0.65, 0.77), zone: 'Zone 1: Recovery', lvl: 0.71 },
      { name: 'Εύκολο τρέξιμο', sec: (minutes - 10) * 60, hr: hr(0.75, 0.86), zone: 'Zone 1: Recovery-Zone 2: Aerobic', lvl: 0.8 },
      { name: 'Αποψύχρανση', sec: 300, hr: hr(0.54, 0.65), zone: 'Zone 1: Recovery', lvl: 0.6 },
    ],
  };
}

export function applyEdits(plan, e, lthr = 155) {
  const today = localISO();
  const orig = {};
  for (const w of plan) for (const d of w.days) orig[d.date] = d;
  return plan.map((w) => {
    const f = e.scale[w.week_start] || 1;
    const days = w.days.map((d) => {
      const out = { ...d };
      const src = e.moves[d.date];
      if (src && orig[src]) {
        for (const k of CONTENT) { if (k in orig[src]) out[k] = orig[src][k]; else delete out[k]; }
        out.moved = orig[src].dow;
      }
      if (e.extras[d.date] && !(out.km > 0)) {
        Object.assign(out, extraDay(e.extras[d.date].minutes, lthr));
        out.extra = true;
      }
      if (f !== 1 && out.km > 0 && !out.done && out.date >= today && out.kind !== 'race' && !out.extra) {
        out.minutes = Math.round((out.minutes * f) / 5) * 5;
        out.gain = Math.round((out.gain * f) / 10) * 10;
        out.impact = Math.round(out.impact * f);
        if (out.steps) out.steps = scaleSteps(out.steps, f);
        out.scaled = f;
      }
      if (e.skips[d.date]) out.skipped = true;
      return out;
    });
    const active = days.filter((d) => d.km > 0 && !d.skipped);
    return {
      ...w, days, scale: f,
      minutes: active.reduce((a, d) => a + d.minutes, 0),
      gain: active.reduce((a, d) => a + d.gain, 0),
      impact: active.reduce((a, d) => a + (d.impact || 0), 0),
    };
  });
}
