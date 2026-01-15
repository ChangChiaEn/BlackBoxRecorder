import { useMemo, useEffect, useRef, useCallback } from 'react'
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    Node,
    Edge,
    useNodesState,
    useEdgesState,
    MarkerType,
    ReactFlowInstance
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useTraceStore } from '@/stores/traceStore'
import EventNode from './EventNode'

const nodeTypes = {
    event: EventNode,
}

const FlowCanvas = () => {
    const { eventTree, currentEventId, selectEvent } = useTraceStore()

    // Transform tree to nodes/edges (simplified for MVP)
    // In a real app, use dagre or elkjs for auto-layout
    const { nodes, edges } = useMemo(() => {
        const nodes: Node[] = []
        const edges: Edge[] = []

        if (!eventTree) return { nodes, edges }

        // Recursive traversal to build graph
        // Placeholder logic - requires proper layouting algo
        let y = 0
        const traverse = (node: any, x: number = 0, parentId?: string) => {
            const id = node.event.id
            const event = node.event
            
            // Create label text based on event type
            let label = event.name || event.event_type || 'Event'
            if (event.tool_name) {
                label = event.tool_name
            } else if (event.event_type === 'llm_call') {
                label = `LLM: ${event.model || 'GPT'}`
            }
            
            nodes.push({
                id,
                position: { x, y: y * 100 },
                data: { 
                    label,
                    ...event 
                },
                type: 'event', // Use custom event node type
                selected: id === currentEventId,
            })

            if (parentId) {
                edges.push({
                    id: `${parentId}-${id}`,
                    source: parentId,
                    target: id,
                    type: 'smoothstep',
                    markerEnd: { type: MarkerType.ArrowClosed },
                })
            }

            y++
            node.children.forEach((child: any) => traverse(child, x + 200, id))
        }

        if (eventTree.event) {
            traverse(eventTree)
        } else if (eventTree.children) {
            eventTree.children.forEach((child: any) => traverse(child, 0))
        }

        return { nodes, edges }
    }, [eventTree, currentEventId])

    const [reactFlowNodes, setNodes, onNodesChange] = useNodesState(nodes)
    const [, , onEdgesChange] = useEdgesState(edges)
    const reactFlowInstanceRef = useRef<ReactFlowInstance | null>(null)
    const prevEventIdRef = useRef<string | null>(null)

    // Update nodes when nodes or currentEventId changes
    useEffect(() => {
        if (nodes.length > 0) {
            setNodes((nds) => {
                // Create a map of new nodes by id for quick lookup
                const newNodeMap = new Map(nodes.map(n => [n.id, n]))
                
                return nds.map((node) => {
                    const newNode = newNodeMap.get(node.id)
                    if (newNode) {
                        return {
                            ...newNode,
                            selected: node.id === currentEventId,
                        }
                    }
                    return {
                        ...node,
                        selected: node.id === currentEventId,
                    }
                })
            })
        }
    }, [currentEventId, setNodes, nodes])

    // Center view on selected node with animation
    useEffect(() => {
        if (currentEventId !== prevEventIdRef.current && reactFlowInstanceRef.current) {
            prevEventIdRef.current = currentEventId
            
            setTimeout(() => {
                if (reactFlowInstanceRef.current && currentEventId) {
                    reactFlowInstanceRef.current.fitView({ 
                        nodes: [{ id: currentEventId }], 
                        duration: 300,
                        padding: 0.2 
                    })
                }
            }, 100)
        }
    }, [currentEventId])

    const onInit = useCallback((instance: ReactFlowInstance) => {
        reactFlowInstanceRef.current = instance
    }, [])

    return (
        <div className="h-full w-full bg-slate-50 dark:bg-slate-900">
            <ReactFlow
                nodes={reactFlowNodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_, node) => selectEvent(node.id)}
                onInit={onInit}
                fitView
            >
                <Background />
                <Controls />
                <MiniMap />
            </ReactFlow>
        </div>
    )
}

export default FlowCanvas
