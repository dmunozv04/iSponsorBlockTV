export function Header({ onSave, onDiscard, saving, hasChanges, onLogout, session }) {
    return (
        <header className="header-container">
            <div className="header-brand">
                <img src="/LogoSponsorBlocker256px.png" alt="" />
                <div>
                    <h1>iSponsorBlockTV</h1>
                    <p>Manage your TVs and playback settings.</p>
                </div>
            </div>
            <div className="header-actions">
                {hasChanges && <>
                    <span className="unsaved-indicator" role="status">Unsaved changes</span>
                    <button className="btn-secondary" onClick={onDiscard} disabled={saving}>Discard</button>
                </>}
                <button className="btn-primary" onClick={onSave} disabled={saving || !hasChanges}>
                    {saving ? 'Saving...' : 'Save changes'}
                </button>
                {session?.enabled && session.authenticated && (
                    <button className="btn-secondary" onClick={onLogout}>Log out</button>
                )}
            </div>
        </header>
    )
}
