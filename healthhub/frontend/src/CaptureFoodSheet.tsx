import { useEffect, useMemo, useRef, useState } from 'react'

const API = './api/v1'

type MealPeriod = 'breakfast' | 'morning_snack' | 'lunch' | 'afternoon_snack' | 'dinner' | 'evening_snack' | 'snack' | 'drink'
type CaptureMode = 'eaten' | 'planned'
type CaptureImage = { upload_id: string; filename: string; content_type: string; confidence: string }
type CaptureResult = {
  capture_id: string
  images: CaptureImage[]
  extraction: Record<string, unknown>
  field_confidence: Record<string, string>
  warnings: string[]
}
type Draft = {
  name: string
  brand: string
  barcode: string
  serving_name: string
  serving_quantity: string
  serving_unit: string
  nutrition_basis: string
  energy_kj: string
  calories: string
  protein_g: string
  carbohydrates_g: string
  fat_g: string
  saturated_fat_g: string
  sugar_g: string
  fibre_g: string
  sodium_mg: string
}

const emptyDraft: Draft = {
  name: '', brand: '', barcode: '', serving_name: '1 serve', serving_quantity: '', serving_unit: 'serving', nutrition_basis: 'per_serving',
  energy_kj: '', calories: '', protein_g: '', carbohydrates_g: '', fat_g: '', saturated_fat_g: '', sugar_g: '', fibre_g: '', sodium_mg: '',
}

const asInput = (value: unknown) => value == null ? '' : String(value)
const numeric = (value: string) => value.trim() === '' ? null : Number(value)

export default function CaptureFoodSheet({
  profileId,
  day,
  mealPeriod,
  mode,
  servings,
  onClose,
  onSaved,
  onNotice,
}: {
  profileId: string
  day: string
  mealPeriod: MealPeriod
  mode: CaptureMode
  servings: number
  onClose: () => void
  onSaved: () => Promise<void>
  onNotice: (message: string) => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [result, setResult] = useState<CaptureResult | null>(null)
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [stage, setStage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const cameraRef = useRef<HTMLInputElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)
  const previews = useMemo(() => files.map((file) => ({ file, url: URL.createObjectURL(file) })), [files])

  useEffect(() => () => previews.forEach((preview) => URL.revokeObjectURL(preview.url)), [previews])

  function appendFiles(items: FileList | null) {
    if (!items) return
    setFiles((current) => [...current, ...Array.from(items)].slice(0, 8))
    setResult(null)
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setResult(null)
  }

  async function processImages() {
    if (files.length === 0) return
    setStage('Uploading image…')
    try {
      const form = new FormData()
      files.forEach((file) => form.append('images', file))
      setStage(files.length > 1 ? 'Reading nutrition labels…' : 'Reading nutrition label…')
      const response = await fetch(`${API}/capture/nutrition-labels`, { method: 'POST', body: form })
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Image capture failed')
      const capture = data as CaptureResult
      setResult(capture)
      const servingQuantity = asInput(capture.extraction.serving_size)
      const servingUnit = asInput(capture.extraction.serving_unit) || 'serving'
      setDraft({
        ...emptyDraft,
        serving_name: servingQuantity ? `${servingQuantity} ${servingUnit}` : '1 serve',
        serving_quantity: servingQuantity,
        serving_unit: servingUnit,
        nutrition_basis: asInput(capture.extraction.nutrition_basis) || 'per_serving',
        energy_kj: asInput(capture.extraction.energy_kj),
        calories: asInput(capture.extraction.calories),
        protein_g: asInput(capture.extraction.protein_g),
        carbohydrates_g: asInput(capture.extraction.carbohydrates_g),
        fat_g: asInput(capture.extraction.fat_g),
        saturated_fat_g: asInput(capture.extraction.saturated_fat_g),
        sugar_g: asInput(capture.extraction.sugar_g),
        fibre_g: asInput(capture.extraction.fibre_g),
        sodium_mg: asInput(capture.extraction.sodium_mg),
      })
      onNotice('OCR complete. Review and correct the extracted values before saving.')
    } catch (error) {
      onNotice(error instanceof Error ? error.message : 'Image capture failed')
    } finally {
      setStage(null)
    }
  }

  async function saveAndAdd() {
    if (!result || !result.images[0] || !draft.name.trim() || draft.calories.trim() === '') {
      onNotice('Product name and calories are required before saving.')
      return
    }
    setSaving(true)
    setStage(`Saving & adding to ${mealPeriod.replaceAll('_', ' ')}…`)
    try {
      const payload = {
        upload_id: result.images[0].upload_id,
        name: draft.name.trim(),
        brand: draft.brand.trim() || null,
        barcode: draft.barcode.trim() || null,
        kind: 'food',
        serving_name: draft.serving_name.trim() || '1 serve',
        serving_quantity: numeric(draft.serving_quantity),
        serving_unit: draft.serving_unit.trim() || 'serving',
        serving_grams: draft.serving_unit.toLowerCase() === 'g' ? numeric(draft.serving_quantity) : null,
        nutrition_basis: draft.nutrition_basis,
        energy_kj: numeric(draft.energy_kj),
        calories: Number(draft.calories),
        protein_g: numeric(draft.protein_g),
        carbohydrates_g: numeric(draft.carbohydrates_g),
        fat_g: numeric(draft.fat_g),
        saturated_fat_g: numeric(draft.saturated_fat_g),
        sugar_g: numeric(draft.sugar_g),
        fibre_g: numeric(draft.fibre_g),
        sodium_mg: numeric(draft.sodium_mg),
        reviewed: true,
      }
      const params = new URLSearchParams({ profile_id: profileId, day, meal_period: mealPeriod, mode, servings: String(servings) })
      result.images.slice(1).forEach((image) => params.append('upload_ids', image.upload_id))
      const response = await fetch(`${API}/capture/nutrition-label/review-and-add?${params.toString()}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Could not save captured food')
      await onSaved()
      onNotice(`${data.name} saved and added to ${mealPeriod.replaceAll('_', ' ')}.`)
      onClose()
    } catch (error) {
      onNotice(error instanceof Error ? error.message : 'Could not save captured food')
    } finally {
      setSaving(false)
      setStage(null)
    }
  }

  const update = (field: keyof Draft, value: string) => setDraft((current) => ({ ...current, [field]: value }))

  return <div className="capture-flow">
    <div className="capture-actions">
      <button type="button" onClick={() => cameraRef.current?.click()}>Take Photo</button>
      <button type="button" onClick={() => uploadRef.current?.click()}>Upload Photo(s)</button>
      <input ref={cameraRef} className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(event) => appendFiles(event.target.files)} />
      <input ref={uploadRef} className="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => appendFiles(event.target.files)} />
    </div>
    <p className="muted">Use the front of the pack, nutrition panel, serving details and barcode image as needed. Up to 8 photos belong to one capture.</p>
    {previews.length > 0 && <div className="capture-previews">{previews.map(({ file, url }, index) => <article key={`${file.name}-${index}`}><img src={url} alt={file.name} /><div><small>{file.name}</small><button type="button" onClick={() => removeFile(index)}>Remove</button></div></article>)}</div>}
    {files.length > 0 && !result && <div className="capture-footer"><button type="button" onClick={() => setFiles([])}>Clear all</button><button className="quick-add" type="button" disabled={stage != null} onClick={() => void processImages()}>{stage ?? `Process ${files.length} photo${files.length === 1 ? '' : 's'}`}</button></div>}
    {stage && <p className="capture-progress" role="status">{stage}</p>}
    {result && <div className="capture-review">
      <h3>Verify captured food</h3>
      <p className="muted">{result.images.length} image{result.images.length === 1 ? '' : 's'} processed locally.</p>
      {result.warnings.length > 0 && <div className="notice">{result.warnings.join(' · ')}</div>}
      <div className="food-form">
        <label>Product name<input value={draft.name} onChange={(e) => update('name', e.target.value)} /></label>
        <label>Brand<input value={draft.brand} onChange={(e) => update('brand', e.target.value)} /></label>
        <label>Barcode<input inputMode="numeric" value={draft.barcode} onChange={(e) => update('barcode', e.target.value)} /></label>
        <label>Serving name<input value={draft.serving_name} onChange={(e) => update('serving_name', e.target.value)} /></label>
        <label>Serving quantity<input inputMode="decimal" value={draft.serving_quantity} onChange={(e) => update('serving_quantity', e.target.value)} /></label>
        <label>Serving unit<input value={draft.serving_unit} onChange={(e) => update('serving_unit', e.target.value)} /></label>
        <label>Nutrition basis<select value={draft.nutrition_basis} onChange={(e) => update('nutrition_basis', e.target.value)}><option value="per_serving">Per serving</option><option value="per_100g">Per 100 g</option><option value="per_100ml">Per 100 mL</option></select></label>
        {(['energy_kj','calories','protein_g','carbohydrates_g','fat_g','saturated_fat_g','sugar_g','fibre_g','sodium_mg'] as Array<keyof Draft>).map((field) => <label key={field}>{field.replaceAll('_', ' ')}<input inputMode="decimal" value={draft[field]} onChange={(e) => update(field, e.target.value)} /><small>{result.field_confidence[field] ? `OCR: ${result.field_confidence[field]}` : 'OCR: unknown'}</small></label>)}
      </div>
      <button className="quick-add" type="button" disabled={saving} onClick={() => void saveAndAdd()}>{saving ? 'Saving…' : `Save & Add to ${mealPeriod.replaceAll('_', ' ')}`}</button>
    </div>}
  </div>
}
