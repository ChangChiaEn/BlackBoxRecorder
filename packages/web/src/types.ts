export interface TraceEvent {
    id: string
    trace_id: string
    parent_id?: string
    event_type: "span" | "llm_call" | "tool_call" | "state_change" | "error"
    timestamp: string
    end_timestamp?: string
    duration_ms?: number
    name: string
    status: "running" | "success" | "error"
    metadata: Record<string, any>
    input_data?: any
    output_data?: any
    model?: string
    prompt?: string
    response?: string
    tokens_used?: {
        prompt_tokens: number
        completion_tokens: number
        total_tokens: number
    }
    tool_name?: string
    arguments?: Record<string, any>
    result?: any
    error_message?: string
}

export interface StateSnapshot {
    id: string
    trace_id: string
    event_id: string
    timestamp: string
    state: any
    restorable: boolean
    checkpoint_name?: string
}

export interface TraceSession {
    id: string
    name: string
    description?: string
    start_time: string
    end_time?: string
    status: "running" | "success" | "error"
    event_count: number
    snapshot_count: number
    framework?: string
    metadata: Record<string, any>
}
