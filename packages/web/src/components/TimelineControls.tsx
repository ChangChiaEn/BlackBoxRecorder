import { useEffect, useMemo, useRef } from 'react'
import { useTraceStore } from '@/stores/traceStore'
import { Button } from './ui/button'
import { Play, Pause, SkipBack, SkipForward, RotateCcw } from 'lucide-react'

const TimelineControls = () => {
    const {
        currentSession,
        events,
        currentTime,
        playbackSpeed,
        isPlaying,
        currentEventId,
        setCurrentTime,
        setIsPlaying,
        setPlaybackSpeed,
        selectEvent,
    } = useTraceStore()

    const intervalRef = useRef<NodeJS.Timeout | null>(null)

    // Calculate timeline bounds
    const { startTime, endTime, duration, progress } = useMemo(() => {
        if (!currentSession || events.length === 0) {
            return { startTime: 0, endTime: 0, duration: 0, progress: 0 }
        }

        const start = new Date(currentSession.start_time).getTime()
        
        // Validate start time
        if (!isFinite(start) || isNaN(start)) {
            return { startTime: 0, endTime: 0, duration: 0, progress: 0 }
        }
        
        // Use end_time from session, or last event's end_timestamp, or last event's timestamp
        let end: number
        if (currentSession.end_time) {
            end = new Date(currentSession.end_time).getTime()
        } else if (events.length > 0) {
            const lastEvent = events[events.length - 1]
            if (lastEvent.end_timestamp) {
                end = new Date(lastEvent.end_timestamp).getTime()
            } else {
                end = new Date(lastEvent.timestamp).getTime()
            }
        } else {
            end = start + 1000 // Fallback: 1 second
        }

        // Validate end time
        if (!isFinite(end) || isNaN(end)) {
            end = start + 1000
        }

        // Ensure minimum duration for very short traces
        const duration = Math.max(end - start, 1)
        const validCurrentTime = isFinite(currentTime) && !isNaN(currentTime) ? currentTime : start
        const progress = duration > 0 ? ((validCurrentTime - start) / duration) * 100 : 0

        return {
            startTime: start,
            endTime: end,
            duration,
            progress: Math.max(0, Math.min(100, progress)),
        }
    }, [currentSession, events, currentTime])

    // Get current event index
    const currentEventIndex = useMemo(() => {
        if (!currentEventId || events.length === 0) return -1
        return events.findIndex((e) => e.id === currentEventId)
    }, [currentEventId, events])

    // Playback logic
    useEffect(() => {
        if (isPlaying && duration > 0 && events.length > 0) {
            // For very short traces (< 10ms), use simulated playback with fixed duration
            if (duration < 10) {
                // Simulate playback over 2 seconds for visualization
                const playbackDuration = 2000 / playbackSpeed // 2 seconds total
                const startPlaybackTime = Date.now()
                const startProgress = ((currentTime - startTime) / duration) * 100
                
                intervalRef.current = setInterval(() => {
                    const elapsed = Date.now() - startPlaybackTime
                    const progress = Math.min(100, startProgress + (elapsed / playbackDuration) * 100)
                    const newTime = startTime + (progress / 100) * duration
                    
                    if (progress >= 100) {
                        setIsPlaying(false)
                        setCurrentTime(endTime)
                    } else {
                        setCurrentTime(newTime)
                    }
                }, 16) // ~60fps for smooth animation
            } else {
                // For longer traces, use time-based playback
                const intervalMs = duration < 1000 ? 16 : 100 // 16ms for <1s (60fps), 100ms otherwise
                // Calculate step to complete playback in reasonable time
                const targetPlaybackTime = Math.max(2000, duration * 10) / playbackSpeed // At least 2 seconds
                const stepMs = (duration / targetPlaybackTime) * intervalMs
                
                intervalRef.current = setInterval(() => {
                    setCurrentTime((prev) => {
                        const next = prev + stepMs
                        if (next >= endTime) {
                            setIsPlaying(false)
                            return endTime
                        }
                        return next
                    })
                }, intervalMs)
            }
        } else {
            if (intervalRef.current) {
                clearInterval(intervalRef.current)
                intervalRef.current = null
            }
        }

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current)
            }
        }
    }, [isPlaying, playbackSpeed, duration, endTime, startTime, setCurrentTime, setIsPlaying, currentTime])

    // Update selected event based on current time
    useEffect(() => {
        if (events.length === 0 || !isFinite(currentTime) || isNaN(currentTime)) return

        // For short traces (< 1s), use sequential event selection based on progress
        if (duration < 1000) {
            const progressPercent = ((currentTime - startTime) / duration) * 100
            const targetIndex = Math.min(
                Math.floor((progressPercent / 100) * events.length),
                events.length - 1
            )
            
            if (targetIndex >= 0 && targetIndex < events.length) {
                const targetEvent = events[targetIndex]
                if (targetEvent && targetEvent.id !== currentEventId) {
                    selectEvent(targetEvent.id)
                }
            }
        } else {
            // For longer traces, use time-based selection
            const eventAtTime = events.find((e) => {
                const eventTime = new Date(e.timestamp).getTime()
                if (!isFinite(eventTime) || isNaN(eventTime)) return false
                
                const eventEndTime = e.end_timestamp ? new Date(e.end_timestamp).getTime() : eventTime
                if (!isFinite(eventEndTime) || isNaN(eventEndTime)) return false
                
                return eventTime <= currentTime && eventEndTime >= currentTime
            })

            if (eventAtTime && eventAtTime.id !== currentEventId) {
                selectEvent(eventAtTime.id)
            }
        }
    }, [currentTime, events, currentEventId, selectEvent, duration, startTime])

    const handlePlayPause = () => {
        setIsPlaying(!isPlaying)
    }

    const handlePrevious = () => {
        if (currentEventIndex > 0) {
            const prevEvent = events[currentEventIndex - 1]
            const time = new Date(prevEvent.timestamp).getTime()
            if (isFinite(time) && !isNaN(time)) {
                setCurrentTime(time)
                selectEvent(prevEvent.id)
            }
        } else if (events.length > 0) {
            const firstEvent = events[0]
            const time = new Date(firstEvent.timestamp).getTime()
            if (isFinite(time) && !isNaN(time)) {
                setCurrentTime(time)
                selectEvent(firstEvent.id)
            }
        }
    }

    const handleNext = () => {
        if (currentEventIndex < events.length - 1) {
            const nextEvent = events[currentEventIndex + 1]
            const time = new Date(nextEvent.timestamp).getTime()
            if (isFinite(time) && !isNaN(time)) {
                setCurrentTime(time)
                selectEvent(nextEvent.id)
            }
        } else if (events.length > 0) {
            const lastEvent = events[events.length - 1]
            const endTimestamp = lastEvent.end_timestamp || lastEvent.timestamp
            const time = new Date(endTimestamp).getTime()
            if (isFinite(time) && !isNaN(time)) {
                setCurrentTime(time)
                selectEvent(lastEvent.id)
            }
        }
    }

    const handleReset = () => {
        setIsPlaying(false)
        if (events.length > 0) {
            const firstEvent = events[0]
            const time = new Date(firstEvent.timestamp).getTime()
            if (isFinite(time) && !isNaN(time)) {
                setCurrentTime(time)
                selectEvent(firstEvent.id)
            } else if (isFinite(startTime) && !isNaN(startTime)) {
                setCurrentTime(startTime)
            }
        } else if (isFinite(startTime) && !isNaN(startTime)) {
            setCurrentTime(startTime)
        }
    }

    const handleProgressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newProgress = parseFloat(e.target.value)
        const newTime = startTime + (newProgress / 100) * duration
        setCurrentTime(newTime)
        setIsPlaying(false)
    }

    const formatTime = (ms: number) => {
        // Handle invalid values
        if (!isFinite(ms) || isNaN(ms) || ms < 0) {
            return '0:00'
        }
        
        if (ms < 1000) {
            // Show milliseconds for very short durations
            return `${Math.max(0, ms).toFixed(1)}ms`
        }
        
        const seconds = Math.floor(ms / 1000)
        const minutes = Math.floor(seconds / 60)
        const hours = Math.floor(minutes / 60)
        
        if (hours > 0) {
            return `${hours}:${String(minutes % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
        }
        return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
    }

    const formatDuration = (ms: number) => {
        if (!isFinite(ms) || isNaN(ms) || ms < 0) {
            return '0.0ms'
        }
        if (ms < 1000) return `${ms.toFixed(1)}ms`
        return formatTime(ms)
    }

    if (!currentSession) return null

    return (
        <div className="bg-background/95 backdrop-blur border rounded-lg shadow-lg p-4">
            <div className="flex items-center gap-4">
                {/* Playback Controls */}
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleReset}
                        title="Reset to start"
                    >
                        <RotateCcw className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handlePrevious}
                        disabled={currentEventIndex <= 0}
                        title="Previous event"
                    >
                        <SkipBack className="h-4 w-4" />
                    </Button>
                    <Button
                        variant="default"
                        size="sm"
                        onClick={handlePlayPause}
                        title={isPlaying ? 'Pause' : 'Play'}
                    >
                        {isPlaying ? (
                            <Pause className="h-4 w-4" />
                        ) : (
                            <Play className="h-4 w-4" />
                        )}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleNext}
                        disabled={currentEventIndex >= events.length - 1}
                        title="Next event"
                    >
                        <SkipForward className="h-4 w-4" />
                    </Button>
                </div>

                {/* Progress Bar */}
                <div className="flex-1 flex items-center gap-3">
                    <span className="text-xs text-muted-foreground min-w-[60px]">
                        {formatTime(Math.max(0, currentTime - startTime))}
                    </span>
                    <input
                        type="range"
                        min="0"
                        max="100"
                        step={duration < 1000 ? "0.01" : "0.1"}
                        value={progress}
                        onChange={handleProgressChange}
                        className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <span className="text-xs text-muted-foreground min-w-[60px]">
                        {formatTime(duration)}
                    </span>
                </div>

                {/* Speed Control */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Speed:</span>
                    <div className="flex gap-1">
                        {[0.5, 1, 1.5, 2].map((speed) => (
                            <Button
                                key={speed}
                                variant={playbackSpeed === speed ? 'default' : 'outline'}
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => setPlaybackSpeed(speed)}
                            >
                                {speed}x
                            </Button>
                        ))}
                    </div>
                </div>

                {/* Event Counter */}
                <div className="text-xs text-muted-foreground min-w-[100px] text-right">
                    {currentEventIndex >= 0 ? currentEventIndex + 1 : 0} / {events.length} events
                </div>
            </div>
        </div>
    )
}

export default TimelineControls

