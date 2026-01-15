import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { TraceEvent } from '../types'

interface EventNodeData extends TraceEvent {
    label: string
}

const EventNode = ({ data, selected }: NodeProps<EventNodeData>) => {
    const getStatusColor = () => {
        if (data.status === 'error') return 'bg-red-50 border-red-300 text-gray-900'
        if (data.status === 'success') return 'bg-green-50 border-green-300 text-gray-900'
        return 'bg-white border-gray-300 text-gray-900'
    }

    const getEventTypeLabel = () => {
        if (data.tool_name) return 'Tool'
        if (data.event_type === 'llm_call') return 'LLM'
        if (data.event_type === 'span') return 'Span'
        if (data.event_type === 'error') return 'Error'
        return 'Event'
    }

    return (
        <div
            className={`${getStatusColor()} rounded-lg border-2 shadow-sm p-3 min-w-[180px] max-w-[220px] transition-all duration-300 ${
                selected 
                    ? 'ring-2 ring-blue-500 scale-105 shadow-lg' 
                    : 'ring-0 scale-100'
            }`}
        >
            <Handle
                type="target"
                position={Position.Top}
                className="w-3 h-3 !bg-blue-500"
            />
            
            <div className="flex flex-col gap-1">
                <div className="flex-1 min-w-0">
                    <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                        {getEventTypeLabel()}
                    </div>
                    <div className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">
                        {data.label || data.name || data.event_type}
                    </div>
                    {data.tool_name && (
                        <div className="text-xs text-gray-700 dark:text-gray-300 mt-1">
                            Tool: {data.tool_name}
                        </div>
                    )}
                    {data.model && (
                        <div className="text-xs text-gray-700 dark:text-gray-300 mt-1">
                            Model: {data.model}
                        </div>
                    )}
                    {data.duration_ms !== undefined && data.duration_ms !== null && (
                        <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            {data.duration_ms < 1 
                                ? `${data.duration_ms.toFixed(3)}ms`
                                : data.duration_ms < 1000
                                ? `${data.duration_ms.toFixed(1)}ms`
                                : `${(data.duration_ms / 1000).toFixed(2)}s`}
                        </div>
                    )}
                </div>
            </div>

            <Handle
                type="source"
                position={Position.Bottom}
                className="w-3 h-3 !bg-blue-500"
            />
        </div>
    )
}

export default memo(EventNode)

