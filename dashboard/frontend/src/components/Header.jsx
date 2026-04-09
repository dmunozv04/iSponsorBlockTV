export function Header({ onSave, onDiscard, saving, hasChanges }) {
    return (
        <header className="header-container">
            <div className="header-brand">
                <img src="/LogoSponsorBlocker256px.png" alt="SponsorBlock Logo" />
                <div>
                    <h1>iSponsorBlockTV</h1>
                </div>
            </div>
            <div className="header-actions">
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
