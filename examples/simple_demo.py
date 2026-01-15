import sys
import os

# Add the packages/python directory to the path so we can import the package
# This allows running the example without installing the package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'packages', 'python')))

from agent_blackbox_recorder import Recorder
import time

recorder = Recorder(storage="./traces")

@recorder.trace
def math_agent(question: str):
    print(f"Thinking about: {question}")
    
    # Simulate LLM call
    recorder.record_llm_call(
        model="gpt-4",
        prompt=f"Solve this math problem: {question}",
        response="To solve this, I'll use the calculator tool.",
    )
    
    # Simulate tool call
    recorder.record_tool_call(
        tool_name="calculator",
        arguments={"expression": question},
        result=42,
    )
    
    return 42

if __name__ == "__main__":
    print("Running math agent...")
    result = math_agent("What is 6 * 7?")
    print(f"Result: {result}")
    
    print("\nStarting replay server...")
    # Don't open browser in CI/test env
    recorder.replay(open_browser=False, port=8765) 
