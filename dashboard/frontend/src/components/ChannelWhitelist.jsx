
import React, { useState } from 'react'
import toast from 'react-hot-toast'

function ChannelAdder({ onAdd, config }) {
    const [searchTerm, setSearchTerm] = useState('')
    const [searchResults, setSearchResults] = useState([])
    const [loading, setLoading] = useState(false)
    const [searched, setSearched] = useState(false)

    const handleSearch = async () => {
        if (!searchTerm) return
        setLoading(true)
        setSearched(true)
        setSearchResults([])
        try {
            const queryParams = new URLSearchParams({
                query: searchTerm
            })
            const res = await fetch(`/api/channels/search?${queryParams}`)
            if (res.ok) {
                const data = await res.json()
                setSearchResults(data)
            } else {
                let errorMessage = "Search failed"
                try {
                    const errorData = await res.json()
                    if (errorData.detail) errorMessage = errorData.detail
                } catch (e) {
                    // Ignore JSON parse error, stick to default message
                }
                toast.error(errorMessage)
                console.error("Search failed:", errorMessage)
            }
        } catch (error) {
            console.error(error)
        } finally {
            setLoading(false)
        }
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            handleSearch()
        }
    }

    return (
        <div>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                <input
                    placeholder="Search Channel (e.g. Linus Tech Tips)"
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    onKeyDown={handleKeyDown}
                    style={{ flex: 1 }}
                />
                <button
                    className="btn-primary"
                    onClick={handleSearch}
                    disabled={loading || !searchTerm}
                    style={{ minWidth: '80px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
                >
                    {loading ? <div className="spinner" style={{ width: '16px', height: '16px', border: '2px solid #fff', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> : 'Search'}
                </button>
            </div>

            {searched && (
                <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: '4px' }}>
                    {searchResults.length === 0 ? (
                        <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                            No channels found.
                        </div>
                    ) : (
                        searchResults.map((channel) => (
                            <div key={channel.id} style={{
                                padding: '0.75rem',
                                borderBottom: '1px solid var(--border-color)',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                            }}>
                                <div>
                                    <div style={{ fontWeight: 'bold' }}>{channel.name}</div>
                                    <div style={{ fontSize: '0.8em', color: 'var(--text-secondary)' }}>
                                        {channel.subscribers !== "Hidden" ? `${channel.subscribers} subs` : 'Subs hidden'} • {channel.id}
                                    </div>
                                </div>
                                <button
                                    className="btn-primary"
                                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.8em' }}
                                    onClick={() => {
                                        onAdd({ id: channel.id, name: channel.name })
                                        setSearchTerm('')
                                        setSearchResults([])
                                        setSearched(false)
                                    }}
                                >
                                    Add
                                </button>
                            </div>
                        ))
                    )}
                </div>
            )}
            <style>{`
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}

export function ChannelWhitelist({ config, originalConfig, updateField }) {
    const [showKey, setShowKey] = useState(false)

    return (
        <div className="card">
            <div className="card-header">
                <h3>Channel Whitelist</h3>
            </div>
            <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>YouTube Data API Key</label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <input
                        type={showKey ? "text" : "password"}
                        value={config.apikey || ''}
                        onChange={e => updateField('apikey', e.target.value)}
                        placeholder="Enter API Key to enable whitelisting"
                        style={{ width: '100%', paddingRight: '40px' }}
                    />
                    <button
                        onClick={() => setShowKey(!showKey)}
                        title={showKey ? "Hide API Key" : "Show API Key"}
                        style={{
                            position: 'absolute',
                            right: '5px',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            color: 'var(--text-secondary)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '5px'
                        }}
                    >
                        {showKey ? (
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                        ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                        )}
                    </button>
                </div>
                {!config.apikey && (
                    <div style={{ fontSize: '0.85em', color: 'var(--text-secondary)' }}>
                        Required for channel verification. <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-primary)' }}>Get a key here</a>
                    </div>
                )}
                {config.apikey && config.apikey !== originalConfig?.apikey && (
                    <div style={{ fontSize: '0.85em', color: 'var(--warning)' }}>
                        Please save changes to enable search.
                    </div>
                )}
            </div>
            {config.apikey && config.apikey === originalConfig?.apikey && (
                <>
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
                                }} title="Remove Channel" style={{
                                    background: 'transparent',
                                    border: 'none',
                                    color: 'var(--danger)',
                                    cursor: 'pointer',
                                    padding: '0.25rem',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    opacity: 0.7,
                                    transition: 'opacity 0.2s'
                                }}>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" /></svg>
                                </button>
                            </div>
                        ))
                    }
                    {(!config.channel_whitelist || config.channel_whitelist.length === 0) && <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No channels whitelisted.</p>}

                    <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                        <h4 style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>Add Channel</h4>
                        <ChannelAdder config={config} onAdd={(newChannel) => {
                            const updatedWhitelist = [...(config.channel_whitelist || []), newChannel]
                            updateField('channel_whitelist', updatedWhitelist)
                        }} />
                    </div>
                </>
            )}
        </div >
    )
}
