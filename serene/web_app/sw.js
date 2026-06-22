// Minimal service worker — just enough to make SERENE installable and load the
// app shell offline. API calls always go to the network (never cached).
const SHELL = "serene-shell-v2";
const FILES = ["./", "index.html", "manifest.json", "icon-192.png", "icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== SHELL).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return;          // never cache the brain
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
