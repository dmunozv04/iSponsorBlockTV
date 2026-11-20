import { apiJson } from '../api'

import { useState } from 'react'
import toast from 'react-hot-toast'

function ChannelAdder({ onAdd }) {
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
            const data = await apiJson(`/api/channels/search?${queryParams}`)
            setSearchResults(data)
        } catch (error) {
            console.error(error)
            toast.error(error.message || 'Channel search is unavailable. Try again shortly.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <form className="input-action" onSubmit={event => { event.preventDefault(); handleSearch() }}>
                <input aria-label="Search channels" placeholder="Channel name or ID" value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)} />
                <button className="btn-secondary" type="submit" disabled={loading || !searchTerm.trim()}>
                    {loading ? 'Searching...' : 'Search'}
                </button>
            </form>
            {searched && !loading && (
                <div className="search-results item-list" aria-live="polite">
                    {searchResults.length === 0 ? <p className="empty-state">No channels found.</p> :
                        searchResults.map(channel => (
                            <div key={channel.id} className="list-item">
                                <div className="item-description">
                                    <strong>{channel.name}</strong>
                                    <small>{channel.subscribers !== 'Hidden' ? `${channel.subscribers} subscribers` : 'Subscribers hidden'}</small>
                                </div>
                                <button className="btn-secondary btn-small" onClick={() => {
                                    if (!onAdd({ id: channel.id, name: channel.name })) return
                                    setSearchTerm('')
                                    setSearchResults([])
                                    setSearched(false)
                                }}>Add</button>
                            </div>
                        ))}
                </div>
            )}
        </div>
    )
}

export function ChannelWhitelist({ config, originalConfig, updateField }) {
    const [showKey, setShowKey] = useState(false)
    const [channelId, setChannelId] = useState('')
    const [channelName, setChannelName] = useState('')
    const canSearch = Boolean(config.apikey && config.apikey === originalConfig?.apikey)

    const addChannel = (channel) => {
        const id = channel.id.trim()
        if (!id) return false
        if (config.channel_whitelist?.some(existing => existing.id === id)) {
            toast.error('This channel is already whitelisted.')
            return false
        }
        updateField('channel_whitelist', [...(config.channel_whitelist || []), { id, name: channel.name.trim() }])
        return true
    }

    return (
        <section className="card" aria-labelledby="channels-title">
            <div className="card-header">
                <h2 id="channels-title">Channel whitelist <span className="count-badge">{config.channel_whitelist?.length || 0}</span></h2>
                <p>Keep videos from selected channels from being skipped.</p>
            </div>
            <div className="form-group">
                <label htmlFor="youtube-api-key">YouTube Data API key</label>
                <div className="input-action">
                    <input id="youtube-api-key" type={showKey ? 'text' : 'password'} value={config.apikey || ''}
                        onChange={e => updateField('apikey', e.target.value)} placeholder="Enter an API key to search channels" />
                    <button className="btn-secondary" aria-label={showKey ? 'Hide API key' : 'Show API key'}
                        onClick={() => setShowKey(!showKey)}>{showKey ? 'Hide' : 'Show'}</button>
                </div>
                {!config.apikey && <small className="muted">
                    Required for the channel whitelist. <a href="https://console.cloud.google.com/apis/credentials"
                        target="_blank" rel="noopener noreferrer">Get an API key</a>
                </small>}
                {config.apikey && !canSearch && <small className="notice">Save changes to use this key for search.</small>}
            </div>
            <div className="item-list">
                {config.channel_whitelist?.map((channel, idx) => (
                    <div key={idx} className="list-item">
                        <div className="item-description">
                            <strong>{channel.name || 'Unnamed channel'}</strong>
                            <small>{channel.id}</small>
                        </div>
                        <button className="btn-text-danger" aria-label={`Remove ${channel.name || 'channel'}`}
                            onClick={() => updateField('channel_whitelist', config.channel_whitelist.filter((_, i) => i !== idx))}>
                            Remove
                        </button>
                    </div>
                ))}
                {!config.channel_whitelist?.length && <p className="empty-state">No channels whitelisted.</p>}
            </div>
            {config.apikey.trim() && <div className="settings-section">
                <h3 className="section-label">Add a channel</h3>
                {canSearch && <ChannelAdder onAdd={addChannel} />}
                <details className="manual-channel-entry">
                    <summary>Add by channel ID</summary>
                    <form onSubmit={event => {
                        event.preventDefault()
                        if (addChannel({ id: channelId, name: channelName })) {
                            setChannelId('')
                            setChannelName('')
                        }
                    }}>
                        <div className="form-group">
                            <label htmlFor="whitelist-channel-id">Channel ID</label>
                            <input id="whitelist-channel-id" required maxLength={4096} autoComplete="off" spellCheck={false}
                                placeholder="UC..." value={channelId} onChange={e => setChannelId(e.target.value)} />
                        </div>
                        <div className="form-group">
                            <label htmlFor="whitelist-channel-name">Channel name <span className="optional">(optional)</span></label>
                            <input id="whitelist-channel-name" maxLength={4096}
                                value={channelName} onChange={e => setChannelName(e.target.value)} />
                        </div>
                        <div className="button-row item-actions">
                            <button className="btn-secondary" type="submit" disabled={!channelId.trim()}>Add channel</button>
                        </div>
                    </form>
                </details>
            </div>}
        </section>
    )
}
