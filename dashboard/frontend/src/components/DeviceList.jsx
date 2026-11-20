import { apiJson } from '../api'
import { useState } from 'react'
import toast from 'react-hot-toast'

export function DeviceList({ config, updateField }) {
    const [pairing, setPairing] = useState(false)
    const [pairingCode, setPairingCode] = useState('')

    const [pairingName, setPairingName] = useState('')
    const [pairingOffset, setPairingOffset] = useState(0)

    const [editingDeviceId, setEditingDeviceId] = useState(null)
    const [editForm, setEditForm] = useState({ name: '', offset: 0, screen_id: '' })
    const [showDeviceId, setShowDeviceId] = useState(false)

    const handlePairDevice = async () => {
        setPairing(true)

        try {
            const newDevice = await apiJson('/api/pair', {
                method: 'POST',
                body: JSON.stringify({
                    code: pairingCode,
                    name: pairingName,
                    offset: pairingOffset === '' ? 0 : parseFloat(pairingOffset)
                })
            })
            updateField('devices', (devices = []) => devices.some(device => device.screen_id === newDevice.screen_id)
                ? devices.map(device => device.screen_id === newDevice.screen_id ? newDevice : device)
                : [...devices, newDevice])
            setPairingName('')
            setPairingCode('')
            setPairingOffset(0)
            toast.success(`Successfully paired with ${newDevice.name}!`)
        } catch (err) {
            console.error(err)
            toast.error(err.message || "Failed to pair device")
        } finally {
            setPairing(false)
        }
    }

    const handleEditClick = (device) => {
        setEditingDeviceId(device.screen_id)
        setEditForm({ name: device.name || '', offset: device.offset || 0, screen_id: device.screen_id || '' })
        setShowDeviceId(false)
    }

    const handleCancelEdit = () => {
        setEditingDeviceId(null)
        setEditForm({ name: '', offset: 0 })
    }

    const handleSaveEdit = (id) => {
        updateField('devices', devices => devices.map(device => device.screen_id === id
            ? { ...device, name: editForm.name, offset: editForm.offset === '' ? 0 : editForm.offset }
            : device))
        setEditingDeviceId(null)
        setShowDeviceId(false)
    }

    const handleDeleteDevice = (id) => {
        updateField('devices', devices => devices.filter(device => device.screen_id !== id))
        if (editingDeviceId === id) {
            handleCancelEdit()
        }
    }

    return (
        <section className="card" aria-labelledby="devices-title">
            <div className="card-header">
                <h2 id="devices-title">Devices <span className="count-badge">{config.devices?.length || 0}</span></h2>
                <p>Pair the YouTube app on each TV you want to control.</p>
            </div>
            <div className="item-list">
                {config.devices?.map((device, idx) => (
                    <div key={device.screen_id} className="list-item">
                        {editingDeviceId === device.screen_id ? (
                            <div className="device-editor">
                                <div className="form-grid">
                                    <div className="form-group">
                                        <label htmlFor={`device-name-${idx}`}>Name</label>
                                        <input id={`device-name-${idx}`} value={editForm.name}
                                            onChange={e => setEditForm(prev => ({ ...prev, name: e.target.value }))} />
                                    </div>
                                    <div className="form-group">
                                        <label htmlFor={`device-offset-${idx}`}>Audio offset (ms)</label>
                                        <input id={`device-offset-${idx}`} type="number" step="any" value={editForm.offset}
                                            onChange={e => {
                                                const value = parseFloat(e.target.value)
                                                if (!isNaN(value)) setEditForm(prev => ({ ...prev, offset: value }))
                                                else if (e.target.value === '') setEditForm(prev => ({ ...prev, offset: '' }))
                                            }}
                                            onBlur={() => { if (editForm.offset === '') setEditForm(prev => ({ ...prev, offset: 0 })) }} />
                                    </div>
                                </div>
                                <div className="form-group">
                                    <label htmlFor={`device-id-${idx}`}>Device ID</label>
                                    <div className="input-action">
                                        <input id={`device-id-${idx}`} type={showDeviceId ? 'text' : 'password'}
                                            value={editForm.screen_id} readOnly />
                                        <button className="btn-secondary" onClick={() => setShowDeviceId(!showDeviceId)}>
                                            {showDeviceId ? 'Hide' : 'Show'}
                                        </button>
                                    </div>
                                </div>
                                <div className="button-row item-actions">
                                    <button className="btn-secondary" onClick={handleCancelEdit}>Cancel</button>
                                    <button className="btn-primary" onClick={() => handleSaveEdit(device.screen_id)}>Done</button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <div className="item-description">
                                    <strong>{device.name || 'Unnamed device'}</strong>
                                    <small>Audio offset: {device.offset ?? 0} ms</small>
                                </div>
                                <div className="button-row">
                                    <button className="btn-secondary btn-small" onClick={() => handleEditClick(device)}>Edit</button>
                                    <button className="btn-text-danger" aria-label={`Remove ${device.name || 'device'}`}
                                        onClick={() => handleDeleteDevice(device.screen_id)}>Remove</button>
                                </div>
                            </>
                        )}
                    </div>
                ))}
                {!config.devices?.length && <p className="empty-state">No TVs paired yet. Add your first one below.</p>}
            </div>
            <form className="settings-section" onSubmit={event => { event.preventDefault(); handlePairDevice() }}>
                <h3 className="section-label">Pair a TV</h3>
                <div className="form-group">
                    <label htmlFor="pairing-code">TV pairing code</label>
                    <input id="pairing-code" placeholder="123 456 789 012" inputMode="numeric" autoComplete="off"
                        required value={pairingCode} onChange={e => setPairingCode(e.target.value)} />
                    <small className="muted">On your TV, open YouTube settings and select Link with TV code.</small>
                </div>
                <div className="form-grid">
                    <div className="form-group">
                        <label htmlFor="pairing-name">Name <span className="optional">(optional)</span></label>
                        <input id="pairing-name" placeholder="Living room TV" value={pairingName}
                            onChange={e => setPairingName(e.target.value)} />
                    </div>
                    <div className="form-group">
                        <label htmlFor="pairing-offset">Audio offset (ms)</label>
                        <input id="pairing-offset" type="number" step="any" value={pairingOffset}
                            onChange={e => {
                                const value = parseFloat(e.target.value)
                                if (!isNaN(value)) setPairingOffset(value)
                                else if (e.target.value === '') setPairingOffset('')
                            }}
                            onBlur={() => { if (pairingOffset === '') setPairingOffset(0) }} />
                    </div>
                </div>
                <div className="button-row item-actions">
                    <button className="btn-primary" type="submit" disabled={pairing || !pairingCode.trim()}>
                        {pairing ? 'Pairing...' : 'Pair device'}
                    </button>
                </div>
            </form>
        </section>
    )
}
