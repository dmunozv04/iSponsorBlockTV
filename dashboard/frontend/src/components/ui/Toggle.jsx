export function Toggle({ label, checked, onChange }) {
    return (
        <div className="toggle-group">
            <span>{label}</span>
            <label className="switch">
                <input type="checkbox" checked={!!checked} onChange={e => onChange(e.target.checked)} />
                <span className="slider"></span>
            </label>
        </div>
    )
}
