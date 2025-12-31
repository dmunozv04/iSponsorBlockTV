export function Header({ onSave, onDiscard, saving, hasChanges }) {
    return (
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <img src="/LogoSponsorBlocker256px.png" alt="SponsorBlock Logo" style={{ width: '50px', height: 'auto' }} />
                <div>
                    <h1>iSponsorBlockTV</h1>
                </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                {hasChanges && (
                    <button
                        className="btn-outline-danger"
                        onClick={onDiscard}
                        disabled={saving}
                    >
                        Discard Changes
                    </button>
                )}
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
