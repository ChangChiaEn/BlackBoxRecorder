"""
State snapshot engine for AgentBlackBoxRecorder.

Handles serialization and restoration of agent state for checkpoints
and takeover mode.
"""

import pickle
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar
import base64

from pydantic import BaseModel

from agent_blackbox_recorder.core.events import StateSnapshot


T = TypeVar("T")


class SnapshotEngine:
    """
    Engine for capturing and restoring agent state.
    
    Supports multiple serialization strategies:
    - JSON (preferred, human-readable)
    - Pickle (fallback for complex objects)
    - Custom serializers (for framework-specific objects)
    """
    
    def __init__(self) -> None:
        """Initialize the snapshot engine."""
        self._custom_serializers: dict[type, Callable[[Any], dict[str, Any]]] = {}
        self._custom_deserializers: dict[str, Callable[[dict[str, Any]], Any]] = {}
    
    def register_serializer(
        self,
        type_: type,
        serializer: Callable[[Any], dict[str, Any]],
        deserializer: Callable[[dict[str, Any]], Any],
    ) -> None:
        """
        Register a custom serializer for a specific type.
        
        Args:
            type_: The type to serialize
            serializer: Function to convert object to dict
            deserializer: Function to restore object from dict
        """
        self._custom_serializers[type_] = serializer
        self._custom_deserializers[type_.__name__] = deserializer
    
    def capture(
        self,
        state: Any,
        trace_id: str,
        event_id: str,
        checkpoint_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> StateSnapshot:
        """
        Capture a snapshot of the given state.
        
        Args:
            state: The state object to capture
            trace_id: ID of the current trace
            event_id: ID of the event triggering this snapshot
            checkpoint_name: Optional name for the checkpoint
            description: Optional description
        
        Returns:
            A StateSnapshot object containing the serialized state
        """
        warnings: list[str] = []
        serialized_state, is_restorable = self._serialize_state(state, warnings)
        
        return StateSnapshot(
            trace_id=trace_id,
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            state=serialized_state,
            state_type=type(state).__name__,
            restorable=is_restorable,
            checkpoint_name=checkpoint_name,
            description=description,
            serialization_warnings=warnings,
        )
    
    def restore(self, snapshot: StateSnapshot, target_type: Optional[type[T]] = None) -> T | dict[str, Any]:
        """
        Restore state from a snapshot.
        
        Args:
            snapshot: The snapshot to restore from
            target_type: Optional type to cast the result to
        
        Returns:
            The restored state object
        """
        state = self._deserialize_state(snapshot.state, snapshot.state_type)
        
        if target_type is not None and not isinstance(state, target_type):
            # Try to construct the target type from the state dict
            if isinstance(state, dict):
                if issubclass(target_type, BaseModel):
                    return target_type.model_validate(state)
                elif hasattr(target_type, "__init__"):
                    return target_type(**state)  # type: ignore
        
        return state  # type: ignore
    
    def _serialize_state(
        self,
        state: Any,
        warnings: list[str],
        path: str = "root",
        max_depth: int = 10,
    ) -> tuple[dict[str, Any], bool]:
        """
        Serialize state to a dictionary.
        
        Returns:
            Tuple of (serialized_state, is_restorable)
        """
        if max_depth <= 0:
            warnings.append(f"{path}: max depth reached")
            return {"_error": "max_depth_reached", "_path": path}, False
        
        is_restorable = True
        
        # Check for custom serializer
        for type_, serializer in self._custom_serializers.items():
            if isinstance(state, type_):
                try:
                    serialized = serializer(state)
                    serialized["_custom_type"] = type_.__name__
                    return serialized, True
                except Exception as e:
                    warnings.append(f"{path}: custom serializer failed: {e}")
        
        # None
        if state is None:
            return {"_value": None, "_type": "NoneType"}, True
        
        # Primitives
        if isinstance(state, (bool, int, float, str)):
            return {"_value": state, "_type": type(state).__name__}, True
        
        # Lists/Tuples
        if isinstance(state, (list, tuple)):
            items = []
            for i, item in enumerate(state):
                serialized, restorable = self._serialize_state(
                    item, warnings, f"{path}[{i}]", max_depth - 1
                )
                items.append(serialized)
                is_restorable = is_restorable and restorable
            return {
                "_value": items,
                "_type": type(state).__name__,
            }, is_restorable
        
        # Dicts
        if isinstance(state, dict):
            items = {}
            for key, value in state.items():
                serialized, restorable = self._serialize_state(
                    value, warnings, f"{path}.{key}", max_depth - 1
                )
                items[str(key)] = serialized
                is_restorable = is_restorable and restorable
            return {
                "_value": items,
                "_type": "dict",
            }, is_restorable
        
        # Pydantic models
        if isinstance(state, BaseModel):
            try:
                return {
                    "_value": state.model_dump(),
                    "_type": type(state).__name__,
                    "_pydantic": True,
                    "_module": type(state).__module__,
                }, True
            except Exception as e:
                warnings.append(f"{path}: Pydantic serialization failed: {e}")
        
        # Objects with __dict__
        if hasattr(state, "__dict__"):
            try:
                obj_dict = {}
                for key, value in state.__dict__.items():
                    if not key.startswith("_"):
                        serialized, restorable = self._serialize_state(
                            value, warnings, f"{path}.{key}", max_depth - 1
                        )
                        obj_dict[key] = serialized
                        is_restorable = is_restorable and restorable
                
                return {
                    "_value": obj_dict,
                    "_type": type(state).__name__,
                    "_module": type(state).__module__,
                }, is_restorable
            except Exception as e:
                warnings.append(f"{path}: dict serialization failed: {e}")
        
        # Fallback: try pickle
        try:
            pickled = pickle.dumps(state)
            encoded = base64.b64encode(pickled).decode("utf-8")
            return {
                "_pickled": encoded,
                "_type": type(state).__name__,
            }, True
        except Exception as e:
            warnings.append(f"{path}: pickle fallback failed: {e}")
        
        # Last resort: string representation
        return {
            "_str": str(state)[:500],
            "_type": type(state).__name__,
            "_unserializable": True,
        }, False
    
    def _deserialize_state(self, data: dict[str, Any], type_name: str) -> Any:
        """Deserialize state from a dictionary."""
        
        # Check for custom deserializer
        if "_custom_type" in data:
            custom_type = data["_custom_type"]
            if custom_type in self._custom_deserializers:
                return self._custom_deserializers[custom_type](data)
        
        # Pickled data
        if "_pickled" in data:
            decoded = base64.b64decode(data["_pickled"].encode("utf-8"))
            return pickle.loads(decoded)
        
        # Unserializable
        if data.get("_unserializable"):
            return data.get("_str", f"<{type_name}: unserializable>")
        
        # Get the value
        value = data.get("_value")
        stored_type = data.get("_type", "unknown")
        
        # None
        if stored_type == "NoneType":
            return None
        
        # Primitives
        if stored_type in ("bool", "int", "float", "str"):
            return value
        
        # Lists/Tuples
        if stored_type in ("list", "tuple"):
            items = [self._deserialize_state(item, "unknown") for item in value]
            return tuple(items) if stored_type == "tuple" else items
        
        # Dicts
        if stored_type == "dict":
            return {
                key: self._deserialize_state(item, "unknown")
                for key, item in value.items()
            }
        
        # Pydantic models (return as dict - caller can reconstruct if needed)
        if data.get("_pydantic"):
            return value
        
        # Other objects (return as dict)
        if isinstance(value, dict):
            return {
                key: self._deserialize_state(item, "unknown") 
                if isinstance(item, dict) and "_value" in item 
                else item
                for key, item in value.items()
            }
        
        return value
    
    def diff(self, snapshot1: StateSnapshot, snapshot2: StateSnapshot) -> dict[str, Any]:
        """
        Compare two snapshots and return the differences.
        
        Args:
            snapshot1: The first snapshot (earlier)
            snapshot2: The second snapshot (later)
        
        Returns:
            Dictionary describing the changes
        """
        return self._diff_values(
            snapshot1.state,
            snapshot2.state,
            path="root",
        )
    
    def _diff_values(
        self,
        value1: Any,
        value2: Any,
        path: str,
    ) -> dict[str, Any]:
        """Recursively diff two values."""
        
        # Same value
        if value1 == value2:
            return {}
        
        changes: dict[str, Any] = {}
        
        # Type changed
        type1 = value1.get("_type") if isinstance(value1, dict) else type(value1).__name__
        type2 = value2.get("_type") if isinstance(value2, dict) else type(value2).__name__
        
        if type1 != type2:
            return {
                path: {
                    "type": "type_changed",
                    "from": type1,
                    "to": type2,
                }
            }
        
        # Dicts - compare nested
        if isinstance(value1, dict) and isinstance(value2, dict):
            v1 = value1.get("_value", value1)
            v2 = value2.get("_value", value2)
            
            if isinstance(v1, dict) and isinstance(v2, dict):
                all_keys = set(v1.keys()) | set(v2.keys())
                for key in all_keys:
                    if key not in v1:
                        changes[f"{path}.{key}"] = {"type": "added", "value": v2[key]}
                    elif key not in v2:
                        changes[f"{path}.{key}"] = {"type": "removed", "value": v1[key]}
                    else:
                        nested_changes = self._diff_values(v1[key], v2[key], f"{path}.{key}")
                        changes.update(nested_changes)
            else:
                changes[path] = {"type": "changed", "from": v1, "to": v2}
        else:
            # Simple value change
            changes[path] = {"type": "changed", "from": value1, "to": value2}
        
        return changes
