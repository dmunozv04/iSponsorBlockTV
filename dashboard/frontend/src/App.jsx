import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { GlobalSettings } from './components/GlobalSettings'
import { DeviceList } from './components/DeviceList'
import { ChannelWhitelist } from './components/ChannelWhitelist'
import toast, { Toaster } from 'react-hot-toast'

function App() {
  const [config, setConfig] = useState(null)
  const [originalConfig, setOriginalConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config')
      if (!res.ok) throw new Error('Failed to load config')
      const data = await res.json()
      setConfig(data)
      setOriginalConfig(JSON.parse(JSON.stringify(data)))
    } catch (err) {
      setError(err.message)
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
      if (!res.ok) throw new Error('Failed to save config')
      toast.success('Configuration saved successfully!')
      setOriginalConfig(JSON.parse(JSON.stringify(config)))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const updateField = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }))
  }

  const hasChanges = JSON.stringify(config) !== JSON.stringify(originalConfig)

  if (loading) return <div className="container" style={{ alignItems: 'center', marginTop: '4rem' }}>Loading configuration...</div>
  if (error) return <div className="container" style={{ alignItems: 'center', marginTop: '4rem', color: 'var(--danger)' }}>{error}</div>
  if (!config) return null

  return (
    <div className="container">
      <Toaster position="bottom-right" />
      <Header onSave={handleSave} saving={saving} hasChanges={hasChanges} />

      <div className="grid-cols-2">
        <GlobalSettings config={config} updateField={updateField} />

        <div className="container" style={{ gap: '1rem' }}>
          <DeviceList config={config} updateField={updateField} />
          <ChannelWhitelist config={config} updateField={updateField} />

          <div className="card">
            <div className="card-header">
              <h3>Display Name</h3>
            </div>
            <div className="form-group">
              <label>Join Name</label>
              <input type="text" value={config.join_name || ''} onChange={e => updateField('join_name', e.target.value)} />
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3>Raw Data</h3>
            </div>
            <details>
              <summary style={{ cursor: 'pointer', color: 'var(--accent-primary)' }}>View JSON</summary>
              <pre style={{ overflow: 'auto', maxHeight: '300px', fontSize: '12px' }}>
                {JSON.stringify(config, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
