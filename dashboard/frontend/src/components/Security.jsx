import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { apiJson } from '../api'
import { Toggle } from './ui/Toggle'

export function Security({ onSession }) {
  const [saved, setSaved] = useState(null)
  const [enabled, setEnabled] = useState(false)
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [current, setCurrent] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiJson('/api/security').then(settings => {
      if (!active) return
      setSaved(settings)
      setEnabled(settings.enabled)
      setUsername(settings.username)
    }).catch(error => { if (active) setError(error.message) })
    return () => { active = false }
  }, [])

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (enabled && password && password !== confirm) {
      setError('The new passwords do not match.')
      return
    }
    if (enabled && !saved.password_configured && !password) {
      setError('Set a password before enabling sign-in.')
      return
    }
    setBusy(true)
    try {
      const updated = await apiJson('/api/security', {
        method: 'PUT',
        body: JSON.stringify({ enabled, username: enabled ? username : saved.username, password: enabled ? password : '', current_password: current })
      })
      onSession(updated.session)
      setSaved(updated)
      setEnabled(updated.enabled)
      setUsername(updated.username)
      setPassword('')
      setConfirm('')
      setCurrent('')
      toast.success(updated.enabled ? 'Sign-in is enabled.' : 'Sign-in is disabled.')
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  if (!saved) return <section className="card security-card">{error || 'Loading security settings...'}</section>
  const dirty = enabled !== saved.enabled || (enabled && (username.trim() !== saved.username || password !== ''))

  return (
    <section className="card security-card" aria-labelledby="security-title">
      <div className="card-header">
        <h2 id="security-title">Dashboard login</h2>
        <p>Choose whether a username and password are needed to manage this app.</p>
      </div>
      <form onSubmit={submit}>
        <fieldset disabled={busy} className="security-fields">
          <div className="security-toggle">
            <Toggle label="Require sign-in" checked={enabled} onChange={setEnabled} />
          </div>
          {enabled && <div className="form-grid security-credentials">
            <div className="form-group">
              <label htmlFor="security-username">Username</label>
              <input id="security-username" autoComplete="username" required maxLength={128}
                value={username} onChange={event => setUsername(event.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="security-password">{saved.password_configured ? 'New password' : 'Password'}</label>
              <input id="security-password" type="password" autoComplete="new-password" minLength={12} maxLength={256}
                required={!saved.password_configured}
                value={password} onChange={event => setPassword(event.target.value)} aria-describedby="password-help" />
              <small id="password-help" className="muted">
                {saved.password_configured ? 'Leave blank to keep your password. Use at least 12 characters for a new one.' :
                  'Use at least 12 characters.'}
              </small>
            </div>
            {password !== '' && <div className="form-group">
              <label htmlFor="security-confirm">Confirm new password</label>
              <input id="security-confirm" type="password" autoComplete="new-password" required
                maxLength={256} value={confirm} onChange={event => setConfirm(event.target.value)} />
            </div>}
          </div>}
          {saved.enabled && dirty && <div className="form-group current-password-field">
            <label htmlFor="security-current">Current password</label>
            <input id="security-current" type="password" autoComplete="current-password" required maxLength={256}
              value={current} onChange={event => setCurrent(event.target.value)} />
            <small className="muted">Confirm your current password to apply this change.</small>
          </div>}
          {error && <p className="form-error" role="alert">{error}</p>}
          {dirty && <div className="section-footer">
            <p className="muted">Other browsers will be signed out when you save.</p>
            <button className="btn-primary" disabled={busy} type="submit">
              {busy ? 'Saving...' : 'Save login settings'}
            </button>
          </div>}
        </fieldset>
      </form>
    </section>
  )
}
