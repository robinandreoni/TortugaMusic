// Tortuga Music & TV - Service Worker per PWA Desktop
const CACHE_NAME = 'tortuga-cache-v1';
const STATIC_ASSETS = [
  '/',
  '/tv.html',
  '/static/style.css',
  '/static/style_tv.css',
  '/static/app.js',
  '/static/app_tv.js',
  '/static/hls.min.js',
  '/static/tartugalogo_transparent.png',
  '/static/icona_app.jpg',
  '/static/1.mp3'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // Non mettere in cache le chiamate API o gli stream video/audio dinamici
  if (event.request.url.includes('/api/')) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
