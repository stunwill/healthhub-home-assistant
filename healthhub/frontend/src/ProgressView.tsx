import { useEffect, useMemo, useState } from 'react'

type WeightEntry = {
  id: string
  weight_kg: number
  measured_at: string
}

type WaterEntry = {
  id: string
  amount_ml: number
  consumed_at: string
}

type ProgressSummary = {
  exercise_minutes: number
  exercise_minutes_last_7_days: number
  exercise_minutes_target: number
  exercise_calories: number
  hydration_ml_today: number
  hydration_target_ml?: number | null
  latest_weight_kg?: number | null
  latest_weight_at?: string | null
  starting_weight_kg?: number | null
  goal_weight_kg?: number | null
  change_from_start_kg?: number | null
  change_last_30_days_kg?: number | null
  weight_entries: WeightEntry[]
}

type Props = {
  profileId: string
  onNotice: (message: string) => void
  onActivityChanged: () => Promise<void>
}

const API = './api/v1'

function localDateTimeInput() {
  const now = new Date()
  const offset = now.getTimezoneOffset()
  return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 16)
}

function isoFromLocalInput(value: string) {
  return new Date(value).toISOString()
}

export default function ProgressView({ profileId, onNotice, onActivityChanged }: Props) {
  const [progress, setProgress] = useState<ProgressSummary | null>(null)
  const [waterEntries, setWaterEntries] = useState<WaterEntry[]>([])
  const [exerciseName, setExerciseName] = useState('')
  const [exerciseMinutes, setExerciseMinutes] = useState('')
  const [exerciseCalories, setExerciseCalories] = useState('')
  const [exerciseAt, setExerciseAt] = useState(localDateTimeInput())
  const [weight, setWeight] = useState('')
  const [weightAt, setWeightAt] = useState(localDateTimeInput())
  const [waterAmount, setWaterAmount] = useState('250')
  const [saving, setSaving] = useState(false)

  async function loadProgress() {
    const [progressResponse, waterResponse] = await Promise.all([
      fetch(`${API}/profiles/${profileId}/progress?days=90`),
      fetch(`${API}/profiles/${profileId}/water`),
    ])
    if (!progressResponse.ok || !waterResponse.ok) {
      onNotice('Could not load progress')
      return
    }
    setProgress((await progressResponse.json()) as ProgressSummary)
    setWaterEntries((await waterResponse.json()) as WaterEntry[])
  }

  useEffect(() => { void loadProgress() }, [profileId])

  async function saveExercise() {
    const minutes = Number(exerciseMinutes)
    const calories = Number(exerciseCalories)
    if (!exerciseName.trim() || !Number.isFinite(minutes) || minutes <= 0 || !Number.isFinite(calories) || calories < 0) {
      onNotice('Enter an activity, duration and calories burned')
      return
    }
    setSaving(true)
    try {
      const response = await fetch(`${API}/profiles/${profileId}/exercise`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activity_name: exerciseName.trim(), duration_minutes: minutes, calories_burned: calories, completed_at: isoFromLocalInput(exerciseAt) }),
      })
      if (!response.ok) throw new Error('Could not save exercise')
      setExerciseName('')
      setExerciseMinutes('')
      setExerciseCalories('')
      onNotice('Exercise logged')
      await Promise.all([loadProgress(), onActivityChanged()])
    } catch (error) {
      onNotice(error instanceof Error ? error.message : 'Could not save exercise')
    } finally { setSaving(false) }
  }

  async function saveWeight() {
    const value = Number(weight)
    if (!Number.isFinite(value) || value <= 0) {
      onNotice('Enter a valid weight in kilograms')
      return
    }
    setSaving(true)
    try {
      const response = await fetch(`${API}/profiles/${profileId}/weights`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weight_kg: value, measured_at: isoFromLocalInput(weightAt) }),
      })
      if (!response.ok) throw new Error('Could not save weight')
      setWeight('')
      onNotice('Weight logged')
      await loadProgress()
    } catch (error) {
      onNotice(error instanceof Error ? error.message : 'Could not save weight')
    } finally { setSaving(false) }
  }

  async function saveWater(amountOverride?: number) {
    const value = amountOverride ?? Number(waterAmount)
    if (!Number.isFinite(value) || value <= 0) {
      onNotice('Enter a valid water amount in mL')
      return
    }
    setSaving(true)
    try {
      const response = await fetch(`${API}/profiles/${profileId}/water`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_ml: value, consumed_at: new Date().toISOString() }),
      })
      if (!response.ok) throw new Error('Could not save water')
      onNotice(`${value} mL water logged`)
      await Promise.all([loadProgress(), onActivityChanged()])
    } catch (error) {
      onNotice(error instanceof Error ? error.message : 'Could not save water')
    } finally { setSaving(false) }
  }

  const target = progress?.exercise_minutes_target ?? 0
  const exercisePercent = target > 0 ? Math.min(100, Math.round(((progress?.exercise_minutes_last_7_days ?? 0) / target) * 100)) : 0
  const hydrationTarget = progress?.hydration_target_ml ?? 0
  const hydrationPercent = hydrationTarget > 0 ? Math.min(100, Math.round(((progress?.hydration_ml_today ?? 0) / hydrationTarget) * 100)) : 0
  const chartWeights = useMemo(() => [...(progress?.weight_entries ?? [])].reverse().slice(-20), [progress])
  const weightMin = chartWeights.length ? Math.min(...chartWeights.map((item) => item.weight_kg)) : 0
  const weightMax = chartWeights.length ? Math.max(...chartWeights.map((item) => item.weight_kg)) : 0
  const weightRange = Math.max(1, weightMax - weightMin)

  return <section>
    <div className="page-heading"><div><p className="eyebrow">Progress</p><h1>Activity, hydration & weight</h1></div></div>

    <div className="progress-grid">
      <article className="target-card"><span>Exercise, last 7 days</span><strong>{progress?.exercise_minutes_last_7_days ?? 0} min</strong><div className="progress-track"><span style={{ width: `${exercisePercent}%` }} /></div><small>{target ? `${exercisePercent}% of ${target} min target` : 'No weekly target set'}</small></article>
      <article className="target-card"><span>Water today</span><strong>{(progress?.hydration_ml_today ?? 0).toLocaleString('en-AU')} mL</strong><div className="progress-track"><span style={{ width: `${hydrationPercent}%` }} /></div><small>{hydrationTarget ? `${hydrationPercent}% of ${hydrationTarget.toLocaleString('en-AU')} mL target` : 'No hydration target set'}</small></article>
      <article className="target-card"><span>Latest weight</span><strong>{progress?.latest_weight_kg == null ? 'Not logged' : `${progress.latest_weight_kg.toFixed(1)} kg`}</strong><small>{progress?.change_last_30_days_kg == null ? '30-day change unavailable' : `${progress.change_last_30_days_kg > 0 ? '+' : ''}${progress.change_last_30_days_kg.toFixed(1)} kg over ~30 days`}</small></article>
      <article className="target-card"><span>Goal weight</span><strong>{progress?.goal_weight_kg == null ? 'Not set' : `${progress.goal_weight_kg.toFixed(1)} kg`}</strong><small>HealthHub does not prescribe a target</small></article>
    </div>

    <div className="progress-forms">
      <section className="planner-card">
        <h2>Log water</h2>
        <div className="water-presets"><button onClick={() => void saveWater(250)}>+250 mL</button><button onClick={() => void saveWater(500)}>+500 mL</button><button onClick={() => void saveWater(750)}>+750 mL</button></div>
        <label>Custom amount (mL)<input inputMode="numeric" value={waterAmount} onChange={(event) => setWaterAmount(event.target.value)} /></label>
        <button className="quick-add" disabled={saving} onClick={() => void saveWater()}>Save water</button>
        {waterEntries.length > 0 && <small>Today: {waterEntries.length} entries</small>}
      </section>

      <section className="planner-card">
        <h2>Log exercise</h2>
        <label>Activity<input value={exerciseName} onChange={(event) => setExerciseName(event.target.value)} placeholder="e.g. Walk, gym, cycling" /></label>
        <div className="inline-fields"><label>Minutes<input inputMode="numeric" value={exerciseMinutes} onChange={(event) => setExerciseMinutes(event.target.value)} /></label><label>Calories burned<input inputMode="decimal" value={exerciseCalories} onChange={(event) => setExerciseCalories(event.target.value)} /></label></div>
        <label>Completed<input type="datetime-local" value={exerciseAt} onChange={(event) => setExerciseAt(event.target.value)} /></label>
        <button className="quick-add" disabled={saving} onClick={() => void saveExercise()}>Save exercise</button>
        <p className="muted">Enter calories from a trusted device or source. HealthHub does not estimate exercise calories.</p>
      </section>

      <section className="planner-card">
        <h2>Log weight</h2>
        <label>Weight (kg)<input inputMode="decimal" value={weight} onChange={(event) => setWeight(event.target.value)} /></label>
        <label>Measured<input type="datetime-local" value={weightAt} onChange={(event) => setWeightAt(event.target.value)} /></label>
        <button className="quick-add" disabled={saving} onClick={() => void saveWeight()}>Save weight</button>
      </section>
    </div>

    <section className="weight-history">
      <div className="section-heading"><h2>Weight trend</h2><span>Last 90 days</span></div>
      {chartWeights.length < 2 ? <article className="empty-card"><p>Log at least two weights to show a trend.</p></article> : <div className="weight-chart" aria-label="Weight trend chart">{chartWeights.map((entry) => <div className="weight-bar-wrap" key={entry.id} title={`${entry.weight_kg.toFixed(1)} kg`}><div className="weight-bar" style={{ height: `${25 + ((entry.weight_kg - weightMin) / weightRange) * 75}%` }} /><small>{entry.weight_kg.toFixed(1)}</small></div>)}</div>}
      {(progress?.weight_entries ?? []).map((entry) => <article className="history-row" key={entry.id}><span>{new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(entry.measured_at))}</span><strong>{entry.weight_kg.toFixed(1)} kg</strong></article>)}
    </section>
  </section>
}
