import { useRef, useState } from 'react'

const API = './api/v1'

type MealPeriod = 'breakfast' | 'morning_snack' | 'lunch' | 'afternoon_snack' | 'dinner' | 'evening_snack' | 'snack' | 'drink'
type CaptureMode = 'eaten' | 'planned'
type SavedFood = { id: string; name: string }
type Candidate = { provider: string; provider_id?: string | null; name: string; brand?: string | null; barcode?: string | null; serving_size?: number | null; serving_unit?: string | null; nutrition_basis?: string | null; energy_kj?: number | null; calories?: number | null; protein_g?: number | null; carbohydrates_g?: number | null; fat_g?: number | null; saturated_fat_g?: number | null; sugar_g?: number | null; fibre_g?: number | null; sodium_mg?: number | null; source_url?: string | null; confidence: string; completeness: string }
type BarcodeDetectorInstance = { detect: (source: HTMLVideoElement) => Promise<Array<{ rawValue: string }>> }
type BarcodeDetectorCtor = new (options?: { formats?: string[] }) => BarcodeDetectorInstance

export default function QuickBarcodeCapture({ profileId, day, mealPeriod, mode, servings, onSaved, onPhotoFallback, onNotice }: { profileId: string; day: string; mealPeriod: MealPeriod; mode: CaptureMode; servings: number; onSaved: () => Promise<void>; onPhotoFallback: () => void; onNotice: (message: string) => void }) {
  const [barcode, setBarcode] = useState('')
  const [busy, setBusy] = useState(false)
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [scanning, setScanning] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | null>(null)

  function stopCamera() { if (timerRef.current != null) window.clearInterval(timerRef.current); timerRef.current = null; streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null; if (videoRef.current) videoRef.current.srcObject = null; setScanning(false) }

  async function addFood(food: SavedFood) {
    const when = new Date(`${day}T12:00:00`).toISOString()
    const endpoint = mode === 'planned' ? `${API}/profiles/${profileId}/planned` : `${API}/profiles/${profileId}/diary`
    const body = mode === 'planned' ? { food_id: food.id, meal_period: mealPeriod, planned_for: when, servings } : { food_id: food.id, meal_period: mealPeriod, consumed_at: when, servings }
    const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    if (!response.ok) throw new Error('Food was found but could not be added to the selected meal')
    await onSaved(); onNotice(`${food.name} added to ${mealPeriod.replaceAll('_', ' ')}.`)
  }

  async function lookup(raw: string) {
    const value = raw.replace(/\D/g, '')
    if (!value) return
    setBarcode(value); setBusy(true); setCandidate(null)
    try {
      const response = await fetch(`${API}/products/barcode/${value}`); const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Barcode lookup failed')
      if (data.status === 'local') await addFood({ id: data.food.id, name: data.food.name })
      else if (data.status === 'external') setCandidate(data.candidate as Candidate)
      else { onNotice('Barcode was not found. Use photos to capture the package and nutrition panel.'); onPhotoFallback() }
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Barcode lookup failed') }
    finally { setBusy(false) }
  }

  async function startCamera() {
    const Detector = (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector
    if (!Detector || !navigator.mediaDevices?.getUserMedia) { onNotice('Live barcode scanning is unavailable in this browser. Enter the barcode manually or use photo capture.'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false }); streamRef.current = stream; setScanning(true)
      await new Promise<void>((resolve) => window.setTimeout(resolve, 0)); if (!videoRef.current) return; videoRef.current.srcObject = stream; await videoRef.current.play()
      const detector = new Detector({ formats: ['ean_8', 'ean_13', 'upc_a', 'upc_e'] })
      timerRef.current = window.setInterval(() => { const video = videoRef.current; if (!video || video.readyState < 2) return; void detector.detect(video).then((codes) => { const found = codes[0]?.rawValue; if (found) { stopCamera(); void lookup(found) } }).catch(() => undefined) }, 350)
    } catch { stopCamera(); onNotice('Camera access was unavailable. Enter the barcode manually or use Upload Photo(s).') }
  }

  async function saveCandidate() {
    if (!candidate?.name.trim()) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/products/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...candidate, reviewed: true }) }); const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Could not save product')
      await addFood(data as SavedFood); setCandidate(null)
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not save product') }
    finally { setBusy(false) }
  }

  return <div className="barcode-capture"><div className="capture-actions"><button disabled={busy} onClick={() => scanning ? stopCamera() : void startCamera()}>{scanning ? 'Stop Camera' : 'Scan Barcode'}</button><button onClick={onPhotoFallback}>Use Photo(s)</button></div>{scanning && <video ref={videoRef} playsInline muted className="barcode-video" />}<label>Barcode<input inputMode="numeric" value={barcode} placeholder="EAN / UPC" onChange={(e) => setBarcode(e.target.value)} /></label><button className="quick-add" disabled={busy || !barcode.trim()} onClick={() => void lookup(barcode)}>{busy ? 'Checking…' : 'Look Up Barcode'}</button>{candidate && <div className="capture-review"><h3>Review product</h3><p className="muted">{candidate.brand || 'Unknown brand'} · {candidate.provider} · {candidate.confidence} confidence</p><p><strong>{candidate.name}</strong>{candidate.calories != null ? ` · ${Math.round(candidate.calories)} kcal` : ''}</p><button className="quick-add" disabled={busy} onClick={() => void saveCandidate()}>Confirm & Add to {mealPeriod.replaceAll('_', ' ')}</button></div>}</div>
}
