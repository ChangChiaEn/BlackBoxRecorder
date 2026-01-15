#!/usr/bin/env python3
"""
Quick script to start the backend API server for development.
"""
import sys
import os

# Add the packages/python directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'packages', 'python')))

from pathlib import Path
from agent_blackbox_recorder.storage.json_file import JsonFileStorage
from agent_blackbox_recorder.server.api import start_server

if __name__ == "__main__":
    storage_path = Path(__file__).parent / "traces"
    storage = JsonFileStorage(storage_path)
    
    print("🚀 Starting AgentBlackBoxRecorder API Server...")
    print(f"📁 Traces directory: {storage_path}")
    print(f"🌐 Server will be available at: http://localhost:8765")
    print(f"📊 API endpoint: http://localhost:8765/api/sessions")
    print("\nPress CTRL+C to stop the server\n")
    
    start_server(storage, host="127.0.0.1", port=8765)

