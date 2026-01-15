# AgentBlackBoxRecorder Python SDK

The Python SDK for AgentBlackBoxRecorder - capture, replay, and debug your AI agents.

## Installation

```bash
pip install agent-blackbox-recorder
```

## Quick Start

```python
from agent_blackbox_recorder import Recorder

recorder = Recorder(storage="./traces")

@recorder.trace
def my_agent(query: str):
    # Your agent logic
    pass

# Run and debug
my_agent("Hello!")
recorder.replay()
```

See the [main README](../../README.md) for full documentation.
