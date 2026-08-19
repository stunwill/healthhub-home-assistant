import { useRef, useState } from 'react'

const API = './api/v1'

type Preview = { total_rows: number; valid_rows: number; warning_rows: number; invalid_rows: number; duplicate_rows: number; rows: Record<string, unknown>[] }
type Candidate = { provider: string; provider_id?: string | null; name: string; brand?: string | null; barcode?: string | null; package_size?: string | null; nutrition_basis?: string | null; calories?: number | null; protein_g?: number | null; carbohydrates_g?: number | null; fat_g?: number | null; sugar_g?: number | null; source_url?: string | null; confidence: string; completeness: string; image_url?: string | null }
type OcrResult = { upload_id: string; extraction: Record<string, unknown>; confidence: string; field_confidence: Record<string, string>; warnings: string[] }

export default function FoodImportView({ onNotice }: { onNotice: (message: string) => void }) {
  const [text, setText] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [source, setSource] = useState<'spreadsheet' | 'csv' | 'xlsx'>('spreadsheet')
  const [sourceName, setSourceName] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [barcode, setBarcode] = useState('')
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [productSearch, setProductSearch] = useState('')
  const [products, setProducts] = useState<Candidate[]>([])
  const [ocr, setOcr] = useState<OcrResult | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

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
      setSource('spreadsheet'); setSourceName(null); setPreview(await response.json())
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not preview spreadsheet') }
    finally { setBusy(false) }
  }

  async function previewFile(file: File) {
    setBusy(true)
    try {
      const form = new FormData(); form.append('file', file)
      const response = await fetch(`${API}/foods/import/file`, { method: 'POST', body: form })
      if (!response.ok) { const data = await response.json().catch(() => null); throw new Error(data?.detail ?? 'Could not preview file') }
      setSource(file.name.toLowerCase().endsWith('.xlsx') ? 'xlsx' : 'csv'); setSourceName(file.name); setPreview(await response.json())
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
      setPreview(null); setText('')
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not import foods') }
    finally { setBusy(false) }
  }

  async function lookupBarcode() {
    const value = barcode.replace(/\D/g, '')
    if (!value) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/products/barcode/${value}`)
      const data = await response.json()
      if (!response.ok) throw new Error(data?.detail ?? 'Barcode lookup failed')
      if (data.status === 'local') { onNotice(`${data.food.name} is already in HealthHub.`); setCandidate(null) }
      else if (data.status === 'external') setCandidate(data.candidate)
      else { setCandidate({ provider: 'manual', name: '', barcode: value, confidence: 'unknown', completeness: 'partial' }); onNotice('Barcode not found. Create a food using a label photo or manual details.') }
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Barcode lookup failed') }
    finally { setBusy(false) }
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
    const response = await fetch(`${API}/products/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...item, reviewed: true }) })
    if (!response.ok) { onNotice('Could not save product'); return }
    const saved = await response.json(); onNotice(`${saved.name} saved to the Food Library.`); setCandidate(null)
  }

  async function scanLabel(file: File) {
    setBusy(true)
    try {
      const form = new FormData(); form.append('image', file)
      const response = await fetch(`${API}/capture/nutrition-label`, { method: 'POST', body: form })
      const data = await response.json()
      if (!response.ok) throw new Error(data?.detail ?? 'Nutrition label OCR failed')
      setOcr(data); onNotice('Local OCR complete. Review the extracted values against the label image before saving.')
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Nutrition label OCR failed') }
    finally { setBusy(false) }
  }

  return <section>
    <p className="eyebrow">Foods</p>
    <h1>Import & capture foods</h1>
    <p>All methods feed the same HealthHub Food Library and require preview or human review before saving.</p>

    <div className="planner-card"><h2>Spreadsheet and file import</h2>
      <div className="secondary-actions"><button className="quick-add" onClick={() => void copyTemplate()}>Copy template</button><a className="quick-add" href={`${API}/foods/import/template.csv`}>Download CSV</a><a className="quick-add" href={`${API}/foods/import/template.xlsx`}>Download XLSX</a></div>
      <p className="muted">Required: name. Nutrition may be per serving, per 100 g or per 100 mL. Values are validated before import.</p>
      <textarea aria-label="Paste spreadsheet data" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste spreadsheet cells here…" rows={7} />
      <div className="secondary-actions"><button disabled={!text.trim() || busy} onClick={() => void previewPaste()}>Preview pasted data</button><label className="upload-action">Upload CSV/XLSX<input ref={fileRef} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => { const file = event.target.files?.[0]; if (file) void previewFile(file) }} /></label></div>
    </div>

    {preview && <section className="planner-card import-preview"><h2>Import preview</h2><p>{preview.total_rows} rows, {preview.valid_rows} valid, {preview.warning_rows} warnings, {preview.invalid_rows} invalid, {preview.duplicate_rows} potential duplicates.</p><div className="table-scroll"><table><thead><tr><th>Name</th><th>Basis</th><th>Calories</th><th>Status</th></tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}><td>{String(row.name ?? '')}</td><td>{String(row.nutrition_basis ?? 'per_serving')}</td><td>{String(row.calories ?? '')}</td><td>{row._valid ? (row._duplicate ? 'Potential duplicate' : String((row._warnings as string[] | undefined)?.join(', ') || 'Ready')) : String((row._errors as string[] | undefined)?.join(', '))}</td></tr>)}</tbody></table></div><button className="quick-add" disabled={busy || preview.valid_rows === 0} onClick={() => void commitImport()}>Import valid rows</button></section>}

    <div className="planner-card"><h2>Scan or enter barcode</h2><p>HealthHub checks the local library first, then the configured external provider. Camera scanning falls back to manual barcode entry on unsupported browsers.</p><div className="secondary-actions"><input inputMode="numeric" aria-label="Barcode" placeholder="EAN / GTIN barcode" value={barcode} onChange={(event) => setBarcode(event.target.value)} /><button disabled={busy || !barcode.trim()} onClick={() => void lookupBarcode()}>Look up barcode</button></div></div>
    {candidate && <div className="planner-card"><h3>{candidate.name || 'Unknown barcode'}</h3><p>{candidate.brand || 'Brand not supplied'} · {candidate.barcode || 'No barcode'} · {candidate.provider}</p>{candidate.calories != null && <p><strong>{candidate.calories} kcal</strong> ({candidate.nutrition_basis || 'basis unknown'})</p>}<p className="muted">Confidence: {candidate.confidence}, nutrition: {candidate.completeness}. External values are not authoritative until you review them.</p>{candidate.name && <button className="quick-add" onClick={() => void saveCandidate(candidate)}>Review confirmed, save product</button>}</div>}

    <div className="planner-card"><h2>Search product database</h2><div className="secondary-actions"><input placeholder="Product name, brand or barcode" value={productSearch} onChange={(event) => setProductSearch(event.target.value)} /><button disabled={busy || productSearch.trim().length < 2} onClick={() => void searchProducts()}>Search products</button></div>{products.map((item) => <button className="search-result" key={`${item.provider}-${item.provider_id}-${item.name}`} onClick={() => setCandidate(item)}><span><strong>{item.name}</strong><small>{item.brand || 'Unknown brand'} · {item.provider}</small></span><b>{item.calories == null ? 'Nutrition partial' : `${Math.round(item.calories)} kcal`}</b></button>)}</div>

    <div className="planner-card"><h2>Photograph nutrition label</h2><p>Use a clear Australian Nutrition Information Panel photo. OCR runs locally inside the HealthHub add-on and the image is not sent to an OCR service.</p><label className="upload-action">Take photo or upload label<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(event) => { const file = event.target.files?.[0]; if (file) void scanLabel(file) }} /></label></div>
    {ocr && <div className="planner-card"><h3>OCR review</h3><img style={{ maxWidth: '100%', maxHeight: 320, objectFit: 'contain' }} src={`${API}/capture/nutrition-label/${ocr.upload_id}/image`} alt="Uploaded nutrition label" /><p>Overall OCR confidence: <strong>{ocr.confidence}</strong></p>{ocr.warnings.length > 0 && <p className="notice">{ocr.warnings.join(' · ')}</p>}<div className="table-scroll"><table><thead><tr><th>Field</th><th>Extracted</th><th>Confidence</th></tr></thead><tbody>{Object.entries(ocr.extraction).filter(([, value]) => value != null).map(([field, value]) => <tr key={field}><td>{field}</td><td>{String(value)}</td><td>{ocr.field_confidence[field] || 'unknown'}</td></tr>)}</tbody></table></div><p className="muted">Every field remains editable in the review/save workflow. OCR alone is never treated as packaging-confirmed nutrition.</p></div>}
  </section>
}
