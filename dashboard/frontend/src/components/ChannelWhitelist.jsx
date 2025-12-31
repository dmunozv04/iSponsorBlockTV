
import React, { useState } from 'react'

function ChannelAdder({ onAdd }) {
    const [newChannel, setNewChannel] = useState({ id: '', name: '' })

    const handleAdd = () => {
        if (!newChannel.id) return
        onAdd(newChannel)
        setNewChannel({ id: '', name: '' })
    }

    return (
        <div>
            <div className="form-group">
                <input
                    placeholder="Channel Name (e.g. Linus Tech Tips)"
                    value={newChannel.name}
                    onChange={e => setNewChannel({ ...newChannel, name: e.target.value })}
                />
            </div>
            <div className="form-group">
                <input
                    placeholder="Channel ID (e.g. UCXuqSBlHAE6Xw-yeJA0Tunw)"
                    value={newChannel.id}
                    onChange={e => setNewChannel({ ...newChannel, id: e.target.value })}
                />
            </div>
            <button className="btn-primary" style={{ width: '100%', marginTop: '0.5rem' }} onClick={handleAdd}>
                Add Channel
            </button>
        </div>
    )
}

export function ChannelWhitelist({ config, updateField }) {
    return (
        <div className="card">
            <div className="card-header">
                <h3>Channel Whitelist</h3>
            </div>
            <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>YouTube Data API Key</label>
                <input
                    type="text"
                    value={config.apikey || ''}
                    onChange={e => updateField('apikey', e.target.value)}
                    placeholder="Enter API Key to enable whitelisting"
                    style={{ width: '100%', marginBottom: '0.5rem' }}
                />
                {!config.apikey && (
                    <div style={{ fontSize: '0.85em', color: 'var(--text-secondary)' }}>
                        Required for channel verification. <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-primary)' }}>Get a key here</a>.
                    </div>
                )}
            </div>
            {
                config.channel_whitelist?.map((channel, idx) => (
                    <div key={idx} style={{
                        padding: '0.75rem',
                        background: 'var(--bg-tertiary)',
                        marginBottom: '0.5rem',
                        borderRadius: '4px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                    }}>
                        <div>
                            <div style={{ fontWeight: 'bold' }}>{channel.name || 'Unnamed Channel'}</div>
                            <div style={{ fontSize: '0.8em', color: 'var(--text-secondary)' }}>ID: {channel.id}</div>
                        </div>
                        <button onClick={() => {
                            const updatedWhitelist = config.channel_whitelist.filter((_, i) => i !== idx)
                            updateField('channel_whitelist', updatedWhitelist)
                        }} style={{ color: 'var(--text-secondary)', fontSize: '1.2rem', padding: '0 0.5rem' }}>
                            &times;
                        </button>
                    </div>
                ))
            }
            {(!config.channel_whitelist || config.channel_whitelist.length === 0) && <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No channels whitelisted.</p>}

            <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                <h4 style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>Add Channel</h4>
                <ChannelAdder onAdd={(newChannel) => {
                    const updatedWhitelist = [...(config.channel_whitelist || []), newChannel]
                    updateField('channel_whitelist', updatedWhitelist)
                }} />
            </div>
        </div >
    )
}
