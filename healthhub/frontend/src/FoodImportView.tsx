import { useEffect, useRef, useState } from 'react'

const API = './api/v1'

type Preview = { total_rows: number; valid_rows: number; warning_rows: number; invalid_rows: number; duplicate_rows: number; rows: Record<string, unknown>[]; source_type?: string | null; source_name?: string | null; sheet_names?: string[]; selected_sheet?: string | null }
type Candidate = { provider: string; provider_id?: string | null; name: string; brand?: string | null; barcode?: string | null; package_size?: string | null; serving_size?: number | null; serving_unit?: string | null; nutrition_basis?: string | null; energy_kj?: number | null; calories?: number | null; protein_g?: number | null; carbohydrates_g?: number | null; fat_g?: number | null; saturated_fat_g?: number | null; sugar_g?: number | null; fibre_g?: number | null; sodium_mg?: number | null; source_url?: string | null; confidence: string; completeness: string; image_url?: string | null }
type OcrResult = { upload_id: string; extraction: Record<string, unknown>; confidence: string; field_confidence: Record<string, string>; warnings: string[] }
type SavedFood = { id: string; name: string }
type BarcodeDetectorInstance = { detect: (source: HTMLVideoElement) => Promise<Array<{ rawValue: string }>> }
type BarcodeDetectorCtor = new (options?: { formats?: string[] }) => BarcodeDetectorInstance

type OcrDraft = {
  name: string; brand: string; barcode: string; serving_name: string; serving_quantity: string; serving_unit: string; nutrition_basis: string;
  energy_kj: string; calories: string; protein_g: string; carbohydrates_g: string; fat_g: string; saturated_fat_g: string;
  sugar_g: string; fibre_g: string; sodium_mg: string; calcium_mg: string; iron_mg: string; potassium_mg: string;
  cholesterol_mg: string; alcohol_g: string; caffeine_mg: string
}

const emptyOcrDraft: OcrDraft = { name: '', brand: '', barcode: '', serving_name: '1 serve', serving_quantity: '', serving_unit: 'serving', nutrition_basis: 'per_serving', energy_kj: '', calories: '', protein_g: '', carbohydrates_g: '', fat_g: '', saturated_fat_g: '', sugar_g: '', fibre_g: '', sodium_mg: '', calcium_mg: '', iron_mg: '', potassium_mg: '', cholesterol_mg: '', alcohol_g: '', caffeine_mg: '' }
const numeric = (value: string) => value.trim() === '' ? null : Number(value)
const asInput = (value: unknown) => value == null ? '' : String(value)

export default function FoodImportView({ onNotice }: { onNotice: (message: string) => void }) {
  const [text, setText] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [source, setSource] = useState<'spreadsheet' | 'csv' | 'xlsx'>('spreadsheet')
  const [sourceName, setSourceName] = useState<string | null>(null)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [barcode, setBarcode] = useState('')
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [productSearch, setProductSearch] = useState('')
  const [products, setProducts] = useState<Candidate[]>([])
  const [ocr, setOcr] = useState<OcrResult | null>(null)
  const [ocrDraft, setOcrDraft] = useState<OcrDraft>(emptyOcrDraft)
  const [savedFood, setSavedFood] = useState<SavedFood | null>(null)
  const [scanning, setScanning] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const scanTimerRef = useRef<number | null>(null)

  useEffect(() => () => stopBarcodeCamera(), [])

  function stopBarcodeCamera() {
    if (scanTimerRef.current != null) window.clearInterval(scanTimerRef.current)
    scanTimerRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setScanning(false)
  }

  async function copyTemplate() {
    const response = await fetch(`${API}/foods/import/template`)
    const payload = await response.json() as { template: string }
    await navigator.clipboard.writeText(payload.template)
    setText(payload.template + '\n')
    onNotice('Import template copied.')
  }

  async function previewPaste() {
    setBusy(true)
    try {
      const response = await fetch(`${API}/foods/import/preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tsv: text }) })
      if (!response.ok) throw new Error('Could not preview spreadsheet')
      setSource('spreadsheet'); setSourceName(null); setUploadedFile(null); setPreview(await response.json())
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not preview spreadsheet') }
    finally { setBusy(false) }
  }

  async function previewFile(file: File, sheet?: string) {
    setBusy(true)
    try {
      const form = new FormData(); form.append('file', file); if (sheet) form.append('sheet', sheet)
      const response = await fetch(`${API}/foods/import/file`, { method: 'POST', body: form })
      if (!response.ok) { const data = await response.json().catch(() => null); throw new Error(data?.detail ?? 'Could not preview file') }
      const data = await response.json() as Preview
      setUploadedFile(file); setSource(file.name.toLowerCase().endsWith('.xlsx') ? 'xlsx' : 'csv'); setSourceName(file.name); setPreview(data)
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not preview file') }
    finally { setBusy(false) }
  }

  async function commitImport() {
    if (!preview) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/foods/import/commit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rows: preview.rows, duplicate_action: 'skip', source, source_name: sourceName }) })
      if (!response.ok) throw new Error('Could not import foods')
      const result = await response.json() as { created: number; updated: number; skipped: number; rejected: number }
      onNotice(`Import complete: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped, ${result.rejected} rejected.`)
      setPreview(null); setText(''); setUploadedFile(null)
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not import foods') }
    finally { setBusy(false) }
  }

  async function performBarcodeLookup(raw: string) {
    const value = raw.replace(/\D/g, '')
    if (!value) return
    setBarcode(value); setBusy(true); setSavedFood(null)
    try {
      const response = await fetch(`${API}/products/barcode/${value}`)
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Barcode lookup failed')
      if (data.status === 'local') { onNotice(`${data.food.name} is already in HealthHub.`); setCandidate(null); setSavedFood({ id: data.food.id, name: data.food.name }) }
      else if (data.status === 'external') setCandidate(data.candidate)
      else { setCandidate({ provider: 'manual', name: '', barcode: value, confidence: 'unknown', completeness: 'partial' }); onNotice('Barcode not found. Add product details or use a nutrition-label photo.') }
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Barcode lookup failed') }
    finally { setBusy(false) }
  }

  async function startBarcodeCamera() {
    const Detector = (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector
    if (!Detector || !navigator.mediaDevices?.getUserMedia) { onNotice('Live barcode scanning is not supported by this browser. Enter the barcode manually.'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
      streamRef.current = stream; setScanning(true)
      await new Promise<void>((resolve) => window.setTimeout(resolve, 0))
      if (!videoRef.current) return
      videoRef.current.srcObject = stream; await videoRef.current.play()
      const detector = new Detector({ formats: ['ean_8', 'ean_13', 'upc_a', 'upc_e'] })
      scanTimerRef.current = window.setInterval(() => {
        const video = videoRef.current
        if (!video || video.readyState < 2) return
        void detector.detect(video).then((codes) => {
          const found = codes[0]?.rawValue
          if (found) { stopBarcodeCamera(); void performBarcodeLookup(found) }
        }).catch(() => undefined)
      }, 350)
    } catch { stopBarcodeCamera(); onNotice('Camera access was unavailable. Enter the barcode manually instead.') }
  }

  async function searchProducts() {
    if (productSearch.trim().length < 2) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/products/search?q=${encodeURIComponent(productSearch.trim())}`)
      if (!response.ok) throw new Error('Product search failed')
      setProducts(await response.json())
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Product search failed') }
    finally { setBusy(false) }
  }

  async function saveCandidate(item: Candidate) {
    if (!item.name.trim()) { onNotice('Product name is required before saving.'); return }
    const response = await fetch(`${API}/products/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...item, reviewed: true }) })
    if (!response.ok) { const data = await response.json().catch(() => null); onNotice(typeof data?.detail === 'string' ? data.detail : 'Could not save product'); return }
    const saved = await response.json() as SavedFood; onNotice(`${saved.name} saved to the Food Library.`); setSavedFood(saved); setCandidate(null)
  }

  async function addSavedToDiary() {
    if (!savedFood) return
    const activeResponse = await fetch(`${API}/active-profile`)
    const active = activeResponse.ok ? await activeResponse.json() as { profile_id?: string } : null
    if (!active?.profile_id) { onNotice('Select a HealthHub profile before adding this food to the diary.'); return }
    const response = await fetch(`${API}/profiles/${active.profile_id}/diary`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ food_id: savedFood.id, meal_period: 'snack', consumed_at: new Date().toISOString(), servings: 1 }) })
    onNotice(response.ok ? `${savedFood.name} added to today’s diary.` : 'The food was saved, but could not be added to the diary.')
  }

  async function scanLabel(file: File) {
    setBusy(true); setSavedFood(null)
    try {
      const form = new FormData(); form.append('image', file)
      const response = await fetch(`${API}/capture/nutrition-label`, { method: 'POST', body: form })
      const data = await response.json()
      if (!response.ok) throw new Error(data?.detail ?? 'Nutrition label OCR failed')
      const result = data as OcrResult; setOcr(result)
      const servingQuantity = asInput(result.extraction.serving_size)
      const servingUnit = asInput(result.extraction.serving_unit) || 'serving'
      setOcrDraft({ ...emptyOcrDraft, serving_name: servingQuantity ? `${servingQuantity} ${servingUnit}` : '1 serve', serving_quantity: servingQuantity, serving_unit: servingUnit, nutrition_basis: asInput(result.extraction.nutrition_basis) || 'per_serving', energy_kj: asInput(result.extraction.energy_kj), calories: asInput(result.extraction.calories), protein_g: asInput(result.extraction.protein_g), carbohydrates_g: asInput(result.extraction.carbohydrates_g), fat_g: asInput(result.extraction.fat_g), saturated_fat_g: asInput(result.extraction.saturated_fat_g), sugar_g: asInput(result.extraction.sugar_g), fibre_g: asInput(result.extraction.fibre_g), sodium_mg: asInput(result.extraction.sodium_mg), calcium_mg: asInput(result.extraction.calcium_mg), iron_mg: asInput(result.extraction.iron_mg), potassium_mg: asInput(result.extraction.potassium_mg), cholesterol_mg: asInput(result.extraction.cholesterol_mg), alcohol_g: asInput(result.extraction.alcohol_g), caffeine_mg: asInput(result.extraction.caffeine_mg) })
      onNotice('Local OCR complete. Review and correct every value against the label image before saving.')
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Nutrition label OCR failed') }
    finally { setBusy(false) }
  }

  async function saveOcrReview() {
    if (!ocr || !ocrDraft.name.trim() || ocrDraft.calories.trim() === '') { onNotice('Product name and calories are required before saving the reviewed label.'); return }
    const payload = { upload_id: ocr.upload_id, name: ocrDraft.name.trim(), brand: ocrDraft.brand.trim() || null, kind: 'food', serving_name: ocrDraft.serving_name.trim() || '1 serve', serving_quantity: numeric(ocrDraft.serving_quantity), serving_unit: ocrDraft.serving_unit.trim() || 'serving', serving_grams: ocrDraft.serving_unit.toLowerCase() === 'g' ? numeric(ocrDraft.serving_quantity) : null, nutrition_basis: ocrDraft.nutrition_basis, energy_kj: numeric(ocrDraft.energy_kj), calories: Number(ocrDraft.calories), protein_g: numeric(ocrDraft.protein_g), carbohydrates_g: numeric(ocrDraft.carbohydrates_g), fat_g: numeric(ocrDraft.fat_g), saturated_fat_g: numeric(ocrDraft.saturated_fat_g), sugar_g: numeric(ocrDraft.sugar_g), fibre_g: numeric(ocrDraft.fibre_g), sodium_mg: numeric(ocrDraft.sodium_mg), calcium_mg: numeric(ocrDraft.calcium_mg), iron_mg: numeric(ocrDraft.iron_mg), potassium_mg: numeric(ocrDraft.potassium_mg), cholesterol_mg: numeric(ocrDraft.cholesterol_mg), alcohol_g: numeric(ocrDraft.alcohol_g), caffeine_mg: numeric(ocrDraft.caffeine_mg), barcode: ocrDraft.barcode.trim() || null, reviewed: true }
    const response = await fetch(`${API}/capture/nutrition-label/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    const data = await response.json().catch(() => null)
    if (!response.ok) { onNotice(typeof data?.detail === 'string' ? data.detail : 'Could not save reviewed nutrition label'); return }
    setSavedFood(data as SavedFood); setOcr(null); setOcrDraft(emptyOcrDraft); onNotice(`${data.name} saved as packaging label, user verified.`)
  }

  const updateCandidate = (field: keyof Candidate, value: string) => setCandidate((current) => current ? { ...current, [field]: ['calories', 'energy_kj', 'serving_size', 'protein_g', 'carbohydrates_g', 'fat_g', 'saturated_fat_g', 'sugar_g', 'fibre_g', 'sodium_mg'].includes(field) ? (value === '' ? null : Number(value)) : value } : current)
  const updateOcr = (field: keyof OcrDraft, value: string) => setOcrDraft((current) => ({ ...current, [field]: value }))

  return <section>
    <p className="eyebrow">Foods</p><h1>Import & capture foods</h1><p>All methods feed the same HealthHub Food Library and require preview or human review before saving.</p>

    <div className="planner-card"><h2>Spreadsheet and file import</h2><div className="secondary-actions"><button className="quick-add" onClick={() => void copyTemplate()}>Copy template</button><a className="quick-add" href={`${API}/foods/import/template.csv`}>Download CSV</a><a className="quick-add" href={`${API}/foods/import/template.xlsx`}>Download XLSX</a></div><p className="muted">Required: name. Nutrition may be per serving, per 100 g or per 100 mL. Values are validated before import.</p><textarea aria-label="Paste spreadsheet data" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste spreadsheet cells here…" rows={7} /><div className="secondary-actions"><button disabled={!text.trim() || busy} onClick={() => void previewPaste()}>Preview pasted data</button><label className="upload-action">Upload CSV/XLSX<input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => { const file = event.target.files?.[0]; if (file) void previewFile(file) }} /></label></div></div>

    {preview && <section className="planner-card import-preview"><h2>Import preview</h2>{source === 'xlsx' && uploadedFile && (preview.sheet_names?.length ?? 0) > 1 && <label>Worksheet<select value={preview.selected_sheet ?? ''} onChange={(event) => void previewFile(uploadedFile, event.target.value)}>{preview.sheet_names?.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>}<p>{preview.total_rows} rows, {preview.valid_rows} valid, {preview.warning_rows} warnings, {preview.invalid_rows} invalid, {preview.duplicate_rows} potential duplicates.</p><div className="table-scroll"><table><thead><tr><th>Name</th><th>Basis</th><th>Calories</th><th>Status</th></tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}><td>{String(row.name ?? '')}</td><td>{String(row.nutrition_basis ?? 'per_serving')}</td><td>{String(row.calories ?? '')}</td><td>{row._valid ? (row._duplicate ? 'Potential duplicate' : String((row._warnings as string[] | undefined)?.join(', ') || 'Ready')) : String((row._errors as string[] | undefined)?.join(', '))}</td></tr>)}</tbody></table></div><button className="quick-add" disabled={busy || preview.valid_rows === 0} onClick={() => void commitImport()}>Import valid rows</button></section>}

    <div className="planner-card"><h2>Scan or enter barcode</h2><p>HealthHub checks the local library first, then the configured external provider. Manual entry remains available if camera scanning is unsupported.</p><div className="secondary-actions"><button onClick={() => scanning ? stopBarcodeCamera() : void startBarcodeCamera()}>{scanning ? 'Stop camera' : 'Scan barcode'}</button><input inputMode="numeric" aria-label="Barcode" placeholder="EAN / GTIN barcode" value={barcode} onChange={(event) => setBarcode(event.target.value)} /><button disabled={busy || !barcode.trim()} onClick={() => void performBarcodeLookup(barcode)}>Look up barcode</button></div>{scanning && <video ref={videoRef} playsInline muted style={{ width: '100%', maxHeight: 320, objectFit: 'cover', marginTop: 12 }} />}</div>

    {candidate && <div className="planner-card"><h3>Review product</h3><p className="muted">Provider: {candidate.provider}. Confidence: {candidate.confidence}. Nutrition: {candidate.completeness}. Correct any value before saving.</p><div className="food-form"><label>Name<input value={candidate.name} onChange={(e) => updateCandidate('name', e.target.value)} /></label><label>Brand<input value={candidate.brand ?? ''} onChange={(e) => updateCandidate('brand', e.target.value)} /></label><label>Barcode<input inputMode="numeric" value={candidate.barcode ?? ''} onChange={(e) => updateCandidate('barcode', e.target.value)} /></label><label>Package size<input value={candidate.package_size ?? ''} onChange={(e) => updateCandidate('package_size', e.target.value)} /></label><label>Serving quantity<input inputMode="decimal" value={candidate.serving_size ?? ''} onChange={(e) => updateCandidate('serving_size', e.target.value)} /></label><label>Serving unit<input value={candidate.serving_unit ?? ''} onChange={(e) => updateCandidate('serving_unit', e.target.value)} /></label><label>Nutrition basis<select value={candidate.nutrition_basis ?? 'per_100g'} onChange={(e) => updateCandidate('nutrition_basis', e.target.value)}><option value="per_serving">Per serving</option><option value="per_100g">Per 100 g</option><option value="per_100ml">Per 100 mL</option></select></label><label>Calories<input inputMode="decimal" value={candidate.calories ?? ''} onChange={(e) => updateCandidate('calories', e.target.value)} /></label><label>Protein (g)<input inputMode="decimal" value={candidate.protein_g ?? ''} onChange={(e) => updateCandidate('protein_g', e.target.value)} /></label><label>Carbohydrates (g)<input inputMode="decimal" value={candidate.carbohydrates_g ?? ''} onChange={(e) => updateCandidate('carbohydrates_g', e.target.value)} /></label><label>Fat (g)<input inputMode="decimal" value={candidate.fat_g ?? ''} onChange={(e) => updateCandidate('fat_g', e.target.value)} /></label><label>Saturated fat (g)<input inputMode="decimal" value={candidate.saturated_fat_g ?? ''} onChange={(e) => updateCandidate('saturated_fat_g', e.target.value)} /></label><label>Sugars (g)<input inputMode="decimal" value={candidate.sugar_g ?? ''} onChange={(e) => updateCandidate('sugar_g', e.target.value)} /></label><label>Fibre (g)<input inputMode="decimal" value={candidate.fibre_g ?? ''} onChange={(e) => updateCandidate('fibre_g', e.target.value)} /></label><label>Sodium (mg)<input inputMode="decimal" value={candidate.sodium_mg ?? ''} onChange={(e) => updateCandidate('sodium_mg', e.target.value)} /></label></div><button className="quick-add" onClick={() => void saveCandidate(candidate)}>Confirm review & save</button></div>}

    <div className="planner-card"><h2>Search product database</h2><div className="secondary-actions"><input placeholder="Product name, brand or barcode" value={productSearch} onChange={(event) => setProductSearch(event.target.value)} /><button disabled={busy || productSearch.trim().length < 2} onClick={() => void searchProducts()}>Search products</button></div>{products.map((item) => <button className="search-result" key={`${item.provider}-${item.provider_id}-${item.name}`} onClick={() => setCandidate(item)}><span><strong>{item.name}</strong><small>{item.brand || 'Unknown brand'} · {item.provider}</small></span><b>{item.calories == null ? 'Nutrition partial' : `${Math.round(item.calories)} kcal`}</b></button>)}</div>

    <div className="planner-card"><h2>Photograph nutrition label</h2><p>Use a clear Australian Nutrition Information Panel photo. OCR runs locally inside the HealthHub add-on and the image is not sent to a third-party OCR service.</p><label className="upload-action">Take photo or upload label<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(event) => { const file = event.target.files?.[0]; if (file) void scanLabel(file) }} /></label></div>

    {ocr && <div className="planner-card"><h3>OCR review</h3><img style={{ maxWidth: '100%', maxHeight: 320, objectFit: 'contain' }} src={`${API}/capture/nutrition-label/${ocr.upload_id}/image`} alt="Uploaded nutrition label" /><p>Overall OCR confidence: <strong>{ocr.confidence}</strong></p>{ocr.warnings.length > 0 && <p className="notice">{ocr.warnings.join(' · ')}</p>}<div className="food-form"><label>Product name<input value={ocrDraft.name} onChange={(e) => updateOcr('name', e.target.value)} /></label><label>Brand<input value={ocrDraft.brand} onChange={(e) => updateOcr('brand', e.target.value)} /></label><label>Barcode<input inputMode="numeric" value={ocrDraft.barcode} onChange={(e) => updateOcr('barcode', e.target.value)} /></label><label>Serving name<input value={ocrDraft.serving_name} onChange={(e) => updateOcr('serving_name', e.target.value)} /></label><label>Serving quantity<input inputMode="decimal" value={ocrDraft.serving_quantity} onChange={(e) => updateOcr('serving_quantity', e.target.value)} /></label><label>Serving unit<input value={ocrDraft.serving_unit} onChange={(e) => updateOcr('serving_unit', e.target.value)} /></label><label>Nutrition basis<select value={ocrDraft.nutrition_basis} onChange={(e) => updateOcr('nutrition_basis', e.target.value)}><option value="per_serving">Per serving</option><option value="per_100g">Per 100 g</option><option value="per_100ml">Per 100 mL</option></select></label>{(['energy_kj','calories','protein_g','carbohydrates_g','fat_g','saturated_fat_g','sugar_g','fibre_g','sodium_mg','calcium_mg','iron_mg','potassium_mg','cholesterol_mg','alcohol_g','caffeine_mg'] as Array<keyof OcrDraft>).map((field) => <label key={field}>{field.replaceAll('_', ' ')}<input inputMode="decimal" value={ocrDraft[field]} onChange={(e) => updateOcr(field, e.target.value)} /><small>{ocr.field_confidence[field] ? `OCR: ${ocr.field_confidence[field]}` : 'OCR: unknown'}</small></label>)}</div><button className="quick-add" onClick={() => void saveOcrReview()}>Confirm reviewed label & save</button></div>}

    {savedFood && <div className="planner-card"><h2>Ready to use</h2><p><strong>{savedFood.name}</strong> is in the Food Library.</p><button className="quick-add" onClick={() => void addSavedToDiary()}>Add 1 serving to today</button></div>}
  </section>
}
