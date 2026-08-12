import { useEffect, useMemo, useState } from 'react'
import WeekView from './WeekView'

type Profile = {
  id: string
  display_name: string
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

type DiaryEntry = {
  id: string
  food_name: string
  serving_name: string
  meal_period: 'breakfast' | 'lunch' | 'dinner' | 'snack' | 'drink'
  servings: number
  calories: number
  protein_g?: number | null
  carbohydrates_g?: number | null
  fat_g?: number | null
  consumed_at: string
}

type DailySummary = {
  calorie_target: number
  consumed_calories: number
  remaining_calories: number
  protein_g: number
  carbohydrates_g: number
  fat_g: number
  entry_count: number
}

type SearchResult = {
  id: string
  source: 'healthhub' | 'foodhub'
  result_type: string
  name: string
  subtitle?: string | null
  calories?: number | null
  nutrition_complete: boolean
}

type FoodDraft = {
  name: string
  brand: string
  serving_name: string
  serving_grams: string
  calories: string
  energy_kj: string
  protein_g: string
  carbohydrates_g: string
  fat_g: string
}

const API = './api/v1'
const emptyFood: FoodDraft = {
  name: '', brand: '', serving_name: '1 serve', serving_grams: '', calories: '', energy_kj: '',
  protein_g: '', carbohydrates_g: '', fat_g: '',
}

function todayIso() {
  return new Intl.DateTimeFormat('en-CA').format(new Date())
}

export default function App() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null)
  const [view, setView] = useState<'today' | 'week' | 'progress' | 'settings'>('today')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [quickAddOpen, setQuickAddOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [mealPeriod, setMealPeriod] = useState<DiaryEntry['meal_period']>('snack')
  const [entries, setEntries] = useState<DiaryEntry[]>([])
  const [summary, setSummary] = useState<DailySummary | null>(null)
  const [foodDraft, setFoodDraft] = useState<FoodDraft>(emptyFood)
  const [savingFood, setSavingFood] = useState(false)

  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.id === activeProfileId) ?? null,
    [profiles, activeProfileId],
  )

  async function loadToday(profileId: string) {
    const day = todayIso()
    const [entriesResponse, summaryResponse] = await Promise.all([
      fetch(`${API}/profiles/${profileId}/diary?day=${day}`),
      fetch(`${API}/profiles/${profileId}/daily-summary?day=${day}`),
    ])
    if (!entriesResponse.ok || !summaryResponse.ok) throw new Error('Could not load today’s diary')
    setEntries((await entriesResponse.json()) as DiaryEntry[])
    setSummary((await summaryResponse.json()) as DailySummary)
  }

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
        let selected: string | null = null
        if (activeResponse.ok) {
          const active = await activeResponse.json()
          if (active?.profile_id) selected = active.profile_id
        }
        if (!selected && profileData.length === 1) selected = profileData[0].id
        setActiveProfileId(selected)
        if (selected) await loadToday(selected)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'HealthHub could not be loaded')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  useEffect(() => {
    if (search.trim().length < 2) {
      setSearchResults([])
      return
    }
    const timer = window.setTimeout(async () => {
      setSearching(true)
      try {
        const response = await fetch(`${API}/quick-add/search?q=${encodeURIComponent(search.trim())}`)
        if (!response.ok) throw new Error('Search failed')
        setSearchResults((await response.json()) as SearchResult[])
      } catch (err) {
        setNotice(err instanceof Error ? err.message : 'Search failed')
      } finally {
        setSearching(false)
      }
    }, 250)
    return () => window.clearTimeout(timer)
  }, [search])

  async function switchProfile(profileId: string) {
    setActiveProfileId(profileId)
    try {
      const response = await fetch(`${API}/active-profile`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile_id: profileId }),
      })
      if (!response.ok) throw new Error('Could not switch profile')
      await loadToday(profileId)
      setNotice('Profile switched')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not switch profile')
    }
  }

  async function addSearchResult(result: SearchResult) {
    if (!activeProfileId) return
    if (result.source !== 'healthhub') {
      setNotice(result.nutrition_complete
        ? 'FoodHub recipe logging is being connected through the v1 recipe contract.'
        : 'This FoodHub recipe does not yet have authoritative per-serving nutrition.')
      return
    }
    const response = await fetch(`${API}/profiles/${activeProfileId}/diary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ food_id: result.id, meal_period: mealPeriod, consumed_at: new Date().toISOString(), servings: 1 }),
    })
    if (!response.ok) {
      setNotice('Could not add this item to the diary')
      return
    }
    await loadToday(activeProfileId)
    setQuickAddOpen(false)
    setSearch('')
    setNotice(`${result.name} added to today`)
  }

  async function deleteEntry(entryId: string) {
    if (!activeProfileId) return
    const response = await fetch(`${API}/profiles/${activeProfileId}/diary/${entryId}`, { method: 'DELETE' })
    if (response.ok) {
      await loadToday(activeProfileId)
      setNotice('Diary entry removed')
    }
  }

  async function saveFood() {
    if (!foodDraft.name.trim() || !foodDraft.calories) {
      setNotice('Food name and calories are required')
      return
    }
    setSavingFood(true)
    try {
      const numberOrNull = (value: string) => value === '' ? null : Number(value)
      const response = await fetch(`${API}/foods`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: foodDraft.name.trim(), brand: foodDraft.brand.trim() || null, kind: 'food',
          serving_name: foodDraft.serving_name.trim() || '1 serve', serving_grams: numberOrNull(foodDraft.serving_grams),
          calories: Number(foodDraft.calories), energy_kj: numberOrNull(foodDraft.energy_kj),
          protein_g: numberOrNull(foodDraft.protein_g), carbohydrates_g: numberOrNull(foodDraft.carbohydrates_g),
          fat_g: numberOrNull(foodDraft.fat_g), favourite: false, notes: null, source: 'manual',
        }),
      })
      if (!response.ok) throw new Error('Could not save food')
      setFoodDraft(emptyFood)
      setNotice('Food saved and ready for Quick Add')
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'Could not save food')
    } finally {
      setSavingFood(false)
    }
  }

  async function uploadLabel(file: File) {
    const form = new FormData()
    form.append('image', file)
    const response = await fetch(`${API}/capture/nutrition-label`, { method: 'POST', body: form })
    if (!response.ok) {
      setNotice('Could not upload nutrition label')
      return
    }
    const payload = await response.json()
    setNotice(`Label image captured (${payload.upload_id.slice(0, 8)}…). OCR is not enabled yet, review and enter the label values below.`)
    setView('settings')
    setQuickAddOpen(false)
  }

  if (loading) return <main className="state-page">Loading HealthHub…</main>
  if (error) return <main className="state-page"><h1>HealthHub</h1><p>{error}</p></main>

  return (
    <div className="app-shell">
      <header className="topbar">
        <div><div className="brand">HealthHub</div><div className="subtitle">Nutrition & activity</div></div>
        <label className="profile-select"><span>Profile</span>
          <select value={activeProfileId ?? ''} onChange={(event) => void switchProfile(event.target.value)}>
            <option value="" disabled>Select profile</option>
            {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.display_name}</option>)}
          </select>
        </label>
      </header>

      <main className="content">
        {notice && <div className="notice" role="status">{notice}</div>}
        {profiles.length === 0 ? <section className="empty-card"><h1>Create your first profile</h1><p>Profiles separate household nutrition records. They are not secure accounts.</p><button onClick={() => setView('settings')}>Open settings</button></section>
        : view === 'today' ? <section>
          <div className="page-heading"><div><p className="eyebrow">Today</p><h1>{activeProfile ? `${activeProfile.display_name}'s day` : 'Select a profile'}</h1></div><button className="quick-add" onClick={() => setQuickAddOpen(true)}>+ Quick Add</button></div>
          {activeProfile && summary ? <div className="target-grid">
            <article className="target-card"><span>Remaining</span><strong>{summary.remaining_calories.toLocaleString('en-AU')} kcal</strong></article>
            <article className="target-card"><span>Consumed</span><strong>{summary.consumed_calories.toLocaleString('en-AU')} kcal</strong></article>
            <article className="target-card"><span>Daily target</span><strong>{summary.calorie_target.toLocaleString('en-AU')} kcal</strong></article>
            <article className="target-card"><span>Protein</span><strong>{summary.protein_g.toFixed(1)} g</strong></article>
          </div> : null}
          <section className="diary-list">
            <div className="section-heading"><h2>Food diary</h2><span>{summary?.entry_count ?? 0} items</span></div>
            {entries.length === 0 ? <article className="empty-card"><h2>Nothing logged yet</h2><p>Use Quick Add to search your HealthHub foods and available FoodHub recipes.</p></article>
            : entries.map((entry) => <article className="diary-row" key={entry.id}><div><span className="meal-tag">{entry.meal_period}</span><strong>{entry.food_name}</strong><small>{entry.servings} × {entry.serving_name}</small></div><div className="diary-energy"><strong>{Math.round(entry.calories)} kcal</strong><button aria-label={`Remove ${entry.food_name}`} onClick={() => void deleteEntry(entry.id)}>Remove</button></div></article>)}
          </section>
        </section>
        : view === 'week' && activeProfileId ? <WeekView profileId={activeProfileId} onNotice={setNotice} />
        : view === 'settings' ? <section><p className="eyebrow">Settings</p><h1>Foods & preferences</h1><p>Add foods from Australian packaging or other trusted sources. Values are stored per serving and can be edited later through the API.</p>
          <div className="food-form">
            <label>Name<input value={foodDraft.name} onChange={(e) => setFoodDraft({ ...foodDraft, name: e.target.value })} /></label>
            <label>Brand<input value={foodDraft.brand} onChange={(e) => setFoodDraft({ ...foodDraft, brand: e.target.value })} /></label>
            <label>Serving<input value={foodDraft.serving_name} onChange={(e) => setFoodDraft({ ...foodDraft, serving_name: e.target.value })} /></label>
            <label>Serving grams<input inputMode="decimal" value={foodDraft.serving_grams} onChange={(e) => setFoodDraft({ ...foodDraft, serving_grams: e.target.value })} /></label>
            <label>Energy (kJ)<input inputMode="decimal" value={foodDraft.energy_kj} onChange={(e) => setFoodDraft({ ...foodDraft, energy_kj: e.target.value })} /></label>
            <label>Calories (kcal)<input inputMode="decimal" value={foodDraft.calories} onChange={(e) => setFoodDraft({ ...foodDraft, calories: e.target.value })} /></label>
            <label>Protein (g)<input inputMode="decimal" value={foodDraft.protein_g} onChange={(e) => setFoodDraft({ ...foodDraft, protein_g: e.target.value })} /></label>
            <label>Carbohydrates (g)<input inputMode="decimal" value={foodDraft.carbohydrates_g} onChange={(e) => setFoodDraft({ ...foodDraft, carbohydrates_g: e.target.value })} /></label>
            <label>Fat (g)<input inputMode="decimal" value={foodDraft.fat_g} onChange={(e) => setFoodDraft({ ...foodDraft, fat_g: e.target.value })} /></label>
          </div><button className="quick-add" disabled={savingFood} onClick={() => void saveFood()}>{savingFood ? 'Saving…' : 'Save food'}</button>
        </section>
        : <section className="empty-card"><h1>Progress</h1><p>This area remains reserved for a later HealthHub release. No fake totals or analytics are shown.</p></section>}
      </main>

      <nav className="bottom-nav" aria-label="Primary navigation"><button onClick={() => setView('today')} aria-current={view === 'today' ? 'page' : undefined}>Today</button><button onClick={() => setView('week')} aria-current={view === 'week' ? 'page' : undefined}>Week</button><button onClick={() => setView('progress')} aria-current={view === 'progress' ? 'page' : undefined}>Progress</button><button onClick={() => setView('settings')} aria-current={view === 'settings' ? 'page' : undefined}>Settings</button></nav>

      {quickAddOpen && <div className="sheet-backdrop" onClick={() => setQuickAddOpen(false)}><section className="quick-sheet" onClick={(event) => event.stopPropagation()}><div className="sheet-handle" /><h2>Quick Add</h2>
        <label className="meal-period">Add to<select value={mealPeriod} onChange={(e) => setMealPeriod(e.target.value as DiaryEntry['meal_period'])}><option value="breakfast">Breakfast</option><option value="lunch">Lunch</option><option value="dinner">Dinner</option><option value="snack">Snack</option><option value="drink">Drink</option></select></label>
        <input autoFocus aria-label="Search foods and meals" placeholder="Search foods, drinks or FoodHub recipes" value={search} onChange={(e) => setSearch(e.target.value)} />
        {searching && <p>Searching…</p>}
        <div className="search-results">{searchResults.map((result) => <button key={`${result.source}-${result.id}`} className="search-result" onClick={() => void addSearchResult(result)}><span><strong>{result.name}</strong><small>{result.subtitle} · {result.source === 'foodhub' ? 'FoodHub' : 'HealthHub'}</small></span><b>{result.calories == null ? 'Nutrition pending' : `${Math.round(result.calories)} kcal`}</b></button>)}</div>
        {search.trim().length >= 2 && !searching && searchResults.length === 0 && <p>No matching foods yet. Add a food in Settings.</p>}
        <div className="secondary-actions"><label className="upload-action">Nutrition label<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => { const file = e.target.files?.[0]; if (file) void uploadLabel(file) }} /></label><button disabled>Scan barcode</button><button disabled>Photograph meal</button><button disabled>Quick calories</button><button disabled>Exercise</button><button disabled>Weight</button><button disabled>Water</button></div>
        <button onClick={() => setQuickAddOpen(false)}>Close</button></section></div>}
    </div>
  )
}
