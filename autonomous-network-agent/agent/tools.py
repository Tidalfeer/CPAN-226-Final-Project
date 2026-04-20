"""
Network Tools Module for Autonomous Network Resilience Agent
"""

import subprocess
import sys
import time
import platform
import os
import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from smolagents import tool

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from pythonping import ping
    PYTHONPING_AVAILABLE = True
except ImportError:
    PYTHONPING_AVAILABLE = False

from .utils import print_status

@dataclass
class LinkMetrics:
    """Structured representation of network link metrics."""
    packet_loss: float
    avg_latency_ms: float
    jitter_ms: float
    status: str
    bandwidth_mbps: float = 100.0
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        """Convert metrics to dictionary."""
        return asdict(self)

class NetworkTools:
    """Collection of network tools exposed to the AI agent."""
    
    def __init__(self, config: dict):
        """Initialize network tools with configuration."""
        self.config = config
        
        # Network configuration
        self.primary_if = config['network']['primary_interface']
        self.backup_if = config['network']['backup_interface']
        self.primary_gw = config['network'].get('primary_gateway', '192.168.1.1')
        self.backup_gw = config['network'].get('backup_gateway', '192.168.2.1')
        self.test_target = config['network']['test_target']
        
        # Thresholds
        self.packet_loss_max = config['thresholds']['packet_loss_max']
        self.latency_max = config['thresholds']['latency_max_ms']
        self.jitter_max = config['thresholds'].get('jitter_max_ms', 30.0)
        
        # Agent state
        self.current_active = "primary"
        self.failover_count = 0
        self.last_failover_time = 0.0
        self.stability_period = config['agent'].get('stability_period_seconds', 30)
        
        # Mock server configuration
        mock_config = config.get('mock_server', {})
        config_enabled = mock_config.get('enabled', False)
        env_enabled = os.environ.get('USE_MOCK_SERVER', '').lower() == 'true'
        
        self.use_mock_server = env_enabled or config_enabled
        self.mock_server_url = os.environ.get('MOCK_SERVER_URL', 
                              mock_config.get('url', 'http://127.0.0.1:5001'))
        
        # OS detection
        self.os_type = platform.system()
        
        # Setup logging
        self.logger = logging.getLogger("NetworkAgent.Tools")
        
        # Initialize
        self._log_initialization()
        
        # Verify mock server if enabled
        if self.use_mock_server:
            self._verify_mock_server()
    
    def _log_initialization(self):
        """Log initialization details."""
        print_status(f"OS Detected: {self.os_type}", "info")
        print_status(f"Primary: {self.primary_if}", "info")
        print_status(f"Backup: {self.backup_if}", "info")
        print_status(f"Test target: {self.test_target}", "info")
        print_status(f"Thresholds: Loss={self.packet_loss_max}%, Latency={self.latency_max}ms", "info")
        
        if self.use_mock_server:
            print_status("MOCK SERVER MODE ENABLED", "action")
            print_status(f"URL: {self.mock_server_url}", "info")
        else:
            print_status("PRODUCTION MODE - Real network measurements", "warning")
    
    def _verify_mock_server(self):
        """Verify that the mock server is accessible."""
        if not REQUESTS_AVAILABLE:
            print_status("'requests' library not installed - mock server disabled", "error")
            self.use_mock_server = False
            return
        
        try:
            response = requests.get(f"{self.mock_server_url}/health", timeout=3)
            if response.status_code == 200:
                print_status(f"Connected to mock server", "success")
            else:
                print_status(f"Mock server returned HTTP {response.status_code}", "warning")
        except requests.exceptions.ConnectionError:
            print_status(f"Cannot connect to mock server at {self.mock_server_url}", "error")
            print_status("Make sure run_mock_server.py is running", "info")
            self.use_mock_server = False
        except Exception as e:
            print_status(f"Mock server error: {e}", "warning")
    
    def get_link_metrics(self, interface: str) -> LinkMetrics:
        """
        Get comprehensive metrics for a network interface.
        
        In mock mode: Fetches from FastAPI mock server
        In production mode: Performs real ICMP measurements
        """
        print_status(f"Probing: {interface}", "action")
        
        if self.use_mock_server:
            return self._get_mock_metrics(interface)
        else:
            return self._get_real_metrics(interface)
    
    def _get_mock_metrics(self, interface: str) -> LinkMetrics:
        """Get metrics from mock server."""
        # Map interface names for mock server
        if interface == self.primary_if:
            mock_interface = "primary"
        elif interface == self.backup_if:
            mock_interface = "backup"
        else:
            mock_interface = interface
        
        url = f"{self.mock_server_url}/api/health/{mock_interface}"
        
        try:
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract fields - mock server uses "condition" not "status"
                condition = data.get('condition', 'unknown')
                packet_loss = float(data.get('packet_loss', 0))
                avg_latency_ms = float(data.get('avg_latency_ms', 0))
                jitter_ms = float(data.get('jitter_ms', 0))
                bandwidth_mbps = float(data.get('bandwidth_mbps', 100.0))
                
                print_status(f"  Response: {condition.upper()} (loss={packet_loss:.1f}%, lat={avg_latency_ms:.1f}ms)", 
                           "success" if condition == "healthy" else "warning")
                
                return LinkMetrics(
                    packet_loss=packet_loss,
                    avg_latency_ms=avg_latency_ms,
                    jitter_ms=jitter_ms,
                    status=condition,  # Store condition as status
                    bandwidth_mbps=bandwidth_mbps
                )
            else:
                print_status(f"  Mock server HTTP error: {response.status_code}", "error")
                
        except requests.exceptions.ConnectionError:
            print_status(f"  Mock server connection failed", "error")
        except requests.exceptions.Timeout:
            print_status(f"  Mock server timeout", "error")
        except Exception as e:
            print_status(f"  Mock server error: {e}", "error")
        
        # Fallback to healthy
        print_status(f"  Using fallback healthy metrics", "warning")
        return LinkMetrics(
            packet_loss=0.0,
            avg_latency_ms=15.0,
            jitter_ms=2.0,
            status="healthy"
        )
    
    def _get_real_metrics(self, interface: str) -> LinkMetrics:
        """Perform real network measurements."""
        packet_loss = self._measure_packet_loss(interface)
        latency_data = self._measure_latency(interface)
        
        # Determine status
        if packet_loss >= 100.0 or latency_data['avg_latency_ms'] >= 999.0:
            status = "down"
        elif packet_loss > self.packet_loss_max or latency_data['avg_latency_ms'] > self.latency_max:
            status = "degraded"
        else:
            status = "healthy"
        
        print_status(f"  Result: {status.upper()} (loss={packet_loss:.1f}%, lat={latency_data['avg_latency_ms']:.1f}ms)", 
                   "success" if status == "healthy" else "warning")
        
        return LinkMetrics(
            packet_loss=packet_loss,
            avg_latency_ms=latency_data['avg_latency_ms'],
            jitter_ms=latency_data['jitter_ms'],
            status=status
        )
    
    def _measure_packet_loss(self, interface: str, count: int = 4) -> float:
        """Measure packet loss using system ping."""
        try:
            if self.os_type == "Windows":
                cmd = ["ping", "-n", str(count), self.test_target]
            elif self.os_type == "Darwin":
                cmd = ["ping", "-c", str(count), "-S", interface, self.test_target]
            else:
                cmd = ["ping", "-c", str(count), "-I", interface, self.test_target]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=count * 2)
            output = result.stdout + result.stderr
            
            if "100% packet loss" in output or "100% loss" in output:
                return 100.0
            elif "0% packet loss" in output or "0% loss" in output:
                return 0.0
            
            match = re.search(r'(\d+(?:\.\d+)?)%', output)
            if match:
                return float(match.group(1))
            
            return 0.0 if result.returncode == 0 else 100.0
            
        except Exception as e:
            self.logger.error(f"Ping error: {e}")
            return 100.0
    
    def _measure_latency(self, interface: str, count: int = 4) -> Dict[str, float]:
        """Measure latency using pythonping or system ping."""
        if PYTHONPING_AVAILABLE:
            try:
                response_list = ping(self.test_target, count=count, timeout=2, verbose=False)
                rtts = [resp.time_elapsed_ms for resp in response_list._responses if resp.success]
                
                if not rtts:
                    return {"avg_latency_ms": 999.0, "jitter_ms": 999.0}
                
                avg = sum(rtts) / len(rtts)
                jitter = sum(abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))) / (len(rtts) - 1) if len(rtts) > 1 else 0.0
                
                return {"avg_latency_ms": round(avg, 2), "jitter_ms": round(jitter, 2)}
            except Exception as e:
                self.logger.warning(f"pythonping failed: {e}")
        
        # Fallback to system ping
        try:
            if self.os_type == "Windows":
                cmd = ["ping", "-n", str(count), self.test_target]
            elif self.os_type == "Darwin":
                cmd = ["ping", "-c", str(count), "-S", interface, self.test_target]
            else:
                cmd = ["ping", "-c", str(count), "-I", interface, self.test_target]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = result.stdout
            
            if self.os_type == "Windows":
                match = re.search(r'Average = (\d+)ms', output)
                if match:
                    return {"avg_latency_ms": float(match.group(1)), "jitter_ms": 0.0}
            else:
                match = re.search(r'min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/([\d.]+)', output)
                if match:
                    return {"avg_latency_ms": float(match.group(1)), "jitter_ms": float(match.group(2))}
                match = re.search(r'avg = ([\d.]+)', output)
                if match:
                    return {"avg_latency_ms": float(match.group(1)), "jitter_ms": 0.0}
            
            return {"avg_latency_ms": 999.0, "jitter_ms": 999.0}
            
        except Exception as e:
            self.logger.error(f"Latency measurement error: {e}")
            return {"avg_latency_ms": 999.0, "jitter_ms": 999.0}
    
    def execute_failover(self) -> str:
        """Execute failover from primary to backup link."""
        print_status(f"FAILOVER: {self.primary_if} -> {self.backup_if}", "warning")
        
        if not self.use_mock_server:
            self._execute_real_failover()
        else:
            self._simulate_failover()
        
        self.current_active = "backup"
        self.failover_count += 1
        self.last_failover_time = time.time()
        
        self._notify_mock_server('failover', 'backup')
        
        result = f"Traffic routing through backup interface '{self.backup_if}'. Failover count: {self.failover_count}"
        print_status(result, "success")
        self.logger.info(f"Failover executed. Count: {self.failover_count}")
        
        return result
    
    def _execute_real_failover(self):
        """Execute actual routing table changes."""
        if self.os_type == "Windows":
            cmd = f"route change 0.0.0.0 mask 0.0.0.0 {self.backup_gw}"
        else:
            cmd = f"ip route replace default via {self.backup_gw} dev {self.backup_if}"
        print_status(f"Command: {cmd}", "info")
    
    def _simulate_failover(self):
        """Simulate failover for testing."""
        print_status(f"[SIMULATED] Routing switched to backup", "info")
    
    def execute_failback(self) -> str:
        """Execute failback from backup to primary link."""
        print_status(f"FAILBACK: {self.backup_if} -> {self.primary_if}", "action")
        
        if not self.use_mock_server:
            self._execute_real_failback()
        else:
            self._simulate_failback()
        
        self.current_active = "primary"
        
        self._notify_mock_server('failback', 'primary')
        
        result = f"Traffic routing through primary interface '{self.primary_if}'"
        print_status(result, "success")
        self.logger.info("Failback executed")
        
        return result
    
    def _execute_real_failback(self):
        """Execute actual routing table changes."""
        if self.os_type == "Windows":
            cmd = f"route change 0.0.0.0 mask 0.0.0.0 {self.primary_gw}"
        else:
            cmd = f"ip route replace default via {self.primary_gw} dev {self.primary_if}"
        print_status(f"Command: {cmd}", "info")
    
    def _simulate_failback(self):
        """Simulate failback for testing."""
        print_status(f"[SIMULATED] Routing switched to primary", "info")
    
    def _notify_mock_server(self, action: str, active_link: str):
        """Notify mock server of agent action."""
        if not self.use_mock_server:
            return
        
        try:
            requests.post(
                f"{self.mock_server_url}/api/agent/action",
                json={'action': action, 'active_link': active_link},
                timeout=2
            )
        except Exception:
            pass
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current state of the network resilience agent."""
        time_since = 0.0
        if self.last_failover_time > 0:
            time_since = time.time() - self.last_failover_time
        
        return {
            "active_link": self.current_active,
            "primary_interface": self.primary_if,
            "backup_interface": self.backup_if,
            "failover_count": self.failover_count,
            "time_since_last_failover": round(time_since, 1),
            "stability_achieved": time_since >= self.stability_period,
            "mode": "test" if self.use_mock_server else "production",
            "thresholds": {
                "packet_loss_max": self.packet_loss_max,
                "latency_max_ms": self.latency_max,
                "jitter_max_ms": self.jitter_max
            }
        }


# ==============================================================================
# Global Network Tools Instance
# ==============================================================================

_network_tools: Optional[NetworkTools] = None


def init_tools(config: dict) -> NetworkTools:
    """Initialize the network tools singleton."""
    global _network_tools
    _network_tools = NetworkTools(config)
    return _network_tools


def get_tools() -> Optional[NetworkTools]:
    """Get the initialized network tools instance."""
    return _network_tools


# ==============================================================================
# Tools Exposed to AI Agent
# ==============================================================================

@tool
def get_link_metrics(interface: str) -> dict:
    """
    Analyzes the health of a specific network interface.
    
    Use this tool to check if a network link is experiencing degradation.
    This should be called before making any failover decisions.
    
    Args:
        interface: The network interface to test (e.g., 'eth0', 'Wi-Fi', 'en0')
    
    Returns:
        A dictionary containing:
        - packet_loss: Percentage of packet loss (0-100%)
        - avg_latency_ms: Average round-trip time in milliseconds
        - jitter_ms: Variation in latency (jitter) in milliseconds
        - status: 'healthy', 'degraded', or 'down'
        - timestamp: Unix timestamp of measurement
    """
    global _network_tools
    if _network_tools is None:
        return {"error": "Network tools not initialized"}
    return _network_tools.get_link_metrics(interface).to_dict()


@tool
def execute_failover() -> str:
    """
    Orchestrates the cut-over from the primary link to the backup link.
    
    Use this tool when the primary link is degraded and you need to
    switch traffic to the backup connection. This action is logged
    and increments the failover counter.
    
    Returns:
        A confirmation message indicating success or failure.
    """
    global _network_tools
    if _network_tools is None:
        return "ERROR: Network tools not initialized"
    return _network_tools.execute_failover()


@tool
def execute_failback() -> str:
    """
    Reverts to the primary link after it has been stable.
    
    Use this tool when the primary link has been consistently healthy
    for the required stability period. This restores normal operation.
    
    Returns:
        A confirmation message indicating success or failure.
    """
    global _network_tools
    if _network_tools is None:
        return "ERROR: Network tools not initialized"
    return _network_tools.execute_failback()


@tool
def get_current_status() -> dict:
    """
    Returns the current state of the network resilience agent.
    
    Use this tool at the beginning of each decision cycle to understand
    the current operational context before analyzing metrics.
    
    Returns:
        A dictionary containing:
        - active_link: Which link is currently active ('primary' or 'backup')
        - failover_count: Number of failovers performed this session
        - time_since_last_failover: Seconds since last state change
        - stability_achieved: Whether stability period has elapsed
        - mode: 'test' or 'production'
    """
    global _network_tools
    if _network_tools is None:
        return {"error": "Network tools not initialized"}
    return _network_tools.get_current_status()


@tool
def wait_and_observe(seconds: int = 10) -> str:
    """
    Pause decision-making to gather more data.
    
    Use this tool when metrics are borderline or fluctuating.
    This prevents unnecessary failover flapping.
    
    Args:
        seconds: Number of seconds to wait (default: 10)
    
    Returns:
        Confirmation message
    """
    time.sleep(seconds)
    return f"Waited {seconds} seconds for additional observation."


# ==============================================================================
# Utility Functions
# ==============================================================================

def get_tool_list() -> List[str]:
    """Return list of available tool names."""
    return [
        "get_link_metrics",
        "execute_failover",
        "execute_failback",
        "get_current_status",
        "wait_and_observe"
    ]


def get_tool_descriptions() -> Dict[str, str]:
    """Return descriptions of all available tools."""
    return {
        "get_link_metrics": "Measure packet loss, latency, and jitter for a network interface",
        "execute_failover": "Switch traffic from primary to backup link",
        "execute_failback": "Switch traffic from backup to primary link",
        "get_current_status": "Get current agent state and failover history",
        "wait_and_observe": "Pause to gather more data before deciding"
    }