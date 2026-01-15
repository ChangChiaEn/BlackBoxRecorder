@echo off
echo Starting AgentBlackBoxRecorder Development Environment...

echo 1. Installing Python dependencies...
cd packages/python
pip install -e .
cd ../../

echo 2. Installing Web dependencies...
cd packages/web
call npm install
cd ../../

echo 3. Build Web...
cd packages/web
call npm run build
cd ../../

echo 4. Running Demo...
python examples/simple_demo.py
