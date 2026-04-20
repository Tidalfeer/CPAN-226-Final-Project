#!/usr/bin/env python3
"""
Standalone FastAPI Mock Network Server
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import random
import time
import math
from typing import Optional, List, Dict, Any
from datetime import datetime

# ==============================================================================
# FastAPI App Setup
# ==============================================================================

app = FastAPI(
    title="Network Resilience Simulator",
    description="Mock network server for testing autonomous failover agent",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# Network State
# ==============================================================================

class NetworkState:
    def __init__(self):
        self.primary = {
            "condition": "healthy",
            "packet_loss": 0.0,
            "avg_latency_ms": 15.0,
            "jitter_ms": 2.0,
            "bandwidth_mbps": 100.0
        }
        self.backup = {
            "condition": "healthy",
            "packet_loss": 0.0,
            "avg_latency_ms": 20.0,
            "jitter_ms": 3.0,
            "bandwidth_mbps": 50.0
        }
        self.current_active_link = "primary"  # Can be 'primary' or 'backup'
        self.active_scenario = None
        self.scenario_start = 0
        self.scenario_duration = 0
        self.agent_actions = []
        self.manual_override = False
    
    def update_metrics(self):
        """Add random variations to metrics"""
        if self.primary["condition"] != "down":
            self.primary["packet_loss"] = max(0, min(100, 
                self.primary["packet_loss"] + random.uniform(-0.3, 0.3)))
            self.primary["avg_latency_ms"] = max(1,
                self.primary["avg_latency_ms"] + random.uniform(-1, 1))
        
        if self.backup["condition"] != "down":
            self.backup["packet_loss"] = max(0, min(100,
                self.backup["packet_loss"] + random.uniform(-0.2, 0.2)))
            self.backup["avg_latency_ms"] = max(1,
                self.backup["avg_latency_ms"] + random.uniform(-0.5, 0.5))
        
        # Update scenario effects
        if self.active_scenario:
            elapsed = time.time() - self.scenario_start
            if elapsed > self.scenario_duration:
                self.stop_scenario()
            else:
                self._apply_scenario(elapsed)
    
    def _apply_scenario(self, elapsed):
        """Apply active scenario effects"""
        progress = min(elapsed / self.scenario_duration, 1.0)
        
        if self.active_scenario == "primary_degradation":
            self.primary["condition"] = "degraded"
            self.primary["packet_loss"] = 5.0 + progress * 10.0
            self.primary["avg_latency_ms"] = 15.0 + progress * 105.0
        elif self.active_scenario == "primary_outage":
            self.primary["condition"] = "down"
            self.primary["packet_loss"] = 100.0
            self.primary["avg_latency_ms"] = 999.0
        elif self.active_scenario == "intermittent_primary":
            self.primary["condition"] = "intermittent"
            phase = elapsed * 3
            self.primary["packet_loss"] = 20.0 + 15.0 * math.sin(phase)
        elif self.active_scenario == "backup_degradation":
            self.backup["condition"] = "degraded"
            self.backup["packet_loss"] = 10.0 + progress * 20.0
            self.backup["avg_latency_ms"] = 20.0 + progress * 80.0
    
    def start_scenario(self, scenario: str, duration: float = 30.0):
        self.active_scenario = scenario
        self.scenario_start = time.time()
        self.scenario_duration = duration
    
    def stop_scenario(self):
        self.active_scenario = None
        self.primary.update({
            "condition": "healthy",
            "packet_loss": 0.0,
            "avg_latency_ms": 15.0
        })
        self.backup.update({
            "condition": "healthy",
            "packet_loss": 0.0,
            "avg_latency_ms": 20.0
        })
    
    def switch_active_link(self, link: str):
        """Manually switch the active link"""
        if link in ["primary", "backup"]:
            self.current_active_link = link
            self.manual_override = True
            self.agent_actions.append({
                "action": f"manual_switch_to_{link}",
                "active_link": link,
                "timestamp": time.time()
            })
    
    def get_remaining_time(self) -> float:
        if not self.active_scenario:
            return 0
        elapsed = time.time() - self.scenario_start
        return max(0, self.scenario_duration - elapsed)

state = NetworkState()

# ==============================================================================
# Pydantic Models
# ==============================================================================

class LinkCondition(BaseModel):
    link: str
    condition: str

class ScenarioRequest(BaseModel):
    scenario: str
    duration: float = 30.0

class AgentAction(BaseModel):
    action: str
    active_link: str

class SwitchLinkRequest(BaseModel):
    link: str  # 'primary' or 'backup'

# ==============================================================================
# HTML Dashboard
# ==============================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Network Resilience Simulator</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 100%); 
            color: #eee; 
            min-height: 100vh; 
        }
        
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
        }
        
        h1 { 
            color: #00d2ff; 
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        h2 { 
            color: #00d2ff; 
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        
        .card { 
            background: rgba(22, 33, 62, 0.95); 
            padding: 20px; 
            border-radius: 12px; 
            margin: 20px 0; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
            border: 1px solid rgba(0, 210, 255, 0.1);
        }
        
        .metric { 
            display: flex; 
            justify-content: space-between; 
            margin: 10px 0; 
            padding: 10px; 
            background: #0f3460; 
            border-radius: 8px; 
        }
        
        .status { 
            padding: 5px 15px; 
            border-radius: 20px; 
            font-weight: bold; 
            text-transform: uppercase;
            font-size: 0.9em;
        }
        
        .healthy { background: #00aa55; color: white; }
        .degraded { background: #ffa500; color: black; }
        .down { background: #ff4444; color: white; }
        .intermittent { background: #ff8800; color: white; }
        
        .active-link-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #00ff88;
            margin-right: 8px;
            box-shadow: 0 0 10px #00ff88;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        button { 
            background: #00d2ff; 
            color: #1a1a2e; 
            border: none; 
            padding: 10px 20px; 
            margin: 5px; 
            border-radius: 6px; 
            cursor: pointer; 
            font-weight: bold;
            font-size: 0.9em;
            transition: all 0.2s;
        }
        
        button:hover { 
            background: #00b4d8; 
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 210, 255, 0.3);
        }
        
        button.danger { 
            background: #ff6b6b; 
        }
        
        button.danger:hover { 
            background: #ff4444; 
        }
        
        button.success { 
            background: #00aa55; 
            color: white;
        }
        
        button.success:hover { 
            background: #008844; 
        }
        
        button.warning { 
            background: #ffa500; 
        }
        
        button.warning:hover { 
            background: #cc8800; 
        }
        
        .grid-2 { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 20px; 
        }
        
        .api-links { 
            font-size: 0.8em;
            font-weight: normal;
        }
        
        .api-links a { 
            color: #00d2ff; 
            text-decoration: none; 
            margin: 0 10px;
            padding: 5px 10px;
            background: rgba(0, 210, 255, 0.1);
            border-radius: 4px;
        }
        
        .api-links a:hover { 
            background: rgba(0, 210, 255, 0.2);
        }
        
        .active-link-section {
            background: linear-gradient(135deg, #0f3460 0%, #1a1a4e 100%);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .switch-buttons {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        
        .switch-btn {
            flex: 1;
            padding: 12px;
            font-size: 1.1em;
            opacity: 0.7;
        }
        
        .switch-btn.active {
            opacity: 1;
            box-shadow: 0 0 15px currentColor;
        }
        
        .switch-btn.primary.active {
            background: #0066cc;
            color: white;
            box-shadow: 0 0 20px #0066cc;
        }
        
        .switch-btn.backup.active {
            background: #00aa55;
            color: white;
            box-shadow: 0 0 20px #00aa55;
        }
        
        .timestamp {
            font-size: 0.8em;
            color: #888;
            margin-top: 5px;
        }
        
        .action-log {
            max-height: 200px;
            overflow-y: auto;
            background: #0a0a1a;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.9em;
        }
        
        .action-entry {
            padding: 5px;
            border-bottom: 1px solid #1a1a3e;
        }
        
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 8px;
        }
        
        .scenario-badge {
            background: #ffa500;
            color: black;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>
            <span>🌐 Network Resilience Simulator</span>
            <span class="api-links">
                <a href="/docs" target="_blank">📚 API Docs</a>
                <a href="/redoc" target="_blank">📄 ReDoc</a>
                <a href="/health" target="_blank">💚 Health</a>
            </span>
        </h1>
        
        <!-- Active Link Control Section -->
        <div class="card active-link-section">
            <h2 style="margin-top: 0;">
                <span class="active-link-indicator"></span>
                Active Connection Link
            </h2>
            <div style="font-size: 1.2em; margin-bottom: 15px;">
                Currently Active: 
                <strong style="color: #00d2ff; text-transform: uppercase;">
                    {{ current_active_link }}
                </strong>
                {% if manual_override %}
                <span class="badge" style="background: #ffa500; color: black;">MANUAL OVERRIDE</span>
                {% else %}
                <span class="badge" style="background: #00aa55;">AGENT CONTROLLED</span>
                {% endif %}
            </div>
            <div class="switch-buttons">
                <button class="switch-btn primary {% if current_active_link == 'primary' %}active{% endif %}" 
                        onclick="switchActiveLink('primary')">
                    🔵 Switch to PRIMARY
                </button>
                <button class="switch-btn backup {% if current_active_link == 'backup' %}active{% endif %}" 
                        onclick="switchActiveLink('backup')">
                    🟢 Switch to BACKUP
                </button>
            </div>
            <div class="timestamp">
                Last updated: {{ current_time }}
            </div>
        </div>
        
        <!-- Network Metrics -->
        <div class="grid-2">
            <div class="card">
                <h2>🔵 Primary Link (eth0 / Wi-Fi)</h2>
                <div class="metric">
                    <span>Status:</span> 
                    <span class="status {{ primary.condition }}">{{ primary.condition }}</span>
                </div>
                <div class="metric">
                    <span>Packet Loss:</span> 
                    <span>{{ "%.2f"|format(primary.packet_loss) }}%</span>
                </div>
                <div class="metric">
                    <span>Latency:</span> 
                    <span>{{ "%.1f"|format(primary.avg_latency_ms) }} ms</span>
                </div>
                <div class="metric">
                    <span>Jitter:</span> 
                    <span>{{ "%.1f"|format(primary.jitter_ms) }} ms</span>
                </div>
                <div class="metric">
                    <span>Bandwidth:</span> 
                    <span>{{ primary.bandwidth_mbps }} Mbps</span>
                </div>
            </div>
            
            <div class="card">
                <h2>🟢 Backup Link (eth1 / Ethernet)</h2>
                <div class="metric">
                    <span>Status:</span> 
                    <span class="status {{ backup.condition }}">{{ backup.condition }}</span>
                </div>
                <div class="metric">
                    <span>Packet Loss:</span> 
                    <span>{{ "%.2f"|format(backup.packet_loss) }}%</span>
                </div>
                <div class="metric">
                    <span>Latency:</span> 
                    <span>{{ "%.1f"|format(backup.avg_latency_ms) }} ms</span>
                </div>
                <div class="metric">
                    <span>Jitter:</span> 
                    <span>{{ "%.1f"|format(backup.jitter_ms) }} ms</span>
                </div>
                <div class="metric">
                    <span>Bandwidth:</span> 
                    <span>{{ backup.bandwidth_mbps }} Mbps</span>
                </div>
            </div>
        </div>
        
        <!-- Manual Controls -->
        <div class="card">
            <h2>🎮 Manual Link Condition Controls</h2>
            <div style="margin-bottom: 15px;">
                <strong>Primary Link:</strong>
                <button class="success" onclick="setCondition('primary', 'healthy')">✅ Healthy</button>
                <button class="warning" onclick="setCondition('primary', 'degraded')">⚠️ Degraded</button>
                <button class="danger" onclick="setCondition('primary', 'down')">❌ Down</button>
            </div>
            <div>
                <strong>Backup Link:</strong>
                <button class="success" onclick="setCondition('backup', 'healthy')">✅ Healthy</button>
                <button class="warning" onclick="setCondition('backup', 'degraded')">⚠️ Degraded</button>
                <button class="danger" onclick="setCondition('backup', 'down')">❌ Down</button>
            </div>
        </div>
        
        <!-- Scenarios -->
        <div class="card">
            <h2>🎯 Automated Test Scenarios</h2>
            {% if active_scenario %}
            <div style="margin-bottom: 15px; padding: 10px; background: rgba(255, 165, 0, 0.2); border-radius: 8px;">
                <strong>Active Scenario:</strong> 
                <span class="scenario-badge">{{ active_scenario }}</span>
                <span style="margin-left: 10px;">({{ scenario_remaining }}s remaining)</span>
            </div>
            {% endif %}
            <button onclick="startScenario('primary_degradation')">📉 Primary Gradual Degradation</button>
            <button onclick="startScenario('primary_outage')">💥 Primary Outage</button>
            <button onclick="startScenario('intermittent_primary')">📊 Intermittent Primary</button>
            <button onclick="startScenario('backup_degradation')">⚠️ Backup Degradation</button>
            <button class="danger" onclick="stopScenario()">🛑 Stop Scenario</button>
        </div>
        
        <!-- Action Log -->
        <div class="card">
            <h2>📋 Recent Actions</h2>
            <div class="action-log">
                {% for action in agent_actions %}
                <div class="action-entry">
                    [{{ action.time_str }}] 
                    <strong>{{ action.action }}</strong> 
                    → Active: {{ action.active_link }}
                </div>
                {% endfor %}
                {% if not agent_actions %}
                <div style="color: #888; text-align: center; padding: 20px;">
                    No actions recorded yet
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        async function setCondition(link, condition) {
            try {
                const response = await fetch('/api/link/set', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({link, condition})
                });
                if (response.ok) {
                    location.reload();
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to set condition');
            }
        }
        
        async function startScenario(scenario) {
            try {
                const response = await fetch('/api/scenario/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({scenario, duration: 30})
                });
                if (response.ok) {
                    location.reload();
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to start scenario');
            }
        }
        
        async function stopScenario() {
            try {
                const response = await fetch('/api/scenario/stop', {method: 'POST'});
                if (response.ok) {
                    location.reload();
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to stop scenario');
            }
        }
        
        async function switchActiveLink(link) {
            try {
                const response = await fetch('/api/link/switch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({link})
                });
                if (response.ok) {
                    location.reload();
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to switch active link');
            }
        }
        
        // Auto-refresh every 3 seconds
        setTimeout(() => location.reload(), 3000);
    </script>
</body>
</html>
"""

# ==============================================================================
# Routes
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard"""
    from jinja2 import Template
    
    state.update_metrics()
    template = Template(DASHBOARD_HTML)
    
    # Format timestamps for actions
    actions_display = []
    for action in state.agent_actions[-10:]:
        action_copy = action.copy()
        if 'timestamp' in action_copy:
            dt = datetime.fromtimestamp(action_copy['timestamp'])
            action_copy['time_str'] = dt.strftime('%H:%M:%S')
        else:
            action_copy['time_str'] = '--:--:--'
        actions_display.append(action_copy)
    
    return template.render(
        primary=state.primary,
        backup=state.backup,
        current_active_link=state.current_active_link,
        active_scenario=state.active_scenario,
        scenario_remaining=round(state.get_remaining_time(), 1),
        agent_actions=list(reversed(actions_display)),
        manual_override=state.manual_override,
        current_time=datetime.now().strftime('%H:%M:%S')
    )

@app.get("/api/status")
async def get_status():
    """Get complete network status"""
    state.update_metrics()
    return {
        "primary": state.primary,
        "backup": state.backup,
        "current_active_link": state.current_active_link,
        "active_scenario": state.active_scenario,
        "scenario_remaining": round(state.get_remaining_time(), 1),
        "agent_actions": state.agent_actions[-10:],
        "manual_override": state.manual_override
    }

@app.get("/api/health/{interface}")
async def get_health(interface: str):
    """Get link health - called by agent"""
    state.update_metrics()
    if interface in ["primary", "eth0", "Wi-Fi"]:
        return state.primary
    return state.backup

@app.post("/api/link/set")
async def set_link(req: LinkCondition):
    """Manually set link condition"""
    target = state.primary if req.link == "primary" else state.backup
    target["condition"] = req.condition
    
    if req.condition == "down":
        target["packet_loss"] = 100.0
        target["avg_latency_ms"] = 999.0
    elif req.condition == "degraded":
        target["packet_loss"] = 15.0
        target["avg_latency_ms"] = 120.0
    else:
        target["packet_loss"] = 0.0
        target["avg_latency_ms"] = 15.0 if req.link == "primary" else 20.0
    
    state.agent_actions.append({
        "action": f"manual_set_{req.link}_{req.condition}",
        "active_link": state.current_active_link,
        "timestamp": time.time()
    })
    
    return {"status": "success"}

@app.post("/api/link/switch")
async def switch_link(req: SwitchLinkRequest):
    """Manually switch active link"""
    state.switch_active_link(req.link)
    return {"status": "success", "active_link": state.current_active_link}

@app.post("/api/scenario/start")
async def start_scenario(req: ScenarioRequest):
    """Start test scenario"""
    state.start_scenario(req.scenario, req.duration)
    state.manual_override = False  # Agent will take over
    state.agent_actions.append({
        "action": f"scenario_start_{req.scenario}",
        "active_link": state.current_active_link,
        "timestamp": time.time()
    })
    return {"status": "success"}

@app.post("/api/scenario/stop")
async def stop_scenario():
    """Stop active scenario"""
    state.stop_scenario()
    state.agent_actions.append({
        "action": "scenario_stop",
        "active_link": state.current_active_link,
        "timestamp": time.time()
    })
    return {"status": "success"}

@app.post("/api/agent/action")
async def record_action(req: AgentAction):
    """Record agent action"""
    state.agent_actions.append({
        "action": req.action,
        "active_link": req.active_link,
        "timestamp": time.time()
    })
    state.current_active_link = req.active_link
    state.manual_override = False  # Agent is in control
    
    if len(state.agent_actions) > 50:
        state.agent_actions = state.agent_actions[-50:]
    
    return {"status": "success"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/api/reset")
async def reset():
    """Reset everything to default"""
    state.__init__()
    return {"status": "success"}

# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  🌐 FASTAPI NETWORK SIMULATOR v2.0")
    print("="*60)
    print("  📡 Server: http://127.0.0.1:5001")
    print("  🎮 Dashboard: http://127.0.0.1:5001")
    print("  📚 API Docs: http://127.0.0.1:5001/docs")
    print("  💚 Health: http://127.0.0.1:5001/health")
    print("="*60)
    print("  ✨ New Features:")
    print("     - Manual link switching")
    print("     - Active link indicator")
    print("     - Override status display")
    print("="*60)
    print("  Press Ctrl+C to stop\n")
    
    uvicorn.run(app, host="127.0.0.1", port=5001, log_level="info")