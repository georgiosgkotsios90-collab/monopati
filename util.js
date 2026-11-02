// Κοινά βοηθητικά.
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const nf1 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 1 });
export const nf0 = new Intl.NumberFormat('el-GR', { maximumFractionDigits: 0 });
export const mt = (n) => nf0.format(n);
export const dur = (m) => {
  m = Math.round(m);
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return h ? `${h} ώρ ${String(mm).padStart(2, '0')} λ` : `${mm} λ`;
};
export const clock = (m) => {
  m = Math.round(m);
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;
};
export const localISO = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const atNoon = (iso) => new Date(`${iso}T12:00:00`);
export const longDate = (iso) => atNoon(iso).toLocaleDateString('el-GR', { weekday: 'long', day: 'numeric', month: 'long' });
export const shortDate = (iso) => atNoon(iso).toLocaleDateString('el-GR', { day: 'numeric', month: 'short' });
export const dayDiff = (a, b) => Math.round((atNoon(a) - atNoon(b)) / 86400000);
export const addDays = (iso, n) => { const d = atNoon(iso); d.setDate(d.getDate() + n); return localISO(d); };

export const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* αγνοείται */ } },
  del: (k) => { try { localStorage.removeItem(k); } catch { /* αγνοείται */ } },
  json: (k, def) => { try { return JSON.parse(localStorage.getItem(k)) ?? def; } catch { return def; } },
  put: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* αγνοείται */ } },
};

// Ίδιος τύπος με το impact.py: 1 ώρα στο κατώφλι = 100.
export const hrLoad = (minutes, intensity) => {
  const i = Math.min(1.15, Math.max(0.5, intensity));
  return (minutes / 60) * i * i * 100;
};
