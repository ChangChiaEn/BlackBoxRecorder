import { create } from "zustand"
import { TraceSession, TraceEvent } from "../types"
import { fetchSession, fetchSessionTree } from "../api/client"

interface TraceState {
    currentSession: TraceSession | null
    events: TraceEvent[]
    eventTree: any
    isLoading: boolean
    error: string | null

    // Playback state
    currentTime: number // timestamp in ms
    playbackSpeed: number
    isPlaying: boolean
    currentEventId: string | null

    // Actions
    loadSession: (sessionId: string) => Promise<void>
    setPlaybackSpeed: (speed: number) => void
    setIsPlaying: (isPlaying: boolean) => void
    setCurrentTime: (time: number) => void
    selectEvent: (eventId: string) => void
}

export const useTraceStore = create<TraceState>((set) => ({
    currentSession: null,
    events: [],
    eventTree: null,
    isLoading: false,
    error: null,

    currentTime: 0,
    playbackSpeed: 1,
    isPlaying: false,
    currentEventId: null,

    loadSession: async (sessionId: string) => {
        set({ isLoading: true, error: null })
        try {
            const session = await fetchSession(sessionId)
            const tree = await fetchSessionTree(sessionId)

            // Flatten events from tree for timeline
            const flattenEvents = (node: any, events: TraceEvent[] = []): TraceEvent[] => {
                if (node.event) {
                    events.push(node.event)
                }
                if (node.children && Array.isArray(node.children)) {
                    node.children.forEach((child: any) => flattenEvents(child, events))
                }
                return events
            }

            const events = flattenEvents(tree).sort((a, b) => {
                const timeA = new Date(a.timestamp).getTime()
                const timeB = new Date(b.timestamp).getTime()
                return timeA - timeB
            })

            const startTime = new Date(session.start_time).getTime()
            const firstEventTime = events.length > 0 
                ? new Date(events[0].timestamp).getTime()
                : startTime

            // Ensure we have a valid time
            const validTime = isFinite(firstEventTime) && !isNaN(firstEventTime) 
                ? firstEventTime 
                : (isFinite(startTime) && !isNaN(startTime) ? startTime : Date.now())

            set({
                currentSession: session,
                eventTree: tree,
                events,
                isLoading: false,
                currentTime: validTime,
                currentEventId: events.length > 0 ? events[0].id : null,
            })
        } catch (err) {
            set({ error: (err as Error).message, isLoading: false })
        }
    },

    setPlaybackSpeed: (speed: number) => set({ playbackSpeed: speed }),
    setIsPlaying: (isPlaying: boolean) => set({ isPlaying }),
    setCurrentTime: (time: number) => set({ currentTime: time }),
    selectEvent: (eventId: string) => set({ currentEventId: eventId }),
}))
