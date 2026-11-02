// Βιβλιοθήκη: συνεδρίες ενδυνάμωσης/prehab/κινητικότητας και οδηγός διατροφής.
import { esc, store, nf0 } from './util.js';
import { runSession } from './timer.js';

// Άσκηση: { name, sets, reps | sec, side (ανά πόδι/πλευρά), cue }
export const SESSIONS = {
  eccentric: {
    title: 'Ενδυνάμωση για κατηφόρες', minutes: 35, rest: 60, tag: 'ΔΥΝΑΜΗ',
    intro: 'Αργή κάθοδος (εκκεντρική σύσπαση): δυναμώνει τους τετρακέφαλους που φρενάρουν στις κατηφόρες. 48 ώρες πριν από ποιοτική προπόνηση.',
    ex: [
      { name: 'Κάθισμα σε ένα πόδι σε παγκάκι', sets: 3, reps: 8, side: true, cue: '3 δευτερόλεπτα κάθοδος, γόνατο στη γραμμή του δεύτερου δαχτύλου.' },
      { name: 'Αργό κατέβασμα από σκαλοπάτι', sets: 3, reps: 10, side: true, cue: 'Η φτέρνα του άλλου ποδιού ακουμπά απαλά κάτω. Λεκάνη ίσια.' },
      { name: 'Bulgarian split squat', sets: 3, reps: 8, side: true, cue: 'Πίσω πόδι σε καρέκλα, κορμός ελαφρά μπροστά, έλεγχος στο κάτω μέρος.' },
      { name: 'Ανύψωση φτέρνας σε σκαλί', sets: 3, reps: 12, side: true, cue: 'Πάνω γρήγορα, κάτω σε 3 δευτερόλεπτα, πλήρες εύρος.' },
      { name: 'Γέφυρα γλουτών σε ένα πόδι', sets: 3, reps: 10, side: true, cue: 'Σφίξε τον γλουτό στην κορυφή για 1 δευτερόλεπτο.' },
      { name: 'Σανίδα', sets: 3, sec: 40, cue: 'Ίσια γραμμή από ώμους ως αστράγαλους, κοιλιά σφιχτή.' },
    ],
  },
  gym: {
    title: 'Γυμναστήριο: βαριά δύναμη', minutes: 50, rest: 120, tag: 'ΓΥΜΝΑΣΤΗΡΙΟ',
    intro: 'Βαριά φορτία, λίγες επαναλήψεις (~85% του μέγιστου, 1–2 επαναλήψεις «στην άκρη»). Βελτιώνει την οικονομία του τρεξίματος χωρίς να προσθέτει βάρος (Rønnestad & Mujika, 2014). Ζέσταμα 10 λεπτά σε ποδήλατο ή διάδρομο πριν ξεκινήσεις.',
    ex: [
      { name: 'Back squat ή goblet squat', sets: 4, reps: 5, cue: 'Βαρύ αλλά με τέλεια τεχνική. Κατέβα ελεγχόμενα, ανέβα γρήγορα.' },
      { name: 'Romanian deadlift', sets: 3, reps: 6, cue: 'Πλάτη ίσια, σπρώξε τη λεκάνη πίσω. Δουλεύει οπίσθιους μηριαίους και γλουτούς.' },
      { name: 'Bulgarian split squat με αλτήρες', sets: 3, reps: 6, side: true, cue: 'Ισχυρό μπροστινό πόδι, 3 δευτερόλεπτα κάθοδος.' },
      { name: 'Step-up σε ψηλό κουτί με βάρος', sets: 3, reps: 8, side: true, cue: 'Σπρώξε από τη φτέρνα. Μιμείται τις απότομες ανηφόρες.' },
      { name: 'Ανύψωση φτέρνας σε μηχάνημα/με βάρος', sets: 3, reps: 10, side: true, cue: 'Πλήρες εύρος, 3 δευτερόλεπτα κάθοδος.' },
      { name: 'Εκκεντρικό κατέβασμα από κουτί', sets: 2, reps: 8, side: true, cue: 'Πολύ αργά (4 δευτ.). Για τις κατηφόρες του Ολύμπου.' },
      { name: 'Pallof press ή σανίδα με βάρος', sets: 3, sec: 30, cue: 'Κορμός σταθερός χωρίς περιστροφή.' },
    ],
  },
  gym_light: {
    title: 'Γυμναστήριο: διατήρηση δύναμης', minutes: 40, rest: 120, tag: 'ΓΥΜΝΑΣΤΗΡΙΟ',
    intro: 'Λιγότερα σετ, ίδιο βάρος. Μία συνεδρία την εβδομάδα κρατά τα οφέλη της δύναμης στην ειδική φάση και στις εβδομάδες αποφόρτισης (Rønnestad & Mujika, 2014). Τελείωσε φρέσκος.',
    ex: [
      { name: 'Back squat ή goblet squat', sets: 2, reps: 4, cue: 'Βαρύ, γρήγορη άνοδος, όχι ως την εξάντληση.' },
      { name: 'Romanian deadlift', sets: 2, reps: 5, cue: 'Πλάτη ίσια.' },
      { name: 'Step-up σε ψηλό κουτί με βάρος', sets: 2, reps: 6, side: true, cue: 'Σπρώξε από τη φτέρνα.' },
      { name: 'Ανύψωση φτέρνας με βάρος', sets: 2, reps: 10, side: true, cue: 'Αργή κάθοδος.' },
      { name: 'Εκκεντρικό κατέβασμα από κουτί', sets: 2, reps: 6, side: true, cue: '4 δευτερόλεπτα κάθοδος.' },
    ],
  },
  prehab: {
    title: 'Prehab: αστράγαλοι, γόνατα, ισχία', minutes: 20, rest: 30, tag: 'PREHAB',
    intro: 'Πρόληψη τραυματισμών για ανώμαλο έδαφος: σταθερότητα αστραγάλου, έλεγχος γονάτου, απαγωγοί ισχίου. Κάν’ το 1–2 φορές την εβδομάδα, ακόμα και μετά από εύκολο τρέξιμο.',
    ex: [
      { name: 'Ισορροπία σε ένα πόδι, μάτια κλειστά', sets: 2, sec: 30, side: true, cue: 'Ελαφρά λυγισμένο γόνατο. Για δυσκολία, σε μαξιλάρι.' },
      { name: 'Ανύψωση δαχτύλων (κνημιαίος)', sets: 2, reps: 15, cue: 'Πλάτη στον τοίχο, φτέρνες 30 εκ. μπροστά, σήκωσε τα δάχτυλα.' },
      { name: 'Ανύψωση φτέρνας με λυγισμένο γόνατο', sets: 2, reps: 15, side: true, cue: 'Δουλεύει τον υποκνημίδιο, που αντέχει τις μεγάλες ανηφόρες.' },
      { name: 'Πλάγια σανίδα', sets: 2, sec: 30, side: true, cue: 'Λεκάνη ψηλά, σώμα σε ευθεία.' },
      { name: 'Clamshell με λάστιχο', sets: 2, reps: 15, side: true, cue: 'Πόδια ενωμένα, άνοιξε το γόνατο χωρίς να γυρίσει η λεκάνη.' },
      { name: 'Copenhagen σανίδα (εύκολη)', sets: 2, sec: 20, side: true, cue: 'Γόνατο πάνω σε παγκάκι. Δυναμώνει τους προσαγωγούς.' },
    ],
  },
  core: {
    title: 'Core και δύναμη για ανηφόρες', minutes: 25, rest: 45, tag: 'ΔΥΝΑΜΗ',
    intro: 'Δύναμη για power hiking και σταθερός κορμός όταν κουράζεσαι στο τέλος του αγώνα.',
    ex: [
      { name: 'Step-up με ανύψωση γονάτου', sets: 3, reps: 10, side: true, cue: 'Ψηλό σκαλί ή παγκάκι, σπρώξε από τη φτέρνα.' },
      { name: 'Καθιστό στον τοίχο', sets: 3, sec: 45, cue: 'Γόνατα στις 90°, πλάτη κολλητά στον τοίχο.' },
      { name: 'Dead bug', sets: 3, reps: 10, side: true, cue: 'Μέση κολλητά στο πάτωμα, αργά.' },
      { name: 'Γέφυρα με βηματισμό', sets: 3, reps: 10, side: true, cue: 'Λεκάνη σταθερή, χωρίς να γέρνει.' },
      { name: 'Hip airplane', sets: 2, reps: 5, side: true, cue: 'Σε ένα πόδι, γύρνα τη λεκάνη ανοιχτά και κλειστά, με στήριγμα αν χρειάζεται.' },
      { name: 'Σανίδα με άγγιγμα ώμου', sets: 3, sec: 40, cue: 'Λεκάνη ακίνητη ενώ αλλάζεις χέρι.' },
    ],
  },
  mobility: {
    title: 'Κινητικότητα 15 λεπτών', minutes: 15, rest: 10, tag: 'ΚΙΝΗΤΙΚΟΤΗΤΑ',
    intro: 'Για ημέρες ξεκούρασης, μετά από μακρύ ή την εβδομάδα του αγώνα. Ήπιες διατάσεις, χωρίς πόνο.',
    ex: [
      { name: 'Διάταση καμπτήρων ισχίου (γονάτισμα)', sets: 1, sec: 45, side: true, cue: 'Σφίξε τον γλουτό του πίσω ποδιού.' },
      { name: 'Περιστέρι', sets: 1, sec: 45, side: true, cue: 'Αν πονά το γόνατο, κάν’ το ξαπλωτός (figure-4).' },
      { name: 'Γάτα–καμήλα', sets: 1, sec: 45, cue: 'Αργά, με την αναπνοή.' },
      { name: 'Στροφή θωρακικής σε τετραποδική', sets: 1, sec: 30, side: true, cue: 'Χέρι πίσω από το κεφάλι, ο αγκώνας ανοίγει προς τα πάνω.' },
      { name: 'Διάταση γάμπας στον τοίχο', sets: 1, sec: 30, side: true, cue: 'Ίσιο και μετά λυγισμένο γόνατο.' },
      { name: 'Διάταση οπίσθιων μηριαίων', sets: 1, sec: 45, side: true, cue: 'Πλάτη ίσια, σκύψε από τη λεκάνη.' },
    ],
  },
};

export function sessionItems(s) {
  const items = [];
  s.ex.forEach((x, n) => {
    const sides = x.side ? ['αριστερό', 'δεξί'] : [''];
    for (let k = 1; k <= x.sets; k++) {
      for (const side of sides) {
        const name = side ? `${x.name}: ${side}` : x.name;
        const sub = `Σετ ${k}/${x.sets} · ${x.cue}`;
        items.push(x.sec ? { name, sec: x.sec, sub } : { name, reps: x.reps, sub });
      }
      const last = k === x.sets;
      if (!last) items.push({ name: 'Ανάπαυση', sec: s.rest, rest: true, sub: `Επόμενο: σετ ${k + 1} · ${x.name}` });
      else if (n < s.ex.length - 1) items.push({ name: 'Αλλαγή άσκησης', sec: Math.max(20, Math.min(45, s.rest)), rest: true, sub: `Επόμενη: ${s.ex[n + 1].name}` });
    }
  });
  return items;
}

export const startSession = (key) => runSession(SESSIONS[key].title, sessionItems(SESSIONS[key]));

function sessionCard(key) {
  const s = SESSIONS[key];
  const rows = s.ex.map((x) => `<li><b>${esc(x.name)}</b><span>${x.sets}×${x.sec ? `${x.sec}″` : x.reps}${x.side ? ' ανά πλευρά' : ''}</span><small>${esc(x.cue)}</small></li>`).join('');
  return `<details class="card lib" id="s-${key}"><summary><span class="tag">${s.tag}</span><span class="lt">${esc(s.title)}</span><span class="lm">${s.minutes} λ</span></summary>
    <p class="muted">${esc(s.intro)}</p><ol class="exlist">${rows}</ol>
    <button class="btn" data-session="${key}">▶ Ξεκίνα με χρονόμετρο</button></details>`;
}

// --- Διατροφή --------------------------------------------------------------------
const WKEY = 'monopati.weight';
const g = (lo, hi, kg) => (kg ? `${nf0.format(lo * kg)}–${nf0.format(hi * kg)} g` : `${lo}–${hi} g/kg`);

export function fuelForRun(minutes) {
  if (minutes < 75) return null;
  const carbs = minutes < 150 ? '30–60' : '60–90';
  return `Για ${Math.round(minutes)} λεπτά: ${carbs} g υδατάνθρακες την ώρα από τα πρώτα 30–45 λεπτά, 400–800 ml υγρά την ώρα ανάλογα με τη ζέστη, και αλάτι (300–600 mg νάτριο/ώρα) αν ιδρώνεις πολύ. Δοκίμασε ό,τι θα φας στον αγώνα.`;
}

function nutrition() {
  const kg = Number(store.get(WKEY)) || 0;
  const cards = [
    ['ΚΑΘΗΜΕΡΙΝΑ', 'Ανάλογα με την προπόνηση', [
      `Εύκολη μέρα ή ξεκούραση: υδατάνθρακες ${g(3, 5, kg)} τη μέρα.`,
      `Μέρα με μακρύ ή ποιοτική: ${g(6, 8, kg)} τη μέρα.`,
      `Πρωτεΐνη: ${g(1.6, 2, kg)} τη μέρα, μοιρασμένη σε 3–4 γεύματα.`,
      'Μην κόβεις υδατάνθρακες σε εβδομάδες μεγάλου φορτίου: ο χαμηλός ενεργειακός ισολογισμός αυξάνει τον κίνδυνο τραυματισμού.',
    ]],
    ['ΠΡΙΝ', 'Πριν το μακρύ ή την ποιοτική', [
      `Γεύμα 2–3 ώρες πριν: ${g(1, 2, kg)} υδατάνθρακες, λίγα λιπαρά και φυτικές ίνες (π.χ. ψωμί με μέλι, βρώμη, ρύζι).`,
      'Αν είναι νωρίς το πρωί: μικρό σνακ 30–60 λεπτά πριν (μπανάνα, μπάρα).',
      '400–600 ml νερό τις 2 ώρες πριν.',
    ]],
    ['ΚΑΤΑ', 'Κατά τη διάρκεια', [
      'Έως 75 λεπτά: συνήθως μόνο νερό.',
      '75–150 λεπτά: 30–60 g υδατάνθρακες την ώρα.',
      'Πάνω από 2,5 ώρες: 60–90 g την ώρα, με συνδυασμό γλυκόζης και φρουκτόζης.',
      'Υγρά 400–800 ml την ώρα ανάλογα με τη ζέστη. Νάτριο 300–600 mg την ώρα, περισσότερο στη ζέστη.',
      'Ξεκίνα να τρως στα πρώτα 30–45 λεπτά, σε μικρές δόσεις κάθε 20–30 λεπτά.',
    ]],
    ['ΜΕΤΑ', 'Ανάκαμψη', [
      `Μέσα σε 1 ώρα: ${g(1, 1.2, kg)} υδατάνθρακες και 20–30 g πρωτεΐνη.`,
      'Αναπλήρωσε υγρά: περίπου 1,5 φορές το βάρος που έχασες με τον ιδρώτα.',
    ]],
    ['ΣΤΟΜΑΧΙ', 'Εκπαίδευση του στομαχιού', [
      'Το στομάχι εκπαιδεύεται όπως τα πόδια. Στα μακριά ανέβαινε σταδιακά από 40 σε 60–80 g την ώρα.',
      'Χρησιμοποίησε τα ίδια τζελ, μπάρες και ποτά που θα έχει ο αγώνας ή θα κουβαλάς.',
      'Τίποτα καινούργιο την ημέρα του αγώνα.',
    ]],
    ['ΑΓΩΝΑΣ', 'Εβδομάδα αγώνα', [
      `2 ημέρες πριν: αύξησε τους υδατάνθρακες στα ${g(7, 10, kg)} τη μέρα (φόρτωση), με λιγότερες φυτικές ίνες.`,
      'Πρωινό αγώνα 3 ώρες πριν: γνώριμο γεύμα με υδατάνθρακες.',
      'Ετοίμασε το πλάνο διατροφής από την καρτέλα «Αγώνας» με το GPX της διαδρομής.',
    ]],
  ];
  return `<section class="nutri"><div class="sec-h"><h2>Διατροφή</h2></div>
    <label class="inline">Βάρος σώματος (προαιρετικό, για γραμμάρια):
      <input type="number" id="weight" inputmode="decimal" min="35" max="150" step="0.5" value="${kg || ''}" placeholder="kg"></label>
    ${cards.map(([t, h, items]) => `<details class="card lib"><summary><span class="tag">${t}</span><span class="lt">${esc(h)}</span></summary>
      <ul class="bul">${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></details>`).join('')}
    <p class="muted small">Γενικές οδηγίες για αθλητές αντοχής, όχι εξατομικευμένη διατροφική συμβουλή.</p></section>`;
}

export function viewLibrary() {
  return `<header class="top page-title"><h1>Εργαλεία</h1><p class="sub">Ενδυνάμωση, prehab και διατροφή</p></header>
    <section><div class="sec-h"><h2>Συνεδρίες</h2></div>${Object.keys(SESSIONS).map(sessionCard).join('')}</section>
    ${nutrition()}`;
}

export function bindLibrary(root, rerender) {
  root.querySelectorAll('[data-session]').forEach((b) => { b.onclick = () => startSession(b.dataset.session); });
  const w = root.querySelector('#weight');
  if (w) w.onchange = () => { const v = Number(w.value); if (v >= 35 && v <= 150) store.set(WKEY, String(v)); else store.del(WKEY); rerender(); };
}
