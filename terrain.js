// Προσωπικό μοντέλο κλίσης, αντοχή στην κόπωση και πρόβλεψη αγώνα (τα υπολογίζει το terrain.py).
import { esc, nf1, mt, clock, shortDate } from './util.js';

// Γενικός συντελεστής κόστους ανά κλίση (ίδιος με το terrain.py), για κλίσεις έξω από τα κουτιά.
const COST = [[-40, 1.6], [-35, 1.45], [-30, 1.3], [-25, 1.17], [-20, 1.05], [-15, 0.95], [-9, 0.88], [-5, 0.9],
  [0, 1], [5, 1.2], [10, 1.45], [15, 1.75], [20, 2.05], [25, 2.4], [30, 2.75], [35, 3.1], [40, 3.5]];
function defaultCost(g) {
  if (g <= COST[0][0]) return COST[0][1];
  if (g >= COST[COST.length - 1][0]) return COST[COST.length - 1][1];
  for (let i = 1; i < COST.length; i++) {
    const [a, ca] = COST[i - 1], [b, cb] = COST[i];
    if (g <= b) return ca + ((cb - ca) * (g - a)) / (b - a);
  }
  return 1;
}

// Ταχύτητα (m/s) σε κλίση g (%), όπως η speed() του terrain.py.
export function speedAt(model, g, key = 'p50') {
  const bs = model.bins;
  if (g <= bs[0].g) return Math.max(0.15, (bs[0][key] * defaultCost(bs[0].g)) / defaultCost(g));
  const last = bs[bs.length - 1];
  if (g >= last.g) return Math.max(0.15, (last[key] * defaultCost(last.g)) / defaultCost(g));
  for (let i = 1; i < bs.length; i++) {
    const a = bs[i - 1], b = bs[i];
    if (g <= b.g) return a[key] + ((b[key] - a[key]) * (g - a.g)) / (b.g - a.g);
  }
  return model.v0;
}

const kmh = (v) => v * 3.6;
const paceStr = (v) => { const s = Math.round(1000 / v); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
const sign = (n) => (n > 0 ? `+${n}` : `${n}`);

// --- Πρόβλεψη αγώνα ---------------------------------------------------------------
function marginCls(m) {
  if (m == null) return '';
  if (m < 15) return 'bad';
  if (m < 45) return 'warn';
  return 'ok';
}

function trendSvg(hist) {
  const pts = hist.slice(-84);
  if (pts.length < 2) return '';
  const W = 700, H = 120, top = 14, bot = 24;
  const vals = pts.map((p) => p.minutes);
  const lo = Math.min(...vals) - 10, hi = Math.max(...vals) + 10;
  const x = (i) => (i / (pts.length - 1)) * W;
  const y = (v) => top + (H - top - bot) * (1 - (v - lo) / (hi - lo || 1));
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.minutes).toFixed(1)}`).join(' ');
  const first = pts[0], last = pts[pts.length - 1];
  const diff = last.minutes - first.minutes;
  return `<svg class="lchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Ρεαλιστική πρόβλεψη από ${clock(first.minutes)} σε ${clock(last.minutes)}">
      <path class="ctl" d="${d}"/>
      <text class="lbl" x="${x(0) + 30}" y="${H - 6}">${esc(shortDate(first.date))}</text>
      <text class="lbl" x="${W - 30}" y="${H - 6}">${esc(shortDate(last.date))}</text>
      <text class="lbl t" x="${W - 4}" y="${y(last.minutes) - 8}">${clock(last.minutes)}</text></svg>
    <p class="muted small">${diff === 0 ? 'Χωρίς αλλαγή' : diff < 0 ? `${mt(-diff)} λεπτά πιο γρήγορα` : `${mt(diff)} λεπτά πιο αργά`} από ${esc(shortDate(first.date))}.</p>`;
}

export function viewPrediction(ter, race) {
  const pr = ter && ter.prediction;
  if (!pr) return '';
  const S = pr.scenarios;
  const real = S.real.rows, opt = S.opt.rows, cons = S.cons.rows;
  const fin = (k) => S[k].rows[S[k].rows.length - 1];
  const rows = real.map((r, i) => `<tr${r.cutoff ? ' class="cut"' : ''}>
      <td>${esc(r.name)}<small>${nf1.format(r.km)} km · ${mt(r.alt)} m</small></td>
      <td><b>${r.clock}</b><small>${clock(r.at)}</small></td>
      <td><small>${clock(opt[i].at)}–${clock(cons[i].at)}</small></td>
      <td>${r.cutoff ? `${r.cutoff}<small class="${marginCls(cons[i].margin)}">${cons[i].margin >= 0 ? `+${clock(cons[i].margin)}` : `−${clock(-cons[i].margin)}`}</small>` : ''}</td></tr>`).join('');
  const m = ter.model, cal = ter.calibration;
  const chk = cal && cal.checks && cal.checks.length ? cal.checks[cal.checks.length - 1] : null;
  const worst = Math.min(...cons.filter((r) => r.cutoff).map((r) => r.margin));
  return `<section class="card predict"><h3>Πρόβλεψη χρόνου${race ? `: ${esc(race.name)}` : ''}</h3>
    <div class="scen">
      <div><span>Αισιόδοξο</span><b>${clock(S.opt.minutes)}</b><small>τερμ. ${fin('opt').clock}</small></div>
      <div class="main"><span>Ρεαλιστικό</span><b>${clock(S.real.minutes)}</b><small>τερμ. ${fin('real').clock}</small></div>
      <div><span>Συντηρητικό</span><b>${clock(S.cons.minutes)}</b><small>τερμ. ${fin('cons').clock}</small></div></div>
    ${worst < 15 ? '<p class="banner">Στο συντηρητικό σενάριο περνάς οριακά (ή όχι) ένα όριο αποκλεισμού. Δες τον πίνακα.</p>' : ''}
    <div class="scroll"><table class="pred"><thead><tr><th>Σταθμός</th><th>Άφιξη</th><th>Εύρος</th><th>Όριο</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="muted small">Εκκίνηση ${esc(pr.start)}. Το «Όριο» είναι ο χρόνος από την εκκίνηση μέχρι να φύγεις από τον σταθμό, και δίπλα το περιθώριό σου στο συντηρητικό σενάριο.</p>
    ${pr.history && pr.history.length > 1 ? `<h4>Πώς αλλάζει η ρεαλιστική πρόβλεψη</h4>${trendSvg(pr.history)}` : ''}
    <details class="why"><summary>Πώς βγαίνει</summary><div class="why-txt">
      <p>Από τις <b>δικές σου</b> ταχύτητες σε κάθε κλίση, σε ${m.runs} τρεξίματα αντοχής των τελευταίων 6 μηνών, όχι από μέσους όρους.
      Ρεαλιστικό = η συνηθισμένη σου ταχύτητα (διάμεσος), αισιόδοξο = οι καλύτερες μέρες σου (65ο εκατοστημόριο), συντηρητικό = οι πιο αργές (35ο).</p>
      <p>Κόπωση: η ταχύτητά σου πέφτει περίπου <b>${nf1.format(m.fatigue.per_hour * 100)}% την ώρα</b> μετά τις 2 πρώτες ώρες
      ${m.fatigue.src === 'personal' ? `(από ${m.fatigue.runs} δικά σου τρεξίματα πάνω από 2,5 ώρες)` : '(γενική τιμή, μέχρι να υπάρξουν δικά σου τρεξίματα πάνω από 2,5 ώρες)'}.
      Στάσεις στους σταθμούς: 1, 2 και 4 λεπτά ανά σενάριο.</p>
      ${chk ? `<p>Έλεγχος: για το «${esc(chk.name)}» (${esc(shortDate(chk.date))}, ${nf1.format(chk.km)} km) το μοντέλο έδινε <b>${clock(chk.pred)}</b> και έτρεξες <b>${clock(chk.actual)}</b> (χρόνος κίνησης). Η ρεαλιστική πρόβλεψη διορθώνεται με αυτή τη διαφορά.</p>` : ''}
      <p>Σταθμοί και όρια: ${esc(pr.source || 'από τη διοργάνωση')}. Αν αλλάξει η διαδρομή για τον αγώνα σου, ενημέρωσε το config.json.</p>
    </div></details></section>`;
}

// --- Κλίση ------------------------------------------------------------------------
export function viewGrade(ter) {
  const m = ter && ter.model;
  if (!m) return '';
  const bs = m.bins;
  const W = 700, H = 210, top = 26, bot = 40, plotH = H - top - bot;
  const max = Math.max(...bs.map((b) => kmh(b.p65))) * 1.05;
  const slot = W / bs.length, bw = slot * 0.62;
  const y = (v) => top + plotH * (1 - v / max);
  let out = '';
  bs.forEach((b, i) => {
    const x = i * slot + (slot - bw) / 2, cx = i * slot + slot / 2;
    const v = kmh(b.p50);
    out += `<rect class="rng" x="${cx - 2}" y="${y(kmh(b.p65))}" width="4" height="${y(kmh(b.p35)) - y(kmh(b.p65))}" rx="2"/>`;
    out += `<rect class="${b.src === 'personal' ? 'act' : 'plan'}" x="${x}" y="${y(v)}" width="${bw}" height="${plotH * (v / max)}" rx="3"/>`;
    out += `<text class="val" x="${cx}" y="${y(kmh(b.p65)) - 5}">${nf1.format(v)}</text>`;
    out += `<text class="lbl" x="${cx}" y="${H - 18}">${sign(b.g)}%</text>`;
  });
  const up = bs.filter((b) => b.g === 18 || b.g === 25 || b.g === 35);
  const vam = up.map((b) => `<div><b>${mt(b.p50 * (b.g / 100) * 3600)}</b><span>m/ώρα στο ${b.g}%</span></div>`).join('');
  const dn = bs.find((b) => b.g === -18) || bs[2];
  return `<section class="card chart"><h3>Η ταχύτητά σου ανά κλίση</h3>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Ταχύτητα σε km/h ανά κλίση, από τα τρεξίματα αντοχής σου">${out}</svg>
    <p class="legend"><i class="lg act"></i>Από τα τρεξίματά σου <i class="lg plan"></i>Λίγα δεδομένα: γενική καμπύλη από τη δική σου κοντινότερη κλίση <i class="lg rng"></i>Εύρος (35ο–65ο)</p>
    <div class="stats4">${vam}<div><b>${paceStr(dn.p50)}</b><span>λ/km κατηφόρα ${dn.g}%</span></div></div>
    <p class="muted small">km/h στα τρεξίματα αντοχής (πάνω από ${70} λεπτά, χωρίς διαλειμματικές). Η κατακόρυφη ταχύτητα (m/ώρα) δείχνει πόσο γρήγορα ανεβαίνεις στις απότομες ανηφόρες του αγώνα.
    Τα στοιχεία αυτά χρησιμοποιούνται στην πρόβλεψη του αγώνα και στην ανάλυση GPX.</p></section>`;
}

// --- Αντοχή στην κόπωση -------------------------------------------------------------
function decCls(d) {
  if (d < 5) return 'ok';
  if (d < 10) return 'warn';
  return 'bad';
}

export function viewDurability(ter) {
  const d = ter && ter.durability;
  if (!d || !d.runs.length) {
    return ter ? `<section class="card"><h3>Αντοχή στην κόπωση</h3><p class="muted">Θα εμφανιστεί μετά το πρώτο τρέξιμο πάνω από 90 λεπτά.</p></section>` : '';
  }
  const runs = d.runs;
  const W = 700, H = 200, top = 26, bot = 40, plotH = H - top - bot;
  const max = Math.max(15, ...runs.map((r) => r.decoupling)) * 1.1;
  const min = Math.min(0, ...runs.map((r) => r.decoupling));
  const span = max - min;
  const y = (v) => top + plotH * (1 - (v - min) / span);
  const slot = W / runs.length, bw = Math.min(46, slot * 0.6);
  let out = `<line class="target" x1="0" x2="${W}" y1="${y(5)}" y2="${y(5)}"/><text class="lbl t" x="${W - 4}" y="${y(5) - 6}">5%</text>`;
  if (min < 0) out += `<line class="now" x1="0" x2="${W}" y1="${y(0)}" y2="${y(0)}"/>`;
  runs.forEach((r, i) => {
    const cx = i * slot + slot / 2, v = r.decoupling;
    const yt = y(Math.max(v, 0)), yb = y(Math.min(v, 0));
    out += `<rect class="dc ${decCls(v)}" x="${cx - bw / 2}" y="${yt}" width="${bw}" height="${Math.max(2, yb - yt)}" rx="3"/>`;
    out += `<text class="val" x="${cx}" y="${y(Math.max(v, 0)) - 5}">${nf1.format(v)}</text>`;
    if (i % Math.ceil(runs.length / 8) === 0 || i === runs.length - 1) out += `<text class="lbl" x="${cx}" y="${H - 18}">${esc(shortDate(r.date))}</text>`;
  });
  const last = runs[runs.length - 1];
  const verdict = d.recent == null ? '' : d.recent < 5 ? 'Οι παλμοί σου μένουν σταθεροί μέχρι το τέλος: καλή αερόβια αντοχή.'
    : d.recent < 10 ? 'Στο δεύτερο μισό ξοδεύεις αισθητά περισσότερους παλμούς για την ίδια προσπάθεια. Βοηθούν σταθερά μακριά τρεξίματα και σωστή διατροφή κατά τη διάρκεια.'
      : 'Μεγάλη πτώση στο δεύτερο μισό. Τρέξε τα μακριά πιο συγκρατημένα στην αρχή, φάε από νωρίς και πρόσεξε τη ζέστη.';
  return `<section class="card chart"><h3>Αντοχή στην κόπωση (durability)</h3>
    <p class="kpi-line">Τελευταία 4 μακριά: <b class="${decCls(d.recent)}">${nf1.format(d.recent)}%</b> αποσύνδεση ρυθμού–παλμών</p>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Αποσύνδεση ρυθμού και παλμών ανά μακρύ τρέξιμο. Τελευταίο ${nf1.format(last.decoupling)}%">${out}</svg>
    <p class="muted small">${verdict}</p>
    <details class="why"><summary>Τι μετράει</summary><div class="why-txt">
      <p>Σε κάθε τρέξιμο πάνω από 90 λεπτά συγκρίνει την ταχύτητα ανά παλμό στο πρώτο και στο δεύτερο μισό. Η ταχύτητα διορθώνεται με τη <b>δική σου</b> καμπύλη κλίσης, ώστε μια ανηφόρα στο τέλος να μη μετράει ως κούραση. Οι πολύ απότομες κατηφόρες και τα πρώτα 10 λεπτά δεν μετράνε.</p>
      <p>Κάτω από 5% θεωρείται συνήθως καλή αερόβια αντοχή. Η ζέστη, η αφυδάτωση και το λίγο φαγητό την ανεβάζουν. Τελευταίο μακρύ: ${esc(shortDate(last.date))}, ${clock(last.minutes)}, παλμοί ${last.hr1} → ${last.hr2}.</p>
      <p>Η αντοχή στην κόπωση θεωρείται σήμερα ο «τέταρτος πυλώνας» της απόδοσης στην αντοχή, μαζί με το VO2max, το κατώφλι και την οικονομία τρεξίματος.</p>
    </div></details></section>`;
}
