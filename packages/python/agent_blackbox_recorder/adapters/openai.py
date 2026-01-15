"""
OpenAI adapter for AgentBlackBoxRecorder.

Intercepts OpenAI API calls for automatic tracing.
"""

from typing import TYPE_CHECKING, Any, Optional
import functools

from agent_blackbox_recorder.adapters.base import BaseAdapter
from agent_blackbox_recorder.core.events import LLMCallEvent, TokenUsage

if TYPE_CHECKING:
    from agent_blackbox_recorder.core.recorder import Recorder


class OpenAIAdapter(BaseAdapter):
    """
    Adapter for OpenAI API calls.
    
    Automatically captures all OpenAI API calls including:
    - Chat completions
    - Completions (legacy)
    - Function/tool calls
    - Token usage
    
    Example:
        ```python
        from agent_blackbox_recorder import Recorder
        from agent_blackbox_recorder.adapters import OpenAIAdapter
        
        recorder = Recorder(adapters=[OpenAIAdapter()])
        # All OpenAI calls are now automatically traced
        ```
    """
    
    def __init__(
        self,
        capture_prompts: bool = True,
        capture_responses: bool = True,
        redact_api_key: bool = True,
    ) -> None:
        """
        Initialize the OpenAI adapter.
        
        Args:
            capture_prompts: Whether to capture prompts/messages
            capture_responses: Whether to capture responses
            redact_api_key: Whether to redact API keys from traces
        """
        self._capture_prompts = capture_prompts
        self._capture_responses = capture_responses
        self._redact_api_key = redact_api_key
        self._recorder: Optional["Recorder"] = None
        self._original_funcs: dict[str, Any] = {}
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def version(self) -> str:
        return "0.1.0"
    
    def install(self, recorder: "Recorder") -> None:
        """Install OpenAI instrumentation."""
        self._recorder = recorder
        self._patch_openai()
    
    def uninstall(self) -> None:
        """Remove OpenAI instrumentation."""
        self._unpatch_openai()
        self._recorder = None
    
    def _patch_openai(self) -> None:
        """Patch OpenAI client methods."""
        try:
            import openai
            
            # Patch the new OpenAI client (v1.0+)
            if hasattr(openai, "OpenAI"):
                self._patch_openai_v1()
            
            # Patch the legacy API if present
            if hasattr(openai, "ChatCompletion"):
                self._patch_openai_legacy()
                
        except ImportError:
            # OpenAI not installed
            pass
    
    def _patch_openai_v1(self) -> None:
        """Patch OpenAI v1.0+ client."""
        try:
            from openai.resources.chat import completions as chat_module
            
            original_create = chat_module.Completions.create
            adapter = self
            
            @functools.wraps(original_create)
            def traced_create(self_client: Any, *args: Any, **kwargs: Any) -> Any:
                if adapter._recorder is None:
                    return original_create(self_client, *args, **kwargs)
                
                # Extract request info
                model = kwargs.get("model", "unknown")
                messages = kwargs.get("messages", [])
                
                # Create event
                event = LLMCallEvent(
                    name=f"OpenAI: {model}",
                    trace_id="",
                    model=model,
                    provider="openai",
                    messages=adapter._serialize_messages(messages) if adapter._capture_prompts else None,
                    temperature=kwargs.get("temperature"),
                    max_tokens=kwargs.get("max_tokens"),
                )
                
                adapter._recorder._record_event(event)
                
                try:
                    response = original_create(self_client, *args, **kwargs)
                    
                    # Extract response info
                    if adapter._capture_responses and hasattr(response, "choices"):
                        if response.choices:
                            choice = response.choices[0]
                            if hasattr(choice, "message"):
                                event.response = getattr(choice.message, "content", "")
                                
                                # Check for tool calls
                                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                                    event.tool_calls = [
                                        {
                                            "id": tc.id,
                                            "type": tc.type,
                                            "function": {
                                                "name": tc.function.name,
                                                "arguments": tc.function.arguments,
                                            },
                                        }
                                        for tc in choice.message.tool_calls
                                    ]
                    
                    # Extract token usage
                    if hasattr(response, "usage") and response.usage:
                        event.tokens_used = TokenUsage(
                            prompt_tokens=response.usage.prompt_tokens or 0,
                            completion_tokens=response.usage.completion_tokens or 0,
                            total_tokens=response.usage.total_tokens or 0,
                        )
                    
                    event.complete()
                    return response
                    
                except Exception as e:
                    event.fail(str(e))
                    raise
            
            # Apply patch
            self._original_funcs["chat.completions.create"] = original_create
            chat_module.Completions.create = traced_create  # type: ignore
            
        except (ImportError, AttributeError):
            pass
    
    def _patch_openai_legacy(self) -> None:
        """Patch legacy OpenAI API (pre-v1.0)."""
        try:
            import openai
            
            original_create = openai.ChatCompletion.create
            adapter = self
            
            @functools.wraps(original_create)
            def traced_create(*args: Any, **kwargs: Any) -> Any:
                if adapter._recorder is None:
                    return original_create(*args, **kwargs)
                
                model = kwargs.get("model", "unknown")
                messages = kwargs.get("messages", [])
                
                event = LLMCallEvent(
                    name=f"OpenAI: {model}",
                    trace_id="",
                    model=model,
                    provider="openai",
                    messages=messages if adapter._capture_prompts else None,
                )
                
                adapter._recorder._record_event(event)
                
                try:
                    response = original_create(*args, **kwargs)
                    
                    if adapter._capture_responses:
                        if response.choices:
                            event.response = response.choices[0].message.content
                    
                    if hasattr(response, "usage"):
                        event.tokens_used = TokenUsage(
                            prompt_tokens=response.usage.prompt_tokens,
                            completion_tokens=response.usage.completion_tokens,
                            total_tokens=response.usage.total_tokens,
                        )
                    
                    event.complete()
                    return response
                    
                except Exception as e:
                    event.fail(str(e))
                    raise
            
            self._original_funcs["ChatCompletion.create"] = original_create
            openai.ChatCompletion.create = traced_create  # type: ignore
            
        except (ImportError, AttributeError):
            pass
    
    def _unpatch_openai(self) -> None:
        """Restore original OpenAI methods."""
        try:
            if "chat.completions.create" in self._original_funcs:
                from openai.resources.chat import completions as chat_module
                chat_module.Completions.create = self._original_funcs["chat.completions.create"]
            
            if "ChatCompletion.create" in self._original_funcs:
                import openai
                openai.ChatCompletion.create = self._original_funcs["ChatCompletion.create"]
            
            self._original_funcs.clear()
            
        except ImportError:
            pass
    
    def _serialize_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        """Serialize messages for storage."""
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                # Truncate content if too long
                serialized = msg.copy()
                if "content" in serialized and isinstance(serialized["content"], str):
                    if len(serialized["content"]) > 2000:
                        serialized["content"] = serialized["content"][:2000] + "...[truncated]"
                result.append(serialized)
            elif hasattr(msg, "model_dump"):
                result.append(msg.model_dump())
            else:
                result.append({"raw": str(msg)[:500]})
        return result
