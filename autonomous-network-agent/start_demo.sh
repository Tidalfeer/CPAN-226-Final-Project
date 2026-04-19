#!/bin/bash
# Start the complete demo environment for Autonomous Network Resilience Agent
# Works on macOS, Linux, and Windows WSL

set -e  # Exit on error

echo " Starting Autonomous Network Resilience Agent Demo"
echo "====================================================="

# =============================================================================
# STEP 1: Check Python and Install Dependencies
# =============================================================================

echo ""
echo " Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo " Python 3 is not installed!"
    echo "Please install Python 3.8 or higher from: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo " Python $PYTHON_VERSION found"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo " pip3 is not installed!"
    echo "Please install pip: python3 -m ensurepip --upgrade"
    exit 1
fi

# Install dependencies
echo ""
echo " Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo " Dependencies installed successfully"
else
    echo " Failed to install dependencies"
    exit 1
fi

# =============================================================================
# STEP 2: Check/Create config.yaml
# =============================================================================

echo ""
echo "Checking configuration..."

if [ ! -f "config.yaml" ]; then
    echo "Creating default config.yaml with mock server enabled..."
    cat > config.yaml << 'EOF'
network:
  primary_interface: "eth0"
  backup_interface: "eth1"
  primary_gateway: "192.168.1.1"
  backup_gateway: "192.168.2.1"
  test_target: "8.8.8.8"

thresholds:
  packet_loss_max: 5.0
  latency_max_ms: 100.0
  jitter_max_ms: 30.0

agent:
  check_interval_seconds: 5
  stability_period_seconds: 15
  use_local_llm: true
  llm_model: "llama3.2:1b"
  verbose: true

mock_server:
  enabled: true
  url: "http://localhost:5000"
EOF
    echo "config.yaml created"
fi

# Ensure mock server is enabled
echo " Ensuring mock server is enabled in config.yaml..."
python3 -c "
import yaml
try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
except:
    config = {}
if 'mock_server' not in config:
    config['mock_server'] = {}
config['mock_server']['enabled'] = True
config['mock_server']['url'] = 'http://localhost:5000'
with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)
print(' Mock server enabled')
" || echo "Could not update config.yaml"

# =============================================================================
# STEP 3: Check Ollama (Local LLM)
# =============================================================================

echo ""
echo "Checking Ollama..."

if ! command -v ollama &> /dev/null; then
    echo " Ollama is not installed!"
    echo "Please install Ollama from: https://ollama.com"
    echo ""
    echo "For this demo, you can also:"
    echo "  1. Install Ollama now and re-run"
    echo "  2. Or skip this demo for now"
    exit 1
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo " Ollama is not running. Starting Ollama..."
    ollama serve &
    OLLAMA_PID=$!
    echo "Waiting for Ollama to start..."
    sleep 5
fi

# Pull the required model
echo " Checking for LLM model (llama3.2:1b)..."
if ollama list 2>/dev/null | grep -q "llama3.2:1b"; then
    echo "llama3.2:1b model already available"
else
    echo " Downloading llama3.2:1b model (this may take a few minutes)..."
    ollama pull llama3.2:1b
    echo " Model downloaded"
fi

# =============================================================================
# STEP 4: Create Required Directories
# =============================================================================

echo ""
echo "Creating required directories..."
mkdir -p logs
mkdir -p mock_network_server/templates
echo "Directories created"

# =============================================================================
# STEP 5: Start Mock Network Server
# =============================================================================

echo ""
echo "Starting Mock Network Server..."

# Start the server in background
python3 -m mock_network_server.server &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for mock server to start..."
sleep 3

# Check if server started
if curl -s http://localhost:5000/api/status > /dev/null 2>&1; then
    echo " Mock server running at http://localhost:5000"
else
    echo " Mock server may not have started properly"
fi

# =============================================================================
# STEP 6: Open Dashboard
# =============================================================================

echo ""
echo " Opening dashboard..."

if command -v open &> /dev/null; then
    open http://localhost:5000
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5000
else
    echo "Dashboard available at: http://localhost:5000"
fi

# =============================================================================
# STEP 7: Run the Agent
# =============================================================================

echo ""
echo "════════════════════════════════════════════════════════════"
echo "DEMO ENVIRONMENT READY!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Dashboard: http://localhost:5000"
echo "Logs: tail -f logs/agent.log"
echo "Agent starting in 3 seconds..."
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

sleep 3

# Trap Ctrl+C to cleanup
cleanup() {
    echo ""
    echo "Stopping services..."
    
    # Kill the mock server
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null
        echo "Mock server stopped"
    fi
    
    # Kill Ollama if we started it
    if [ ! -z "$OLLAMA_PID" ]; then
        kill $OLLAMA_PID 2>/dev/null
        echo "Ollama stopped"
    fi
    
    echo "Demo complete."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Run the agent
python3 agent/main.py --interval 5

# Cleanup on normal exit
cleanup