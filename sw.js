// Service worker: η εφαρμογή ανοίγει και χωρίς σύνδεση, με τα τελευταία δεδομένα που κατέβηκαν.
const CACHE = 'monopati-v3';
const SHELL = [
  './', './index.html', './app.js', './vault.js', './util.js', './edits.js', './timer.js',
  './library.js', './gpx.js', './style.css',
  './manifest.webmanifest', './icon-192.png', './icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // Δεδομένα: πρώτα το δίκτυο (για φρέσκο πρόγραμμα), αλλιώς η τελευταία αποθηκευμένη έκδοση.
  if (url.pathname.endsWith('/data.enc')) {
    e.respondWith(
      fetch(req, { cache: 'no-store' })
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Αρχεία εφαρμογής: από την κρυφή μνήμη, με ανανέωση στο παρασκήνιο.
  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || net;
    })
  );
});
