import React, { useState } from 'react'
import toast from 'react-hot-toast'

export function DeviceList({ config, updateField }) {
    const [pairing, setPairing] = useState(false)
    const [pairingCode, setPairingCode] = useState('')

    const [pairingName, setPairingName] = useState('')
    const [pairingOffset, setPairingOffset] = useState(0)

    // Editing State
    const [editingDeviceIdx, setEditingDeviceIdx] = useState(null)
    const [editForm, setEditForm] = useState({ name: '', offset: 0, screen_id: '' })
    const [showDeviceId, setShowDeviceId] = useState(false)

    const handlePairDevice = async () => {
        setPairing(true)

        try {
            const res = await fetch('/api/pair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: pairingCode,
                    name: pairingName,
                    offset: pairingOffset === '' ? 0 : parseInt(pairingOffset)
                })
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || 'Pairing failed')
            }
            const newDevice = await res.json()
            const updatedDevices = [...(config.devices || []), newDevice]
            updateField('devices', updatedDevices)
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

    const handleEditClick = (index, device) => {
        setEditingDeviceIdx(index)
        setEditForm({ name: device.name || '', offset: device.offset || 0, screen_id: device.screen_id || '' })
        setShowDeviceId(false)
    }

    const handleCancelEdit = () => {
        setEditingDeviceIdx(null)
        setEditForm({ name: '', offset: 0 })
    }

    const handleSaveEdit = (index) => {
        const updatedDevices = [...config.devices]
        updatedDevices[index] = {
            ...updatedDevices[index],
            name: editForm.name,
            offset: editForm.offset,
            screen_id: editForm.screen_id
        }
        updateField('devices', updatedDevices)
        setEditingDeviceIdx(null)
        setShowDeviceId(false)
    }

    const handleDeleteDevice = (index) => {
        const updatedDevices = config.devices.filter((_, i) => i !== index)
        updateField('devices', updatedDevices)
        if (editingDeviceIdx === index) {
            handleCancelEdit()
        }
    }

    return (
        <div className="card">
            <div className="card-header">
                <h3>Devices</h3>
            </div>
            {config.devices?.map((device, idx) => (
                <div key={idx} style={{
                    padding: '0.75rem',
                    background: 'var(--bg-tertiary)',
                    marginBottom: '0.5rem',
                    borderRadius: '4px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.5rem'
                }}>
                    {editingDeviceIdx === idx ? (
                        <div style={{ display: 'flex', gap: '0.5rem', width: '100%', alignItems: 'flex-start', flexDirection: 'column' }}>
                            <div style={{ width: '100%' }}>
                                <label style={{ fontSize: '0.8em', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>Name</label>
                                <input
                                    placeholder="Name"
                                    value={editForm.name}
                                    onChange={e => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                                    style={{ width: '100%', marginBottom: '0.5rem', padding: '0.4rem', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                                />
                                <label style={{ fontSize: '0.8em', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>Device ID</label>
                                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', marginBottom: '0.5rem' }}>
                                    <input
                                        type={showDeviceId ? "text" : "password"}
                                        placeholder="Device ID"
                                        value={editForm.screen_id}
                                        readOnly
                                        style={{ width: '100%', padding: '0.4rem', paddingRight: '35px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'default', opacity: 0.9 }}
                                    />
                                    <button
                                        onClick={() => setShowDeviceId(!showDeviceId)}
                                        style={{
                                            position: 'absolute',
                                            right: '5px',
                                            background: 'transparent',
                                            border: 'none',
                                            color: 'var(--text-secondary)',
                                            cursor: 'pointer',
                                            display: 'flex',
                                            alignItems: 'center',
                                            padding: '2px'
                                        }}
                                        title={showDeviceId ? "Hide ID" : "Show ID"}
                                    >
                                        {showDeviceId ? (
                                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                                        ) : (
                                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                                        )}
                                    </button>
                                </div>
                                <label style={{ fontSize: '0.8em', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>Offset (ms)</label>
                                <input
                                    type="number"
                                    placeholder="Offset (ms)"
                                    value={editForm.offset}
                                    onChange={e => {
                                        const val = parseInt(e.target.value)
                                        if (!isNaN(val)) setEditForm(prev => ({ ...prev, offset: val }))
                                        else if (e.target.value === '') setEditForm(prev => ({ ...prev, offset: '' }))
                                    }}
                                    onBlur={() => {
                                        if (editForm.offset === '') setEditForm(prev => ({ ...prev, offset: 0 }))
                                    }}
                                    style={{ width: '100%', padding: '0.4rem', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                                />
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem', alignSelf: 'flex-end', marginTop: '0.5rem' }}>
                                <button className="btn-primary" style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }} onClick={() => handleSaveEdit(idx)}>
                                    Done
                                </button>
                                <button style={{
                                    padding: '0.25rem 0.75rem',
                                    fontSize: '0.8rem',
                                    background: 'transparent',
                                    border: '1px solid var(--border-color)',
                                    color: 'var(--text-primary)',
                                    cursor: 'pointer',
                                    borderRadius: '4px'
                                }} onClick={handleCancelEdit}>
                                    Cancel
                                </button>
                            </div>
                        </div>
                    ) : (
                        <>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 'bold' }}>{device.name || 'Unnamed Device'}</div>
                                <div style={{ fontSize: '0.8em', color: 'var(--text-secondary)' }}>Offset: {device.offset} ms</div>
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button onClick={() => handleEditClick(idx, device)} title="Edit Device" style={{
                                    background: 'transparent',
                                    border: 'none',
                                    color: 'var(--text-primary)',
                                    cursor: 'pointer',
                                    padding: '0.25rem',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    opacity: 0.7,
                                    transition: 'opacity 0.2s'
                                }}>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" /></svg>
                                </button>
                                <button onClick={() => handleDeleteDevice(idx)} title="Delete Device" style={{
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
                        </>
                    )}
                </div>
            ))}
            {(!config.devices || config.devices.length === 0) && <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>No devices found.</p>}

            <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                <h4 style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>Pair New Device</h4>
                <div className="form-group">
                    <label style={{ fontSize: '0.8em', color: 'var(--text-secondary)' }}>
                        Enter the code from YouTube on TV (Settings -&gt; Link with TV code).
                    </label>
                    <input
                        placeholder="Pairing Code (e.g. 123 456 789)"
                        value={pairingCode}
                        onChange={e => setPairingCode(e.target.value)}
                    />
                </div>
                <div className="form-group">
                    <input
                        placeholder="Custom Name (Optional)"
                        value={pairingName}
                        onChange={e => setPairingName(e.target.value)}
                    />
                </div>
                <div className="form-group">
                    <label style={{ fontSize: '0.8em', color: 'var(--text-secondary)' }}>Audio Offset (ms)</label>
                    <input
                        type="number"
                        placeholder="Offset (ms)"
                        value={pairingOffset}
                        onChange={e => {
                            const val = parseInt(e.target.value)
                            if (!isNaN(val)) setPairingOffset(val)
                            else if (e.target.value === '') setPairingOffset('')
                        }}
                        onBlur={() => {
                            if (pairingOffset === '') setPairingOffset(0)
                        }}
                    />
                </div>
                <button className="btn-primary" style={{ width: '100%', marginTop: '0.5rem' }} onClick={handlePairDevice} disabled={pairing}>
                    {pairing ? 'Pairing...' : 'Pair Device'}
                </button>
            </div>
        </div>
    )
}
