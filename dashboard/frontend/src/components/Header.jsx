export function Header({ onSave, saving, hasChanges }) {
    return (
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <img src="/LogoSponsorBlocker256px.png" alt="SponsorBlock Logo" style={{ width: '50px', height: 'auto' }} />
                <div>
                    <h1>iSponsorBlockTV</h1>
                </div>
            </div>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                {hasChanges && <span style={{ color: 'var(--accent-primary)', fontSize: '0.9rem', fontStyle: 'italic' }}>Unsaved Changes</span>}
                <button
                    className="btn-primary"
                    onClick={onSave}
                    disabled={saving || !hasChanges}
                    style={{
                        opacity: hasChanges ? 1 : 0.5,
                        cursor: hasChanges ? 'pointer' : 'not-allowed',
                        transition: 'opacity 0.2s ease'
                    }}
                >
                    {saving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>
        </header>
    )
}
