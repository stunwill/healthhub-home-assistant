import { useEffect, useState } from 'react'

type WeightEntry = {
  id: string
  weight_kg: number
  measured_at: string
}

type ProgressSummary = {
  exercise_minutes: number
  exercise_minutes_target: number
  exercise_calories: number
  latest_weight_kg?: number | null
  latest_weight_at?: string | null
  starting_weight_kg?: number | null
  goal_weight_kg?: number | null
  change_from_start_kg?: number | null
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
  const [exerciseName, setExerciseName] = useState('')
  const [exerciseMinutes, setExerciseMinutes] = useState('')
  const [exerciseCalories, setExerciseCalories] = useState('')
  const [exerciseAt, setExerciseAt] = useState(localDateTimeInput())
  const [weight, setWeight] = useState('')
  const [weightAt, setWeightAt] = useState(localDateTimeInput())
  const [saving, setSaving] = useState(false)

  async function loadProgress() {
    const response = await fetch(`${API}/profiles/${profileId}/progress?days=90`)
    if (!response.ok) {
      onNotice('Could not load progress')
      return
    }
    setProgress((await response.json()) as ProgressSummary)
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
        body: JSON.stringify({
          activity_name: exerciseName.trim(),
          duration_minutes: minutes,
          calories_burned: calories,
          completed_at: isoFromLocalInput(exerciseAt),
        }),
      })
      if (!response.ok) throw new Error('Could not save exercise')
      setExerciseName('')
      setExerciseMinutes('')
      setExerciseCalories('')
      onNotice('Exercise logged')
      await Promise.all([loadProgress(), onActivityChanged()])
    } catch (error) {
      onNotice(error instanceof Error ? error.message : 'Could not save exercise')
    } finally {
      setSaving(false)
    }
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
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weight_kg: value, measured_at: isoFromLocalInput(weightAt) }),
      })
      if (!response.ok) throw new Error('Could not save weight')
      setWeight('')
      onNotice('Weight logged')
      await loadProgress()
    } catch (error) {
      onNotice(error instanceof Error ? error.message : 'Could not save weight')
    } finally {
      setSaving(false)
    }
  }

  const target = progress?.exercise_minutes_target ?? 0
  const exercisePercent = target > 0 ? Math.min(100, Math.round(((progress?.exercise_minutes ?? 0) / target) * 100)) : 0

  return <section>
    <div className="page-heading"><div><p className="eyebrow">Progress</p><h1>Activity & weight</h1></div></div>

    <div className="progress-grid">
      <article className="target-card"><span>Exercise, last 90 days</span><strong>{progress?.exercise_minutes ?? 0} min</strong><small>{target} min weekly target · {exercisePercent}% of one weekly target</small></article>
      <article className="target-card"><span>Exercise calories</span><strong>{progress?.exercise_calories ?? 0} kcal</strong><small>Completed activity, before calorie-credit settings</small></article>
      <article className="target-card"><span>Latest weight</span><strong>{progress?.latest_weight_kg == null ? 'Not logged' : `${progress.latest_weight_kg.toFixed(1)} kg`}</strong><small>{progress?.change_from_start_kg == null ? 'No starting comparison' : `${progress.change_from_start_kg > 0 ? '+' : ''}${progress.change_from_start_kg.toFixed(1)} kg from start`}</small></article>
      <article className="target-card"><span>Goal weight</span><strong>{progress?.goal_weight_kg == null ? 'Not set' : `${progress.goal_weight_kg.toFixed(1)} kg`}</strong><small>HealthHub does not prescribe a target</small></article>
    </div>

    <div className="progress-forms">
      <section className="planner-card">
        <h2>Log exercise</h2>
        <label>Activity<input value={exerciseName} onChange={(event) => setExerciseName(event.target.value)} placeholder="e.g. Walk, gym, cycling" /></label>
        <div className="inline-fields">
          <label>Minutes<input inputMode="numeric" value={exerciseMinutes} onChange={(event) => setExerciseMinutes(event.target.value)} /></label>
          <label>Calories burned<input inputMode="decimal" value={exerciseCalories} onChange={(event) => setExerciseCalories(event.target.value)} /></label>
        </div>
        <label>Completed<input type="datetime-local" value={exerciseAt} onChange={(event) => setExerciseAt(event.target.value)} /></label>
        <button className="quick-add" disabled={saving} onClick={() => void saveExercise()}>Save exercise</button>
        <p className="muted">Enter calories from a trusted device or source. HealthHub does not estimate exercise calories in v0.3.0.</p>
      </section>

      <section className="planner-card">
        <h2>Log weight</h2>
        <label>Weight (kg)<input inputMode="decimal" value={weight} onChange={(event) => setWeight(event.target.value)} /></label>
        <label>Measured<input type="datetime-local" value={weightAt} onChange={(event) => setWeightAt(event.target.value)} /></label>
        <button className="quick-add" disabled={saving} onClick={() => void saveWeight()}>Save weight</button>
      </section>
    </div>

    <section className="weight-history">
      <div className="section-heading"><h2>Weight history</h2><span>Last 90 days</span></div>
      {(progress?.weight_entries ?? []).length === 0 ? <article className="empty-card"><p>No weight entries yet.</p></article> : (progress?.weight_entries ?? []).map((entry) =>
        <article className="history-row" key={entry.id}><span>{new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(entry.measured_at))}</span><strong>{entry.weight_kg.toFixed(1)} kg</strong></article>)}
    </section>
  </section>
}
