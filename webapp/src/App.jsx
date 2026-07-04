import { useEffect, useState } from 'react'
import { supabase, signInWithGoogle } from './supabase.js'
import { Login, Home, Practice, Score, ToolDetail, Stats, Profile, BottomNav } from './screens.jsx'

// 首次登入確保有 profile + stats row（app 層做，唔用 auth trigger，免同其他 app 撞）
async function ensureUserRows(user) {
  await supabase.from('coach_profiles').upsert(
    { id: user.id, email: user.email, display_name: user.user_metadata?.name || user.email },
    { onConflict: 'id', ignoreDuplicates: true }
  )
  await supabase.from('coach_stats').upsert(
    { user_id: user.id },
    { onConflict: 'user_id', ignoreDuplicates: true }
  )
}

export default function App() {
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [stats, setStats] = useState(null)
  const [screen, setScreen] = useState('home')
  const [scenario, setScenario] = useState(null)   // 當前練習題
  const [result, setResult] = useState(null)        // 評分結果
  const [toolKey, setToolKey] = useState('cv')

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session?.user) { setProfile(null); setStats(null); return }
    ;(async () => {
      await ensureUserRows(session.user)
      const { data: p } = await supabase.from('coach_profiles').select('*').eq('id', session.user.id).single()
      const { data: st } = await supabase.from('coach_stats').select('*').eq('user_id', session.user.id).single()
      setProfile(p); setStats(st)
    })()
  }, [session])

  async function refreshStats() {
    if (!session?.user) return
    const { data: st } = await supabase.from('coach_stats').select('*').eq('user_id', session.user.id).single()
    setStats(st)
  }

  if (loading) return <div className="app"><div className="spin" /></div>
  if (!session) return <div className="app"><Login onLogin={signInWithGoogle} /></div>

  const nav = (s) => { setScreen(s) }
  const openTool = (k) => { setToolKey(k); setScreen('tool') }

  return (
    <div className="app">
      <div className="app-body">
        {screen === 'home' && (
          <Home profile={profile} stats={stats}
            onStart={(sc) => { setScenario(sc); setScreen('practice') }}
            onTool={openTool} />
        )}
        {screen === 'practice' && (
          <Practice scenario={scenario} profile={profile}
            onBack={() => nav('home')}
            onScored={(r) => { setResult(r); refreshStats(); setScreen('score') }} />
        )}
        {screen === 'score' && (
          <Score result={result} onNext={() => nav('practice')} onHome={() => nav('home')} />
        )}
        {screen === 'tool' && (
          <ToolDetail toolKey={toolKey} profile={profile} onBack={() => nav('home')} />
        )}
        {screen === 'stats' && <Stats stats={stats} onPractice={() => nav('practice')} />}
        {screen === 'profile' && (
          <Profile profile={profile} session={session} onTool={openTool} onStats={() => nav('stats')} />
        )}
      </div>
      <BottomNav screen={screen} onNav={nav} />
    </div>
  )
}
