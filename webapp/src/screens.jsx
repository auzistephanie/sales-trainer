import { useState, useEffect } from 'react'
import { supabase } from './supabase.js'
import { api } from './api.js'

const todayStr = () => new Date().toISOString().slice(0, 10)

/* ---------------- LOGIN ---------------- */
export function Login({ onLogin }) {
  return (
    <div className="center-screen login view">
      <div className="logo">🎯</div>
      <h2>面試教練</h2>
      <p>練到穩陣先去見工<br />你嘅隨身 AI 面試特訓</p>
      <button className="lbtn" onClick={onLogin}>
        <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.5 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.9c-.3 1.4-1 2.5-2.2 3.3v2.8h3.6c2.1-1.9 3.2-4.8 3.2-7.9z"/><path fill="#34A853" d="M12 23c2.9 0 5.4-1 7.2-2.6l-3.6-2.8c-1 .7-2.2 1.1-3.6 1.1-2.8 0-5.1-1.9-6-4.4H2.3v2.9C4.1 20.6 7.8 23 12 23z"/><path fill="#FBBC05" d="M6 14.3c-.2-.7-.4-1.4-.4-2.3s.1-1.6.4-2.3V6.8H2.3C1.5 8.3 1 10.1 1 12s.5 3.7 1.3 5.2L6 14.3z"/><path fill="#EA4335" d="M12 5.4c1.6 0 3 .5 4.1 1.6l3.1-3.1C17.4 2.1 14.9 1 12 1 7.8 1 4.1 3.4 2.3 6.8L6 9.7c.9-2.5 3.2-4.3 6-4.3z"/></svg>
        用 Google 繼續
      </button>
      <small>用 Google 一撳登入，進度會跨手機、電腦同步。首次登入會做一次 MBTI 檢測。</small>
    </div>
  )
}

/* ---------------- HOME ---------------- */
export function Home({ profile, stats, onStart, onTool }) {
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const name = profile?.display_name || '你'

  async function start() {
    setLoading(true); setErr('')
    try {
      const sc = await api.practiceStart({ difficulty: '中級' })
      await supabase.from('coach_practice_sessions').insert({
        user_id: profile.id, qtype: sc.qtype, industry: sc.industry,
        difficulty: sc.difficulty, scenario: sc
      })
      onStart(sc)
    } catch (e) { setErr('開始練習失敗：' + e.message) }
    setLoading(false)
  }

  return (
    <div className="view pad">
      <div className="greet">
        <span className="hi">今日想練邊方面？👋</span>
        <h2>{name}，練起佢！</h2>
        <div className="streak">🔥 連續練習 {stats?.streak_days ?? 0} 日</div>
      </div>
      <div className="statgrid">
        <div className="stat"><span className="num">{stats?.total_answered ?? 0}</span><small>已練題數</small></div>
        <div className="stat"><span className="num">{stats?.avg_score ? Math.round(stats.avg_score) : 0}</span><small>平均分</small></div>
        <div className="stat"><span className="num">{stats?.streak_days ?? 0}</span><small>連勝日</small></div>
      </div>
      {err && <div className="err">{err}</div>}
      <button className="cta-big" onClick={start} disabled={loading}>
        {loading ? '生成緊場景…' : '🎬 開始今日練習'}
      </button>
      <div className="sect-t">求職工具箱</div>
      <div className="fgrid">
        {[
          ['cv', '📄', 'CV Health', 'AI 體檢你份 CV', 'var(--brick)'],
          ['salary', '💰', '薪酬情報', '市場人工範圍', 'var(--mustard)'],
          ['ats', '✅', 'ATS 檢查', '過機器篩選', 'var(--forest)'],
          ['negotiate', '🤝', '談判演練', '傾人工對白', 'var(--orange)'],
          ['debrief', '📝', '面試覆盤', '即刻執返好', 'var(--brick-dk)'],
          ['mbti', '🧭', 'MBTI', '個人化 coaching', '#6b7a4f']
        ].map(([k, ic, t, d, c]) => (
          <button key={k} className="fcard" onClick={() => onTool(k)}>
            <div className="fic" style={{ background: c }}>{ic}</div>
            <h3>{t}</h3><p>{d}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ---------------- PRACTICE ---------------- */
export function Practice({ scenario, profile, onBack, onScored }) {
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  if (!scenario) return <div className="pad"><p>未有題目，返首頁開始練習。</p><button className="cta-big" onClick={onBack}>返首頁</button></div>

  async function submit() {
    if (!answer.trim()) return
    setLoading(true); setErr('')
    try {
      const fullScenario = scenario.scenario || scenario  // API 回傳包住一層
      const r = await api.practiceAnswer({ scenario: fullScenario, answer, profile })
      // 存答案
      await supabase.from('coach_practice_answers').insert({
        user_id: profile.id, answer_text: answer, score: r.score, feedback: { text: r.feedback }
      })
      await updateStats(profile.id, r.score)
      onScored(r)
    } catch (e) { setErr('評分失敗：' + e.message) }
    setLoading(false)
  }

  return (
    <div className="view pad">
      <div className="pr-head" style={{ background: 'var(--brick)' }}>
        <button className="bk" onClick={onBack}>‹</button>
        <div><b>{scenario.qtype || '面試練習'}</b><span>{scenario.difficulty || '中級'} · {scenario.industry || ''}</span></div>
      </div>
      <div className="chat">
        <div className="msg bot">📋 {scenario.question}</div>
        {scenario.hint && <div className="msg bot">💡 提示：{scenario.hint}</div>}
      </div>
      <div className="answer-box">
        <textarea value={answer} onChange={e => setAnswer(e.target.value)}
          placeholder="喺度打你嘅答案…（建議 1-2 分鐘，貼近真實面試）" />
        <button className="submit-a" onClick={submit} disabled={loading || !answer.trim()}>
          {loading ? 'AI 評分緊…' : '提交評分'}
        </button>
      </div>
      {err && <div className="err">{err}</div>}
    </div>
  )
}

async function updateStats(userId, score) {
  const { data: st } = await supabase.from('coach_stats').select('*').eq('user_id', userId).single()
  const total = (st?.total_answered ?? 0) + 1
  const avg = st?.total_answered ? ((st.avg_score * st.total_answered) + score) / total : score
  let streak = st?.streak_days ?? 0
  const today = todayStr()
  const last = st?.last_practice_date
  if (last !== today) {
    const y = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
    streak = (last === y) ? streak + 1 : 1
  } else if (streak === 0) streak = 1
  await supabase.from('coach_stats').update({
    total_answered: total, avg_score: Math.round(avg * 10) / 10,
    streak_days: streak, last_practice_date: today
  }).eq('user_id', userId)
}

/* ---------------- SCORE ---------------- */
export function Score({ result, onNext, onHome }) {
  const score = result?.score ?? 0
  const C = 2 * Math.PI * 66
  const off = C * (1 - score / 100)
  return (
    <div className="view pad">
      <div className="pr-head" style={{ background: 'var(--forest)' }}>
        <button className="bk" onClick={onHome}>‹</button>
        <div><b>評分結果</b><span>AI 已評估你嘅答案</span></div>
      </div>
      <div className="ring">
        <svg width="150" height="150">
          <circle cx="75" cy="75" r="66" fill="none" stroke="rgba(42,33,26,.1)" strokeWidth="12" />
          <circle cx="75" cy="75" r="66" fill="none" stroke="#c1503a" strokeWidth="12" strokeLinecap="round"
            strokeDasharray={C} strokeDashoffset={off} />
        </svg>
        <div className="val"><span className="num">{score}</span><small>/ 100</small></div>
      </div>
      <div className="fb-card">
        <div className="fb-t" style={{ color: 'var(--brick-dk)' }}>📝 AI 評語</div>
        <p>{result?.feedback || '（未有評語）'}</p>
      </div>
      <button className="cta-big" onClick={onNext}>下一題 ▸</button>
    </div>
  )
}

/* ---------------- TOOL DETAIL ---------------- */
const TOOLS = {
  cv: { t: 'CV Health', c: 'var(--brick)', d: '貼上你份 CV 內容，AI 幫你體檢、揪弱位。',
    fields: [['cv_text', 'textarea', '貼上 CV 全文…']], call: (v) => api.cvHealth(v) },
  salary: { t: '薪酬情報', c: 'var(--mustard)', d: '輸入職位同期望人工，睇市場範圍。',
    fields: [['role', 'input', '職位（例：Product Manager）'], ['expected_salary', 'input', '期望月薪（例：45000）'], ['industry', 'input', '行業（可留空）']], call: (v) => api.salary(v) },
  ats: { t: 'ATS 檢查', c: 'var(--forest)', d: '貼 JD 同 CV，睇過機器篩選機率。',
    fields: [['jd_text', 'textarea', '貼上 Job Description…'], ['cv_text', 'textarea', '貼上 CV 全文…']], call: (v) => api.ats(v) },
  negotiate: { t: '談判演練', c: 'var(--orange)', d: '講你嘅 offer 情況，AI 陪你演練談判。',
    fields: [['offer_details', 'input', 'Offer 情況（職位 / 人工）'], ['user_message', 'textarea', '你想講嘅說話…']], call: (v) => api.negotiate({ ...v, round_num: 1 }) },
  debrief: { t: '面試覆盤', c: 'var(--brick-dk)', d: '講返你面試經過，AI 幫你覆盤。',
    fields: [['company', 'input', '公司 / 職位'], ['debrief_text', 'textarea', '面試經過同你嘅感受…']], call: (v) => api.debrief({ job_info: { company: v.company }, debrief_text: v.debrief_text }) },
  mbti: { t: 'MBTI 檢測', c: '#6b7a4f', d: '20 題快速檢測，教練會照你性格調整 coaching。', mbti: true }
}

export function ToolDetail({ toolKey, profile, onBack }) {
  const cfg = TOOLS[toolKey]
  const [vals, setVals] = useState({})
  const [loading, setLoading] = useState(false)
  const [out, setOut] = useState(null)
  const [err, setErr] = useState('')

  async function run() {
    setLoading(true); setErr(''); setOut(null)
    try {
      const r = await cfg.call(vals)
      setOut(typeof r === 'string' ? r : (r.result || r.message || JSON.stringify(r, null, 2)))
    } catch (e) { setErr('失敗：' + e.message) }
    setLoading(false)
  }

  return (
    <div className="view pad">
      <div className="td-head" style={{ background: cfg.c }}>
        <button className="bk" onClick={onBack}>‹</button>
        <h2>{cfg.t}</h2>
      </div>
      <p style={{ fontSize: 13.5, color: 'var(--ink-soft)', marginBottom: 16 }}>{cfg.d}</p>

      {cfg.mbti ? (
        <div className="upload">
          <div className="u-ic">🧭</div>
          <p>MBTI 20 題檢測<br /><small>完整版稍後推出，會照你性格調整 coaching</small></p>
        </div>
      ) : (
        <>
          {cfg.fields.map(([k, type, ph]) =>
            type === 'textarea'
              ? <textarea key={k} className="field" placeholder={ph} value={vals[k] || ''} onChange={e => setVals({ ...vals, [k]: e.target.value })} />
              : <input key={k} className="field" placeholder={ph} value={vals[k] || ''} onChange={e => setVals({ ...vals, [k]: e.target.value })} />
          )}
          {err && <div className="err">{err}</div>}
          <button className="cta-big" style={{ background: cfg.c }} onClick={run} disabled={loading}>
            {loading ? 'AI 分析緊…' : '開始分析'}
          </button>
          {out && <div className="result-box">{out}</div>}
        </>
      )}
    </div>
  )
}

/* ---------------- STATS ---------------- */
export function Stats({ stats, onPractice }) {
  const [bars, setBars] = useState([])
  useEffect(() => {
    supabase.from('coach_practice_answers').select('score,created_at').order('created_at', { ascending: false }).limit(7)
      .then(({ data }) => setBars((data || []).reverse()))
  }, [])
  const max = Math.max(100, ...bars.map(b => b.score || 0))
  return (
    <div className="view pad">
      <div className="greet"><h2>進度追蹤</h2><span className="hi">你嘅成長曲線</span></div>
      <div className="sect-t">近 7 次得分</div>
      {bars.length ? (
        <div className="bars">
          {bars.map((b, i) => (
            <div key={i} className="bar" style={{ height: `${Math.max(8, (b.score / max) * 100)}%` }}>
              <b>{b.score}</b>
            </div>
          ))}
        </div>
      ) : <div className="result-box">仲未有練習紀錄，去練幾題先！</div>}
      <div className="statgrid">
        <div className="stat"><span className="num">{stats?.streak_days ?? 0}</span><small>連勝日數</small></div>
        <div className="stat"><span className="num">{stats?.total_answered ?? 0}</span><small>累積題數</small></div>
        <div className="stat"><span className="num">{stats?.avg_score ? Math.round(stats.avg_score) : 0}</span><small>平均分</small></div>
      </div>
      <button className="cta-big" style={{ marginTop: 20 }} onClick={onPractice}>🎬 繼續練習</button>
    </div>
  )
}

/* ---------------- PROFILE ---------------- */
export function Profile({ profile, session, onTool, onStats }) {
  async function logout() { await supabase.auth.signOut() }
  return (
    <div className="view pad">
      <div className="prof-top">
        <div className="av">🦊</div>
        <h2>{profile?.display_name || '你'}</h2>
        <small>{session?.user?.email}</small><br />
        <span className="mbti-badge">{profile?.mbti ? `${profile.mbti} · coaching 已開` : 'MBTI 未做'}</span>
      </div>
      <button className="list-card" onClick={() => onTool('mbti')}><div className="li-ic" style={{ background: 'rgba(107,122,79,.2)' }}>🧭</div><div><h3>MBTI 檢測</h3><p>更新你嘅 coaching 風格</p></div><span className="arw">›</span></button>
      <button className="list-card" onClick={onStats}><div className="li-ic" style={{ background: 'rgba(193,80,58,.15)' }}>📊</div><div><h3>我嘅進度</h3><p>成長曲線同連勝</p></div><span className="arw">›</span></button>
      <button className="list-card" onClick={() => onTool('cv')}><div className="li-ic" style={{ background: 'rgba(47,74,62,.14)' }}>📄</div><div><h3>CV Health</h3><p>體檢你份 CV</p></div><span className="arw">›</span></button>
      <button className="list-card" onClick={logout}><div className="li-ic" style={{ background: 'rgba(42,33,26,.1)' }}>🚪</div><div><h3>登出</h3><p>{session?.user?.email}</p></div><span className="arw">›</span></button>
    </div>
  )
}

/* ---------------- BOTTOM NAV ---------------- */
export function BottomNav({ screen, onNav }) {
  const items = [['home', '🏠', '首頁'], ['practice', '🎬', '練習'], ['stats', '📊', '進度'], ['profile', '🦊', '我']]
  const activeFor = (s) => (screen === s || (s === 'practice' && screen === 'score') ? 'item on' : 'item')
  return (
    <div className="bnav">
      {items.map(([k, ic, t]) => (
        <button key={k} className={activeFor(k)} onClick={() => onNav(k === 'practice' ? 'home' : k)}>
          <span className="bi">{ic}</span>{t}
        </button>
      ))}
    </div>
  )
}
