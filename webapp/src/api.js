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

// 檔案上傳（multipart，唔用 JSON）
async function authUpload(path, file) {
  const { data } = await supabase.auth.getSession()
  const token = data?.session?.access_token
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(path, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${txt}`)
  }
  return res.json()
}

export const api = {
  cvExtract: (file) => authUpload('/api/app/cv/extract', file),
  practiceStart: (opts) => authFetch('/api/app/practice/start', opts),
  practiceAnswer: (opts) => authFetch('/api/app/practice/answer', opts),
  cvHealth: (opts) => authFetch('/api/app/cv/health', opts),
  salary: (opts) => authFetch('/api/app/salary', opts),
  ats: (opts) => authFetch('/api/app/ats', opts),
  negotiate: (opts) => authFetch('/api/app/negotiate', opts),
  negotiateSummary: (opts) => authFetch('/api/app/negotiate/summary', opts),
  debrief: (opts) => authFetch('/api/app/debrief', opts),
  tip: () => authFetch('/api/app/tip', {}),
  mbtiQuestions: () => authFetch('/api/app/mbti/questions', {}),
  mbtiSubmit: (opts) => authFetch('/api/app/mbti/submit', opts)
}
