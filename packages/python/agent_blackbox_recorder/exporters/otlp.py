"""
OpenTelemetry OTLP exporter for AgentBlackBoxRecorder.

Exports traces to any OpenTelemetry-compatible backend.
"""

from typing import Any, Optional, Sequence

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider, Span as OTelSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
    BatchSpanProcessor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from agent_blackbox_recorder.core.events import TraceSession, TraceEvent, EventType


class OTLPExporter:
    """
    Export traces to OpenTelemetry-compatible backends.
    
    Supports exporting to:
    - Jaeger
    - Zipkin
    - Datadog
    - Honeycomb
    - Grafana Tempo
    - Any OTLP-compatible collector
    
    Example:
        ```python
        from agent_blackbox_recorder import Recorder
        from agent_blackbox_recorder.exporters import OTLPExporter
        
        exporter = OTLPExporter(endpoint="http://localhost:4317")
        recorder = Recorder(storage="./traces")
        
        # Export existing sessions
        exporter.export_session(recorder.load_session("abc123"))
        ```
    """
    
    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        service_name: str = "agent-blackbox-recorder",
        headers: Optional[dict[str, str]] = None,
        insecure: bool = True,
    ) -> None:
        """
        Initialize the OTLP exporter.
        
        Args:
            endpoint: OTLP collector endpoint
            service_name: Service name to report
            headers: Optional headers for authentication
            insecure: Whether to use insecure connection
        """
        self._endpoint = endpoint
        self._service_name = service_name
        
        # Set up OpenTelemetry
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "0.1.0",
        })
        
        self._tracer_provider = TracerProvider(resource=resource)
        
        # Create OTLP exporter
        self._otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers or {},
            insecure=insecure,
        )
        
        # Add batch processor
        self._tracer_provider.add_span_processor(
            BatchSpanProcessor(self._otlp_exporter)
        )
        
        # Get tracer
        self._tracer = self._tracer_provider.get_tracer(__name__)
    
    def export_session(self, session: TraceSession) -> None:
        """
        Export a trace session to the OTLP collector.
        
        Args:
            session: The TraceSession to export
        """
        # Build span hierarchy
        spans_by_id: dict[str, OTelSpan] = {}
        
        for event in sorted(session.events, key=lambda e: e.timestamp):
            self._export_event(event, spans_by_id)
        
        # Force flush
        self._tracer_provider.force_flush()
    
    def _export_event(
        self,
        event: TraceEvent,
        spans_by_id: dict[str, OTelSpan],
    ) -> None:
        """Export a single event as an OpenTelemetry span."""
        # Determine parent context
        parent_context = None
        if event.parent_id and event.parent_id in spans_by_id:
            parent_span = spans_by_id[event.parent_id]
            parent_context = otel_trace.set_span_in_context(parent_span)
        
        # Create span
        with self._tracer.start_as_current_span(
            event.name,
            context=parent_context,
            start_time=int(event.timestamp.timestamp() * 1e9),
        ) as span:
            # Set attributes
            span.set_attribute("event.id", event.id)
            span.set_attribute("event.type", event.event_type)
            span.set_attribute("event.status", event.status)
            
            for key, value in event.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    span.set_attribute(f"metadata.{key}", value)
            
            # Set specific attributes based on event type
            if event.event_type == EventType.LLM_CALL:
                self._set_llm_attributes(span, event)
            elif event.event_type == EventType.TOOL_CALL:
                self._set_tool_attributes(span, event)
            
            # Store for parent lookup
            spans_by_id[event.id] = span
    
    def _set_llm_attributes(self, span: OTelSpan, event: TraceEvent) -> None:
        """Set LLM-specific span attributes."""
        if hasattr(event, "model"):
            span.set_attribute("llm.model", event.model)  # type: ignore
        if hasattr(event, "provider"):
            span.set_attribute("llm.provider", event.provider)  # type: ignore
        if hasattr(event, "tokens_used"):
            tokens = event.tokens_used  # type: ignore
            span.set_attribute("llm.tokens.prompt", tokens.prompt_tokens)
            span.set_attribute("llm.tokens.completion", tokens.completion_tokens)
            span.set_attribute("llm.tokens.total", tokens.total_tokens)
    
    def _set_tool_attributes(self, span: OTelSpan, event: TraceEvent) -> None:
        """Set tool call-specific span attributes."""
        if hasattr(event, "tool_name"):
            span.set_attribute("tool.name", event.tool_name)  # type: ignore
        if hasattr(event, "arguments"):
            # Don't log full arguments, just the keys
            span.set_attribute("tool.argument_keys", list(event.arguments.keys()))  # type: ignore
    
    def shutdown(self) -> None:
        """Shut down the exporter."""
        self._tracer_provider.shutdown()
