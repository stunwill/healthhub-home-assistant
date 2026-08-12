import { useEffect, useMemo, useState } from 'react'

type Profile = {
  id: string
  display_name: string
  colour?: string | null
  daily_calorie_target: number
  weekly_exercise_minutes_target: number
  hydration_target_ml?: number | null
  exercise_credit_mode: 'none' | 'full' | 'percentage'
  exercise_credit_percentage: number
  nutrition_display_mode: 'simple' | 'balanced' | 'detailed'
  timezone: string
  measurement_units: 'metric'
  archived: boolean
}

const API = './api/v1'

export default function App() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null)
  const [view, setView] = useState<'today' | 'week' | 'progress' | 'settings'>('today')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [quickAddOpen, setQuickAddOpen] = useState(false)

  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.id === activeProfileId) ?? null,
    [profiles, activeProfileId],
  )

  useEffect(() => {
    async function load() {
      try {
        const [profilesResponse, activeResponse] = await Promise.all([
          fetch(`${API}/profiles`),
          fetch(`${API}/active-profile`),
        ])
        if (!profilesResponse.ok) throw new Error('Could not load profiles')
        const profileData = (await profilesResponse.json()) as Profile[]
        setProfiles(profileData)
        if (activeResponse.ok) {
          const active = await activeResponse.json()
          if (active?.profile_id) setActiveProfileId(active.profile_id)
        }
        if (!activeProfileId && profileData.length === 1) setActiveProfileId(profileData[0].id)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'HealthHub could not be loaded')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  async function switchProfile(profileId: string) {
    setActiveProfileId(profileId)
    try {
      const response = await fetch(`${API}/active-profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: profileId }),
      })
      if (!response.ok) throw new Error('Could not switch profile')
      setNotice('Profile switched')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not switch profile')
    }
  }

  if (loading) return <main className="state-page">Loading HealthHub…</main>
  if (error) return <main className="state-page"><h1>HealthHub</h1><p>{error}</p></main>

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand">HealthHub</div>
          <div className="subtitle">Nutrition & activity</div>
        </div>
        <label className="profile-select">
          <span>Profile</span>
          <select value={activeProfileId ?? ''} onChange={(event) => void switchProfile(event.target.value)}>
            <option value="" disabled>Select profile</option>
            {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.display_name}</option>)}
          </select>
        </label>
      </header>

      <main className="content">
        {notice && <div className="notice" role="status">{notice}</div>}
        {profiles.length === 0 ? (
          <section className="empty-card">
            <h1>Create your first profile</h1>
            <p>Profiles keep nutrition and activity records separate. They are data selectors, not secure user accounts.</p>
            <p>Create Stu, Kristy or another household profile from Settings after installation.</p>
            <button onClick={() => setView('settings')}>Open settings</button>
          </section>
        ) : view === 'today' ? (
          <section>
            <div className="page-heading">
              <div>
                <p className="eyebrow">Today</p>
                <h1>{activeProfile ? `${activeProfile.display_name}'s day` : 'Select a profile'}</h1>
              </div>
              <button className="quick-add" onClick={() => setQuickAddOpen(true)}>+ Quick Add</button>
            </div>
            {activeProfile ? (
              <div className="target-grid">
                <article className="target-card"><span>Daily target</span><strong>{activeProfile.daily_calorie_target.toLocaleString('en-AU')} kcal</strong></article>
                <article className="target-card"><span>Exercise target</span><strong>{activeProfile.weekly_exercise_minutes_target} min/week</strong></article>
                <article className="target-card"><span>Exercise credit</span><strong>{activeProfile.exercise_credit_mode === 'percentage' ? `${activeProfile.exercise_credit_percentage}%` : activeProfile.exercise_credit_mode}</strong></article>
                <article className="target-card"><span>Nutrition view</span><strong>{activeProfile.nutrition_display_mode}</strong></article>
              </div>
            ) : null}
            <article className="empty-card diary-empty">
              <h2>No diary entries yet</h2>
              <p>Food logging arrives in a later release. HealthHub v0.1.0 establishes profiles, targets and the daily shell without inventing consumed totals.</p>
            </article>
          </section>
        ) : view === 'settings' ? (
          <section>
            <p className="eyebrow">Settings</p>
            <h1>Profiles & preferences</h1>
            <p>Profile creation and editing are backed by the v1 API. Profiles are selectors for household data, not authentication accounts.</p>
          </section>
        ) : (
          <section className="empty-card">
            <h1>{view === 'week' ? 'Week' : 'Progress'}</h1>
            <p>This area is intentionally reserved for a later HealthHub release. No placeholder totals or fake analytics are shown.</p>
          </section>
        )}
      </main>

      <nav className="bottom-nav" aria-label="Primary navigation">
        <button onClick={() => setView('today')} aria-current={view === 'today' ? 'page' : undefined}>Today</button>
        <button onClick={() => setView('week')} aria-current={view === 'week' ? 'page' : undefined}>Week</button>
        <button onClick={() => setView('progress')} aria-current={view === 'progress' ? 'page' : undefined}>Progress</button>
        <button onClick={() => setView('settings')} aria-current={view === 'settings' ? 'page' : undefined}>Settings</button>
      </nav>

      {quickAddOpen && (
        <div className="sheet-backdrop" onClick={() => setQuickAddOpen(false)}>
          <section className="quick-sheet" onClick={(event) => event.stopPropagation()}>
            <div className="sheet-handle" />
            <h2>Quick Add</h2>
            <input aria-label="Search foods and meals" placeholder="Search foods, drinks, saved meals or FoodHub recipes" disabled />
            <p>Predictive search is not active in v0.1.0. This shell defines the future search-first entry point without fake results.</p>
            <div className="secondary-actions">
              <button disabled>Scan barcode</button><button disabled>Scan nutrition label</button><button disabled>Photograph meal</button><button disabled>Upload photo</button>
              <button disabled>Quick calories</button><button disabled>Exercise</button><button disabled>Weight</button><button disabled>Water</button>
            </div>
            <button onClick={() => setQuickAddOpen(false)}>Close</button>
          </section>
        </div>
      )}
    </div>
  )
}
