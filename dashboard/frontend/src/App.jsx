import { useState, useEffect, useCallback } from 'react'
import { Header } from './components/Header'
import { GlobalSettings } from './components/GlobalSettings'
import { DeviceList } from './components/DeviceList'
import { ChannelWhitelist } from './components/ChannelWhitelist'
import { ConfigJson } from './components/ConfigJson'
import { Login } from './components/Login'
import { Security } from './components/Security'
import { apiJson } from './api'
import toast, { Toaster } from 'react-hot-toast'

function App() {
  const [session, setSession] = useState(null)
  const [config, setConfig] = useState(null)
  const [configOptions, setConfigOptions] = useState(null)
  const [originalConfig, setOriginalConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    const refresh = () => apiJson('/api/auth/session').then(next => {
      if (active) setSession(next)
    }).catch(error => { if (active) { setError(error.message); setLoading(false) } })
    const expired = () => {
      setConfig(null)
      setConfigOptions(null)
      setOriginalConfig(null)
      setLoading(true)
      refresh()
    }
    refresh()
    window.addEventListener('session-expired', expired)
    return () => { active = false; window.removeEventListener('session-expired', expired) }
  }, [])

  const fetchConfig = useCallback(async () => {
    try {
      const [data, options] = await Promise.all([
        apiJson('/api/config'),
        apiJson('/api/config/options')
      ])
      setConfig(data)
      setConfigOptions(options)
      setOriginalConfig(JSON.parse(JSON.stringify(data)))
    } catch (err) {
      setError(err.message)
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const canAccess = Boolean(session && (!session.enabled || session.authenticated))
  useEffect(() => { if (canAccess) fetchConfig() }, [canAccess, fetchConfig])

  const handleLogin = async (username, password) => {
    const next = await apiJson('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
    setError(null)
    setLoading(true)
    setSession(next)
  }

  const handleLogout = async () => {
    try {
      const next = await apiJson('/api/auth/logout', { method: 'POST', body: '{}' })
      setConfig(null)
      setConfigOptions(null)
      setOriginalConfig(null)
      setSession(next)
      if (!next.enabled) {
        setLoading(true)
        await fetchConfig()
      }
    } catch (error) { toast.error(error.message) }
  }

  const handleSave = async () => {
    setSaving(true)
    const submitted = config
    try {
      const configToSave = JSON.parse(JSON.stringify(config))
      if (configToSave.minimum_skip_length === '') configToSave.minimum_skip_length = 0
      if (configToSave.devices) {
        configToSave.devices = configToSave.devices.map(d => ({
          ...d,
          offset: d.offset === '' ? 0 : d.offset
        }))
      }

      const saved = await apiJson('/api/config', {
        method: 'POST',
        body: JSON.stringify(configToSave)
      })
      setConfig(current => current === submitted ? saved.config : current)
      toast.success('Configuration saved successfully!')
      setOriginalConfig(JSON.parse(JSON.stringify(saved.config)))
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
    setConfig(prev => ({ ...prev, [key]: typeof value === 'function' ? value(prev[key]) : value }))
  }

  const replaceConfig = (nextConfig) => {
    setConfig(nextConfig)
  }

  const hasChanges = JSON.stringify(config) !== JSON.stringify(originalConfig)

  if (session?.enabled && !session.authenticated) return <Login onLogin={handleLogin} />
  if (error) return <div className="container" style={{ alignItems: 'center', marginTop: '4rem', color: 'var(--danger)' }}>{error}</div>
  if (loading || !session) return <div className="container" style={{ alignItems: 'center', marginTop: '4rem' }}>Loading configuration...</div>
  if (!config) return null

  return (
    <div className="dashboard">
      <Toaster position="bottom-right" />
      <Header onSave={handleSave} onDiscard={handleDiscard} saving={saving} hasChanges={hasChanges}
        session={session} onLogout={handleLogout} />
      <main className="dashboard-content">
        <div className="dashboard-grid">
          <div className="dashboard-column">
            <GlobalSettings config={config} options={configOptions} updateField={updateField} />
            <ConfigJson config={config} replaceConfig={replaceConfig} />
          </div>
          <div className="dashboard-column">
            <DeviceList config={config} updateField={updateField} />
            <ChannelWhitelist config={config} originalConfig={originalConfig} updateField={updateField} />
            <Security onSession={setSession} />
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
