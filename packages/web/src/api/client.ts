import { TraceSession, StateSnapshot } from "../types"

const API_BASE = "/api"

export async function fetchSessions(limit = 20): Promise<TraceSession[]> {
    const response = await fetch(`${API_BASE}/sessions?limit=${limit}`)
    if (!response.ok) throw new Error("Failed to fetch sessions")
    return response.json()
}

export async function fetchSession(sessionId: string): Promise<TraceSession> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`)
    if (!response.ok) throw new Error("Failed to fetch session")
    return response.json()
}

export async function fetchSessionTree(sessionId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/tree`)
    if (!response.ok) throw new Error("Failed to fetch session tree")
    return response.json()
}

export async function fetchSessionSnapshots(sessionId: string): Promise<StateSnapshot[]> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/snapshots`)
    if (!response.ok) throw new Error("Failed to fetch snapshots")
    return response.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: "DELETE",
    })
    if (!response.ok) throw new Error("Failed to delete session")
}

export async function startTakeover(sessionId: string, snapshotId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/takeover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ snapshot_id: snapshotId }),
    })
    if (!response.ok) throw new Error("Failed to start takeover")
    return response.json()
}
