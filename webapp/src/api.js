import { supabase } from './supabase.js'

// 統一 fetch helper：自動帶 Supabase JWT 去 Python API
async function authFetch(path, body) {
  const { data } = await supabase.auth.getSession()
  const token = data?.session?.access_token
  const res = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(body || {})
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${txt}`)
  }
  return res.json()
}

export const api = {
  practiceStart: (opts) => authFetch('/api/app/practice/start', opts),
  practiceAnswer: (opts) => authFetch('/api/app/practice/answer', opts),
  cvHealth: (opts) => authFetch('/api/app/cv/health', opts),
  salary: (opts) => authFetch('/api/app/salary', opts),
  ats: (opts) => authFetch('/api/app/ats', opts),
  negotiate: (opts) => authFetch('/api/app/negotiate', opts),
  debrief: (opts) => authFetch('/api/app/debrief', opts),
  tip: () => authFetch('/api/app/tip', {}),
  mbtiSubmit: (opts) => authFetch('/api/app/mbti/submit', opts)
}
