import { useState } from 'react'

export function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onLogin(username, password)
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-container">
      <section className="card login-card" aria-labelledby="login-title">
        <img className="login-logo" src="/LogoSponsorBlocker256px.png" alt="" />
        <h1 id="login-title">iSponsorBlockTV</h1>
        <form onSubmit={submit}>
          <div className="form-group">
            <label htmlFor="login-username">Username</label>
            <input id="login-username" autoComplete="username" autoFocus required maxLength={128}
              value={username} onChange={event => setUsername(event.target.value)} disabled={busy} />
          </div>
          <div className="form-group">
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" autoComplete="current-password" required maxLength={256}
              value={password} onChange={event => setPassword(event.target.value)} disabled={busy} />
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn-primary login-submit" disabled={busy} type="submit">
            {busy ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  )
}
