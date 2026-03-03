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
      const configToSave = JSON.parse(JSON.stringify(config))
      // Sanitize numeric fields that might be empty strings
      if (configToSave.minimum_skip_length === '') configToSave.minimum_skip_length = 0
      if (configToSave.devices) {
        configToSave.devices = configToSave.devices.map(d => ({
          ...d,
          offset: d.offset === '' ? 0 : parseInt(d.offset)
        }))
      }

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configToSave)
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

  const handleDiscard = () => {
    if (originalConfig) {
      setConfig(JSON.parse(JSON.stringify(originalConfig)))
      toast.success('Changes discarded')
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
      <Header onSave={handleSave} onDiscard={handleDiscard} saving={saving} hasChanges={hasChanges} />

      <div className="grid-cols-2">
        <div className="container" style={{ gap: '1rem' }}>
          <div className="container" style={{ gap: '1rem' }}>
            <GlobalSettings config={config} updateField={updateField} />
          </div>
        </div>

        <div className="container" style={{ gap: '1rem' }}>
          <DeviceList config={config} updateField={updateField} />
          <ChannelWhitelist config={config} originalConfig={originalConfig} updateField={updateField} />
        </div>
      </div>
    </div>
  )
}

export default App
