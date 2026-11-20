import { apiJson } from '../api'
import React, { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'

function formatConfig(config) {
    return JSON.stringify(config, null, 2)
}

export function ConfigJson({ config, replaceConfig }) {
    const [jsonValue, setJsonValue] = useState('')
    const [isDirty, setIsDirty] = useState(false)
    const [isExpanded, setIsExpanded] = useState(false)
    const [validating, setValidating] = useState(false)
    const fileInputRef = useRef(null)
    const editorRef = useRef(null)

    useEffect(() => {
        if (!isDirty) {
            setJsonValue(formatConfig(config))
        }
    }, [config, isDirty])

    if (!config) return null

    const applyJson = async (nextJson) => {
        setValidating(true)
        try {
            const parsed = JSON.parse(nextJson)
            if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                throw new Error('Configuration must be a JSON object')
            }
            const validated = await apiJson('/api/config/validate', {
                method: 'POST',
                body: JSON.stringify(parsed)
            })
            replaceConfig(validated)
            setJsonValue(formatConfig(validated))
            setIsDirty(false)
            toast.success('Config JSON applied. Save changes to persist it.')
        } catch (error) {
            toast.error(error instanceof SyntaxError ? 'Invalid JSON. Check the config and try again.' : error.message)
        } finally {
            setValidating(false)
        }
    }

    const handleCopy = async () => {
        try {
            let copied = false
            if (navigator.clipboard?.writeText) {
                try {
                    await navigator.clipboard.writeText(jsonValue)
                    copied = true
                } catch {
                    copied = false
                }
            }
            if (!copied) {
                const editor = editorRef.current
                const active = document.activeElement
                const start = editor.selectionStart
                const end = editor.selectionEnd
                try {
                    editor.select()
                    copied = document.execCommand('copy')
                } finally {
                    editor.setSelectionRange(start, end)
                    active?.focus({ preventScroll: true })
                }
            }
            if (!copied) throw new Error('Clipboard unavailable')
            toast.success('Config JSON copied to clipboard')
        } catch {
            toast.error('Select the JSON and copy it manually.')
        }
    }

    const handleExport = () => {
        const blob = new Blob([jsonValue], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = 'config.json'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
        toast.success('Config JSON exported')
    }

    const handleImportFile = async (event) => {
        const file = event.target.files?.[0]
        if (!file) return

        try {
            const nextJson = await file.text()
            await applyJson(nextJson)
        } catch {
            toast.error('Failed to read JSON file')
        } finally {
            event.target.value = ''
        }
    }

    return (
        <section className="card" aria-labelledby="config-json-title">
            <div className="card-header config-json-header">
                <div>
                    <h2 id="config-json-title">Configuration file</h2>
                    <p>Import, export, or edit your configuration as JSON.</p>
                </div>
                <div className="button-row">
                    <button className="btn-secondary" type="button" onClick={() => fileInputRef.current?.click()} disabled={validating}>
                        Import
                    </button>
                    <button className="btn-secondary" type="button" onClick={handleExport}>
                        Export
                    </button>
                </div>
            </div>

            <button
                className="accordion-toggle"
                type="button"
                onClick={() => setIsExpanded((current) => !current)}
                aria-expanded={isExpanded}
                aria-controls="config-json-editor"
            >
                <span>{isExpanded ? 'Hide editor' : 'Show editor'}</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={isExpanded ? 'accordion-icon expanded' : 'accordion-icon'}>
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
            </button>

            <input
                ref={fileInputRef}
                type="file"
                accept="application/json,.json"
                onChange={handleImportFile}
                style={{ display: 'none' }}
            />

            {isExpanded && (
                <div id="config-json-editor">
                    <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                        <div className="editor-shell">
                            <button
                                className="btn-icon editor-copy-button"
                                type="button"
                                onClick={handleCopy}
                                title="Copy JSON"
                                aria-label="Copy JSON"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                </svg>
                            </button>
                            <textarea
                                ref={editorRef}
                                className="code-textarea"
                                value={jsonValue}
                                onChange={(event) => {
                                    setJsonValue(event.target.value)
                                    setIsDirty(true)
                                }}
                                aria-label="Configuration JSON"
                                spellCheck={false}
                            />
                        </div>
                    </div>

                    <div className="button-row">
                        <button className="btn-primary" type="button" onClick={() => applyJson(jsonValue)} disabled={validating}>
                            {validating ? 'Validating...' : 'Apply'}
                        </button>
                        <button
                            className="btn-secondary"
                            type="button"
                            onClick={() => {
                                setJsonValue(formatConfig(config))
                                setIsDirty(false)
                            }}
                        >
                            Reset Editor
                        </button>
                    </div>
                </div>
            )}
        </section>
    )
}
