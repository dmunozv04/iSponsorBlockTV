import React from 'react'
import { Toggle } from './ui/Toggle'

export function GlobalSettings({ config, updateField }) {
    if (!config) return null

    return (
        <div className="card">
            <div className="card-header">
                <h3>Global Settings</h3>
            </div>

            <Toggle label="Skip Sponsor Segments" checked={config.skip_categories?.includes('sponsor')} onChange={(checked) => {
                const cats = new Set(config.skip_categories || [])
                if (checked) cats.add('sponsor'); else cats.delete('sponsor')
                updateField('skip_categories', Array.from(cats))
            }} />
            <Toggle label="Skip Intro Segments" checked={config.skip_categories?.includes('intro')} onChange={(checked) => {
                const cats = new Set(config.skip_categories || [])
                if (checked) cats.add('intro'); else cats.delete('intro')
                updateField('skip_categories', Array.from(cats))
            }} />
            <Toggle label="Skip Outro Segments" checked={config.skip_categories?.includes('outro')} onChange={(checked) => {
                const cats = new Set(config.skip_categories || [])
                if (checked) cats.add('outro'); else cats.delete('outro')
                updateField('skip_categories', Array.from(cats))
            }} />
            <Toggle label="Skip Interaction Segments" checked={config.skip_categories?.includes('interaction')} onChange={(checked) => {
                const cats = new Set(config.skip_categories || [])
                if (checked) cats.add('interaction'); else cats.delete('interaction')
                updateField('skip_categories', Array.from(cats))
            }} />
            <Toggle label="Skip Self Promo Segments" checked={config.skip_categories?.includes('selfpromo')} onChange={(checked) => {
                const cats = new Set(config.skip_categories || [])
                if (checked) cats.add('selfpromo'); else cats.delete('selfpromo')
                updateField('skip_categories', Array.from(cats))
            }} />
            <Toggle label="Skip Music Offtopic Segments" checked={config.skip_categories?.includes('music_offtopic')} onChange={(checked) => {
                const cats = new Set(config.skip_categories || [])
                if (checked) cats.add('music_offtopic'); else cats.delete('music_offtopic')
                updateField('skip_categories', Array.from(cats))
            }} />

            <div style={{ margin: '1rem 0', borderTop: '1px solid var(--border-color)' }}></div>

            <Toggle label="Skip Count Tracking" checked={config.skip_count_tracking} onChange={v => updateField('skip_count_tracking', v)} />
            <Toggle label="Mute Ads" checked={config.mute_ads} onChange={v => updateField('mute_ads', v)} />
            <Toggle label="Skip Ads" checked={config.skip_ads} onChange={v => updateField('skip_ads', v)} />
            <Toggle label="Auto Play" checked={config.auto_play} onChange={v => updateField('auto_play', v)} />
            <Toggle label="Use Proxy" checked={config.use_proxy} onChange={v => updateField('use_proxy', v)} />



            <div className="form-group">
                <label>Minimum Skip Length (seconds)</label>
                <input type="number" value={config.minimum_skip_length || 0} onChange={e => updateField('minimum_skip_length', parseInt(e.target.value))} />
            </div>
        </div>
    )
}
