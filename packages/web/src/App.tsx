import { useEffect, useState } from 'react'
import { TraceSession } from './types'
import { fetchSessions } from './api/client'
import { useTraceStore } from './stores/traceStore'
import FlowCanvas from './components/FlowCanvas'
import TimelineControls from './components/TimelineControls'
import { Button } from './components/ui/button'

function App() {
    const [sessions, setSessions] = useState<TraceSession[]>([])
    const { currentSession, loadSession } = useTraceStore()

    useEffect(() => {
        // Load sessions on mount
        fetchSessions().then(setSessions).catch(console.error)
    }, [])

    return (
        <div className="flex h-screen w-full flex-col overflow-hidden">
            {/* Header */}
            <header className="flex h-14 items-center gap-4 border-b bg-muted/40 px-6">
                <h1 className="font-semibold text-lg">AgentBlackBox</h1>
                <div className="ml-auto flex items-center gap-2">
                    <select
                        className="h-8 rounded-md border border-input bg-background px-3 text-sm"
                        onChange={(e) => loadSession(e.target.value)}
                        value={currentSession?.id || ""}
                    >
                        <option value="" disabled>Select Trace Session</option>
                        {sessions.map(s => (
                            <option key={s.id} value={s.id}>
                                {s.name} ({new Date(s.start_time).toLocaleString()})
                            </option>
                        ))}
                    </select>
                    <Button variant="outline" size="sm">Help</Button>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex flex-1 overflow-hidden">
                {/* Sidebar (Event List) */}
                <aside className="w-64 border-r bg-muted/10 hidden md:block overflow-y-auto">
                    <div className="p-4 text-sm text-muted-foreground">
                        Select a session to view events
                    </div>
                </aside>

                {/* Canvas Area */}
                <div className="flex-1 relative">
                    {currentSession ? (
                        <FlowCanvas />
                    ) : (
                        <div className="flex items-center justify-center h-full text-muted-foreground">
                            Select a trace session to begin replay
                        </div>
                    )}

                    {/* Timeline Controls */}
                    {currentSession && (
                        <div className="absolute bottom-6 left-6 right-6">
                            <TimelineControls />
                        </div>
                    )}
                </div>

                {/* Right Panel (Details) */}
                <aside className="w-80 border-l bg-muted/10 hidden lg:block overflow-y-auto p-4">
                    <h3 className="font-medium mb-4">Event Details</h3>
                    <div className="text-sm text-muted-foreground">
                        Click a node to view details
                    </div>
                </aside>
            </main>
        </div>
    )
}

export default App
