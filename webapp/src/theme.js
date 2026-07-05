// 主題引擎：4 個 preset + 自選 accent 色（照 travel app 套法）。
// 套用時把顏色寫落 .app root 嘅 CSS 變數，覆蓋 styles.css 嘅 :root 預設。

export const THEMES = {
  brick:  { label: '磚紅', bg: '#f6efe0', accent: '#c1503a', accent2: '#6b7a4f', ink: '#2a211a' },
  forest: { label: '松綠', bg: '#f0ece0', accent: '#2f6b53', accent2: '#c99a3c', ink: '#22332b' },
  indigo: { label: '靛藍', bg: '#eee9dd', accent: '#35507a', accent2: '#c96a4a', ink: '#1f2733' },
  ochre:  { label: '芥黃', bg: '#f7efdc', accent: '#b9762a', accent2: '#7a8a4f', ink: '#3a2c1a' },
}

// 把 hex 調暗（做 accent-dk / hover）。
export function darken(hex, f = 0.78) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '')
  if (!m) return hex
  const n = parseInt(m[1], 16)
  const r = Math.round(((n >> 16) & 255) * f)
  const g = Math.round(((n >> 8) & 255) * f)
  const b = Math.round((n & 255) * f)
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('')
}

// 由 profile（theme + custom_accent_color）計出要套落 root 嘅 CSS 變數。
export function themeVars(profile) {
  const base = THEMES[profile?.theme] || THEMES.brick
  const accent = profile?.custom_accent_color || base.accent
  return {
    '--cream': base.bg,
    '--brick': accent,
    '--brick-dk': darken(accent),
    '--orange': accent,
    '--forest': base.accent2,
    '--ink': base.ink,
  }
}
