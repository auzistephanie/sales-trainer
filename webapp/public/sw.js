// 面試教練 PWA service worker
// 策略：navigation → network-first fallback 快取 shell；同源 GET → stale-while-revalidate。
// API / Supabase / 第三方一律直出 network（唔快取，免拎到過期資料）。
const CACHE = 'coach-v1'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (e) => {
  const { request } = e
  if (request.method !== 'GET') return
  const url = new URL(request.url)

  // 唔快取 API / 跨網域（DeepSeek、Supabase auth/db）
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  // 導航：先 network，斷網先返快取 shell
  if (request.mode === 'navigate') {
    e.respondWith(fetch(request).catch(() => caches.match('/index.html')))
    return
  }

  // 靜態資源：stale-while-revalidate
  e.respondWith(
    caches.match(request).then((cached) => {
      const net = fetch(request).then((res) => {
        if (res && res.status === 200) {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(request, copy))
        }
        return res
      }).catch(() => cached)
      return cached || net
    })
  )
})
