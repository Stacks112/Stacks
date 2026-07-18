/* Stacks service worker (v3)
   Strategy:
     - the page itself : network first, fall back to cache, so new signals appear
                         immediately but the app still opens with no connection
     - everything else : cache first, refresh in the background
   Bump CACHE below to force everyone onto a clean cache. */

const CACHE = "stacks-v15";

const SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-maskable-512.png",
  "./apple-touch-icon.png",
  "./favicon-32.png"
];

/* Cache each file on its own. If one fails, the rest still land.
   cache.addAll is all-or-nothing, which is what broke v1. */
self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await Promise.all(
      SHELL.map(url =>
        cache.add(new Request(url, { cache: "reload" })).catch(() => {})
      )
    );
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

const isDocument = request =>
  request.mode === "navigate" || request.destination === "document";

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  if (isDocument(request)) {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        const cache = await caches.open(CACHE);
        cache.put("./index.html", response.clone());
        cache.put("./", response.clone());
        return response;
      } catch (err) {
        const cached =
          (await caches.match("./index.html")) ||
          (await caches.match("./")) ||
          (await caches.match(request, { ignoreSearch: true }));
        if (cached) return cached;
        return new Response(
          "<!doctype html><meta charset=utf-8><body style='font-family:sans-serif;padding:40px;text-align:center;color:#8E93A0'>Offline. Open Stacks once with a connection, then it will work without one.</body>",
          { headers: { "Content-Type": "text/html; charset=utf-8" } }
        );
      }
    })());
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(request);
    const network = fetch(request)
      .then(response => {
        if (response && (response.status === 200 || response.type === "opaque")) {
          caches.open(CACHE).then(cache => cache.put(request, response.clone()));
        }
        return response;
      })
      .catch(() => cached);
    return cached || network;
  })());
});
