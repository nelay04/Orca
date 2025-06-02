self.addEventListener('install', function (event) {
  console.log('[Service Worker] Installed');
});

self.addEventListener('fetch', function (event) {
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

const CACHE_NAME = 'orca-cache-v1.0.2'; // increment this on update

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) return caches.delete(key);
        })
      )
    )
  );
});
