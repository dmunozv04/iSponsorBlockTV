import { Toggle } from './ui/Toggle'

export function GlobalSettings({ config, options, updateField }) {
    if (!config) return null

    const updateCategory = (category, checked) => {
        const selected = new Set(config.skip_categories || [])
        if (checked) selected.add(category)
        else selected.delete(category)
        updateField('skip_categories', Array.from(selected))
    }

    return (
        <section className="card" aria-labelledby="configuration-title">
            <div className="card-header">
                <h2 id="configuration-title">Playback settings</h2>
                <p>Choose what to skip on your paired TVs.</p>
            </div>
            <div className="settings-section">
                <div className="form-group">
                    <label htmlFor="display-name">Display name</label>
                    <input id="display-name" placeholder="iSponsorBlockTV"
                        value={config.join_name ?? 'iSponsorBlockTV'}
                        onChange={e => updateField('join_name', e.target.value)}
                        onBlur={e => { if (!e.target.value.trim()) updateField('join_name', 'iSponsorBlockTV') }} />
                </div>
                <div className="form-group">
                    <label htmlFor="minimum-skip-length">Minimum skip length (seconds)</label>
                    <input id="minimum-skip-length" type="number" min="0" step="any"
                        value={config.minimum_skip_length ?? 0}
                        onChange={e => {
                            const value = parseFloat(e.target.value)
                            if (!isNaN(value)) updateField('minimum_skip_length', value)
                            else if (e.target.value === '') updateField('minimum_skip_length', '')
                        }}
                        onBlur={() => { if (config.minimum_skip_length === '') updateField('minimum_skip_length', 0) }} />
                </div>
            </div>
            <div className="settings-section">
                <h3 className="section-label">Skip segments</h3>
                {options.skip_categories.map(({ value, label }) => (
                    <Toggle key={value} label={label} checked={config.skip_categories?.includes(value)}
                        onChange={checked => updateCategory(value, checked)} />
                ))}
            </div>
            <div className="settings-section">
                <h3 className="section-label">Playback options</h3>
                <Toggle label="Mute ads" checked={config.mute_ads} onChange={v => updateField('mute_ads', v)} />
                <Toggle label="Skip ads" checked={config.skip_ads} onChange={v => updateField('skip_ads', v)} />
                <Toggle label="Auto play" checked={config.auto_play} onChange={v => updateField('auto_play', v)} />
                <Toggle label="Track skip counts" checked={config.skip_count_tracking} onChange={v => updateField('skip_count_tracking', v)} />
                <Toggle label="Use proxy" checked={config.use_proxy} onChange={v => updateField('use_proxy', v)} />
            </div>
            <div className="settings-section">
                <div className="form-group">
                    <label htmlFor="sponsorblock-api-url">SponsorBlock API URL</label>
                    <input id="sponsorblock-api-url" type="url" autoComplete="off" spellCheck={false} maxLength={4096}
                        placeholder={options.sponsorblock_api_url} value={config.sponsorblock_api_url}
                        onChange={e => updateField('sponsorblock_api_url', e.target.value)}
                        onBlur={e => updateField('sponsorblock_api_url', e.target.value.trim() || options.sponsorblock_api_url)} />
                </div>
            </div>
        </section>
    )
}
