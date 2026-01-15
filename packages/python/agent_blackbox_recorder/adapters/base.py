"""
Base adapter interface for AgentBlackBoxRecorder.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from agent_blackbox_recorder.core.recorder import Recorder


T = TypeVar("T")


class BaseAdapter(ABC):
    """
    Base class for framework adapters.
    
    Adapters provide framework-specific instrumentation for capturing
    traces from different agent frameworks (LangGraph, CrewAI, etc.).
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the framework this adapter supports."""
        ...
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Version of the adapter."""
        ...
    
    @abstractmethod
    def install(self, recorder: "Recorder") -> None:
        """
        Install the adapter hooks.
        
        This method is called when the adapter is added to a Recorder.
        It should set up any necessary instrumentation.
        
        Args:
            recorder: The Recorder instance to attach to
        """
        ...
    
    @abstractmethod
    def uninstall(self) -> None:
        """
        Remove the adapter hooks.
        
        This should clean up any modifications made by install().
        """
        ...
    
    def wrap(self, runnable: T, recorder: "Recorder") -> T:
        """
        Wrap a runnable for automatic tracing.
        
        The default implementation returns the runnable unchanged.
        Override this to provide framework-specific wrapping.
        
        Args:
            runnable: The object to wrap
            recorder: The Recorder to use for tracing
        
        Returns:
            The wrapped runnable
        """
        return runnable
