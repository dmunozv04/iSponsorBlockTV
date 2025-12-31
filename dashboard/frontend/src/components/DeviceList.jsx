import React, { useState } from 'react'
import toast from 'react-hot-toast'

export function DeviceList({ config, updateField }) {
    const [pairing, setPairing] = useState(false)
    const [pairingCode, setPairingCode] = useState('')
    const [pairingError, setPairingError] = useState(null)
    const [pairingName, setPairingName] = useState('')
    const [pairingOffset, setPairingOffset] = useState(0)

    // Editing State
    const [editingDeviceIdx, setEditingDeviceIdx] = useState(null)
    const [editForm, setEditForm] = useState({ name: '', offset: 0 })

    const handlePairDevice = async () => {
        setPairing(true)
        setPairingError(null)
        try {
            const res = await fetch('/api/pair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: pairingCode,
                    name: pairingName,
                    offset: pairingOffset
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
            setPairingOffset(0)
            toast.success(`Successfully paired with ${newDevice.name}!`)
        } catch (err) {
            setPairingError(err.message)
        } finally {
            setPairing(false)
        }
    }

    const handleEditClick = (index, device) => {
        setEditingDeviceIdx(index)
        setEditForm({ name: device.name || '', offset: device.offset || 0 })
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
            offset: editForm.offset
        }
        updateField('devices', updatedDevices)
        setEditingDeviceIdx(null)
    }

    const handleDeleteDevice = (index) => {
        if (!confirm("Are you sure you want to delete this device?")) return;
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
                                <label style={{ fontSize: '0.8em', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.25rem' }}>Offset (ms)</label>
                                <input
                                    type="number"
                                    placeholder="Offset (ms)"
                                    value={editForm.offset}
                                    onChange={e => setEditForm(prev => ({ ...prev, offset: parseInt(e.target.value) || 0 }))}
                                    style={{ width: '100%', padding: '0.4rem', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                                />
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem', alignSelf: 'flex-end', marginTop: '0.5rem' }}>
                                <button className="btn-primary" style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }} onClick={() => handleSaveEdit(idx)}>
                                    Save
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
                                <div style={{ fontSize: '0.8em', color: 'var(--text-secondary)' }}>ID: {device.screen_id}</div>
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
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                        <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l10-10zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z" />
                                    </svg>
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
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                                        <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z" />
                                        <path fillRule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z" />
                                    </svg>
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
                        onChange={e => setPairingOffset(parseInt(e.target.value) || 0)}
                    />
                </div>
                <button className="btn-primary" style={{ width: '100%', marginTop: '0.5rem' }} onClick={handlePairDevice} disabled={pairing}>
                    {pairing ? 'Pairing...' : 'Pair Device'}
                </button>
                {pairingError && <p style={{ color: 'var(--danger)', fontSize: '0.8rem', marginTop: '0.5rem' }}>{pairingError}</p>}
            </div>
        </div>
    )
}
