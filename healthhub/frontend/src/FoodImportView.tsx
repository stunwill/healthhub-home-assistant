import { useState } from 'react'

const API = './api/v1'

export default function FoodImportView({ onNotice }: { onNotice: (message: string) => void }) {
  const [text, setText] = useState('')
  const [preview, setPreview] = useState<{ total_rows: number; valid_rows: number; warning_rows: number; invalid_rows: number; duplicate_rows: number; rows: Record<string, unknown>[] } | null>(null)
  const [busy, setBusy] = useState(false)

  async function copyTemplate() {
    const response = await fetch(`${API}/foods/import/template`)
    const payload = await response.json() as { template: string }
    await navigator.clipboard.writeText(payload.template)
    setText(payload.template + '\n')
    onNotice('Import template copied. Paste your spreadsheet rows below.')
  }

  async function previewImport() {
    setBusy(true)
    try {
      const response = await fetch(`${API}/foods/import/preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tsv: text }) })
      if (!response.ok) throw new Error('Could not preview spreadsheet')
      setPreview(await response.json())
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not preview spreadsheet') }
    finally { setBusy(false) }
  }

  async function commitImport() {
    if (!preview) return
    setBusy(true)
    try {
      const response = await fetch(`${API}/foods/import/commit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rows: preview.rows, duplicate_action: 'skip' }) })
      if (!response.ok) throw new Error('Could not import foods')
      const result = await response.json() as { created: number; updated: number; skipped: number; rejected: number }
      onNotice(`Import complete: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped, ${result.rejected} rejected.`)
      setPreview(null)
      setText('')
    } catch (error) { onNotice(error instanceof Error ? error.message : 'Could not import foods') }
    finally { setBusy(false) }
  }

  return <section>
    <p className="eyebrow">Foods</p>
    <h1>Import foods</h1>
    <p>Copy rows from Excel, Google Sheets, Numbers or another TSV-compatible spreadsheet, then paste them here. Empty nutrition fields are allowed.</p>
    <div className="planner-card">
      <button className="quick-add" onClick={() => void copyTemplate()}>Copy import template</button>
      <textarea aria-label="Paste spreadsheet data" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste spreadsheet cells here…" rows={10} />
      <button disabled={!text.trim() || busy} onClick={() => void previewImport()}>{busy ? 'Checking…' : 'Preview import'}</button>
    </div>
    {preview && <section className="planner-card import-preview"><h2>Import preview</h2><p>{preview.total_rows} rows, {preview.valid_rows} valid, {preview.warning_rows} warnings, {preview.invalid_rows} invalid, {preview.duplicate_rows} potential duplicates.</p><div className="table-scroll"><table><thead><tr><th>Name</th><th>Calories</th><th>Status</th></tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}><td>{String(row.name ?? '')}</td><td>{String(row.calories ?? '')}</td><td>{row._valid ? (row._duplicate ? 'Potential duplicate' : 'Ready') : String((row._errors as string[] | undefined)?.join(', '))}</td></tr>)}</tbody></table></div><button className="quick-add" disabled={busy || preview.valid_rows === 0} onClick={() => void commitImport()}>Import valid rows</button></section>}
  </section>
}
