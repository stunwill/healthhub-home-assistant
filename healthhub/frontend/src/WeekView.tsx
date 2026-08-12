import { useEffect, useMemo, useState } from 'react'

type MealPeriod = 'breakfast' | 'lunch' | 'dinner' | 'snack' | 'drink'
type PlannedStatus = 'planned' | 'consumed' | 'skipped'

type PlannedEntry = {
  id: string
  food_name: string
  serving_name: string
  meal_period: MealPeriod
  planned_for: string
  servings: number
  calories: number
  status: PlannedStatus
}

type WeekDay = {
  date: string
  planned_calories: number
  planned_count: number
  consumed_calories: number
  consumed_count: number
}

type WeeklyPlan = {
  start_date: string
  end_date: string
  days: WeekDay[]
  planned_calories: number
  consumed_calories: number
}

type SearchResult = {
  id: string
  source: 'healthhub' | 'foodhub'
  name: string
  subtitle?: string | null
  calories?: number | null
  nutrition_complete: boolean
}

type Props = {
  profileId: string
  onNotice: (message: string) => void
}

const API = './api/v1'

function localDate(value: Date) {
  return new Intl.DateTimeFormat('en-CA').format(value)
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat('en-AU', { weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(`${value}T12:00:00`))
}

export default function WeekView({ profileId, onNotice }: Props) {
  const [weekStart, setWeekStart] = useState(() => {
    const current = new Date()
    const day = current.getDay() || 7
    current.setDate(current.getDate() - day + 1)
    return localDate(current)
  })
  const [summary, setSummary] = useState<WeeklyPlan | null>(null)
  const [planned, setPlanned] = useState<PlannedEntry[]>([])
  const [search, setSearch] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [selectedFood, setSelectedFood] = useState<SearchResult | null>(null)
  const [planDate, setPlanDate] = useState(localDate(new Date()))
  const [planTime, setPlanTime] = useState('12:00')
  const [mealPeriod, setMealPeriod] = useState<MealPeriod>('lunch')
  const [servings, setServings] = useState('1')
  const [recurrence, setRecurrence] = useState<'none' | 'daily' | 'weekdays' | 'weekly'>('none')

  async function loadWeek() {
    const [summaryResponse, plannedResponse] = await Promise.all([
      fetch(`${API}/profiles/${profileId}/weekly-plan?start=${weekStart}`),
      fetch(`${API}/profiles/${profileId}/planned?start=${weekStart}&days=7`),
    ])
    if (!summaryResponse.ok || !plannedResponse.ok) {
      onNotice('Could not load the weekly plan')
      return
    }
    setSummary((await summaryResponse.json()) as WeeklyPlan)
    setPlanned((await plannedResponse.json()) as PlannedEntry[])
  }

  useEffect(() => { void loadWeek() }, [profileId, weekStart])

  useEffect(() => {
    if (search.trim().length < 2) {
      setResults([])
      return
    }
    const timer = window.setTimeout(async () => {
      const response = await fetch(`${API}/quick-add/search?q=${encodeURIComponent(search.trim())}`)
      if (response.ok) setResults((await response.json()) as SearchResult[])
    }, 250)
    return () => window.clearTimeout(timer)
  }, [search])

  const grouped = useMemo(() => {
    const groups = new Map<string, PlannedEntry[]>()
    for (const entry of planned) {
      const key = localDate(new Date(entry.planned_for))
      const current = groups.get(key) ?? []
      current.push(entry)
      groups.set(key, current)
    }
    return groups
  }, [planned])

  function moveWeek(offset: number) {
    const next = new Date(`${weekStart}T12:00:00`)
    next.setDate(next.getDate() + offset * 7)
    setWeekStart(localDate(next))
  }

  async function savePlan() {
    if (!selectedFood || selectedFood.source !== 'healthhub') {
      onNotice('Choose a HealthHub food with nutrition before planning it')
      return
    }
    const plannedFor = new Date(`${planDate}T${planTime}:00`).toISOString()
    const numericServings = Number(servings)
    if (!Number.isFinite(numericServings) || numericServings <= 0) {
      onNotice('Servings must be greater than zero')
      return
    }
    const endpoint = recurrence === 'none'
      ? `${API}/profiles/${profileId}/planned`
      : `${API}/profiles/${profileId}/recurrence`
    const body = recurrence === 'none'
      ? { food_id: selectedFood.id, meal_period: mealPeriod, planned_for: plannedFor, servings: numericServings }
      : { food_id: selectedFood.id, frequency: recurrence, meal_period: mealPeriod, servings: numericServings, start_date: planDate, local_time: planTime }
    const response = await fetch(endpoint, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    if (!response.ok) {
      onNotice('Could not save the planned item')
      return
    }
    setSelectedFood(null)
    setSearch('')
    setResults([])
    setRecurrence('none')
    onNotice(recurrence === 'none' ? 'Food planned' : 'Recurring food plan created')
    await loadWeek()
  }

  async function updateStatus(entry: PlannedEntry, action: 'consume' | 'skip') {
    const response = await fetch(`${API}/profiles/${profileId}/planned/${entry.id}/${action}`, { method: 'POST' })
    if (!response.ok) {
      onNotice(`Could not ${action} this planned item`)
      return
    }
    onNotice(action === 'consume' ? 'Planned item marked as consumed' : 'Planned item skipped')
    await loadWeek()
  }

  return <section>
    <div className="page-heading">
      <div><p className="eyebrow">Week</p><h1>Plan the week</h1></div>
      <div className="week-controls"><button onClick={() => moveWeek(-1)}>Previous</button><button onClick={() => moveWeek(1)}>Next</button></div>
    </div>

    {summary && <div className="week-summary">
      <article className="target-card"><span>Planned</span><strong>{summary.planned_calories.toLocaleString('en-AU')} kcal</strong></article>
      <article className="target-card"><span>Consumed</span><strong>{summary.consumed_calories.toLocaleString('en-AU')} kcal</strong></article>
    </div>}

    <div className="week-grid">
      {(summary?.days ?? []).map((day) => <article className="week-day" key={day.date}>
        <div className="week-day-heading"><strong>{displayDate(day.date)}</strong><span>{day.planned_calories} planned · {day.consumed_calories} consumed</span></div>
        {(grouped.get(day.date) ?? []).length === 0 ? <p className="muted">Nothing planned</p> : (grouped.get(day.date) ?? []).map((entry) =>
          <div className={`planned-row status-${entry.status}`} key={entry.id}>
            <div><span className="meal-tag">{entry.meal_period}</span><strong>{entry.food_name}</strong><small>{entry.servings} × {entry.serving_name} · {Math.round(entry.calories)} kcal</small></div>
            {entry.status === 'planned' ? <div className="planned-actions"><button onClick={() => void updateStatus(entry, 'consume')}>Consumed</button><button onClick={() => void updateStatus(entry, 'skip')}>Skip</button></div> : <span className="status-label">{entry.status}</span>}
          </div>)}
      </article>)}
    </div>

    <section className="planner-card">
      <h2>Add to plan</h2>
      <input aria-label="Search food to plan" placeholder="Search HealthHub foods" value={search} onChange={(event) => { setSearch(event.target.value); setSelectedFood(null) }} />
      {results.length > 0 && <div className="search-results">{results.map((result) => <button key={`${result.source}-${result.id}`} className="search-result" onClick={() => { setSelectedFood(result); setSearch(result.name); setResults([]) }}><span><strong>{result.name}</strong><small>{result.subtitle ?? result.source}</small></span><b>{result.calories == null ? 'Nutrition pending' : `${Math.round(result.calories)} kcal`}</b></button>)}</div>}
      <div className="planner-fields">
        <label>Date<input type="date" value={planDate} onChange={(event) => setPlanDate(event.target.value)} /></label>
        <label>Time<input type="time" value={planTime} onChange={(event) => setPlanTime(event.target.value)} /></label>
        <label>Meal<select value={mealPeriod} onChange={(event) => setMealPeriod(event.target.value as MealPeriod)}><option value="breakfast">Breakfast</option><option value="lunch">Lunch</option><option value="dinner">Dinner</option><option value="snack">Snack</option><option value="drink">Drink</option></select></label>
        <label>Servings<input inputMode="decimal" value={servings} onChange={(event) => setServings(event.target.value)} /></label>
        <label>Repeat<select value={recurrence} onChange={(event) => setRecurrence(event.target.value as typeof recurrence)}><option value="none">Once</option><option value="daily">Daily</option><option value="weekdays">Weekdays</option><option value="weekly">Weekly</option></select></label>
      </div>
      <button className="quick-add" disabled={!selectedFood} onClick={() => void savePlan()}>Add to plan</button>
      {selectedFood?.source === 'foodhub' && <p className="muted">FoodHub recipes cannot be planned as consumed nutrition until authoritative per-serving nutrition is available.</p>}
    </section>
  </section>
}
