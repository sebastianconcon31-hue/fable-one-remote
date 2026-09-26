// Keeps the app itself on the phone, so it opens instantly and even with a
// weak signal. Only this app's own files are cached; the relay (ntfy.sh) is
// never touched. build.py stamps the version, so a new build replaces the old.
const CACHE = "fable-remote-20260926122803";
const SHELL = [
  "./", "index.html", "manifest.webmanifest",
  "js/three.min.js", "js/util.js", "js/orb.js", "js/relay.js", "js/remote.js",
  "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-192.png", "icons/maskable-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("fable-remote-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// The network first, so an update shows up; the cache when offline.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("index.html")))
  );
});
