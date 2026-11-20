export function Toggle({ label, checked, onChange }) {
    return (
        <label className="toggle-group">
            <span>{label}</span>
            <span className="switch">
                <input type="checkbox" aria-label={label} checked={!!checked} onChange={e => onChange(e.target.checked)} />
                <span className="slider" aria-hidden="true"></span>
            </span>
        </label>
    )
}
