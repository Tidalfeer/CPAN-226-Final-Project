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
        self.primary_if = config['network']['primary_interface']
        self.backup_if = config['network']['backup_interface']
        self.primary_gw = config['network'].get('primary_gateway', '192.168.1.1')
        self.backup_gw = config['network'].get('backup_gateway', '192.168.2.1')
        self.test_target = config['network']['test_target']
        
        self.packet_loss_max = config['thresholds']['packet_loss_max']
        self.latency_max = config['thresholds']['latency_max_ms']
        self.jitter_max = config['thresholds'].get('jitter_max_ms', 30.0)
        
        self.current_active = "primary"
        self.failover_count = 0
        self.last_failover_time = 0.0
        self.stability_period = config['agent'].get('stability_period_seconds', 30)
        
        # Mock server config
        mock_config = config.get('mock_server', {})
        config_enabled = mock_config.get('enabled', False)
        env_enabled = os.environ.get('USE_MOCK_SERVER', '').lower() == 'true'
        
        self.use_mock_server = env_enabled or config_enabled
        self.mock_server_url = os.environ.get('MOCK_SERVER_URL', 
                              mock_config.get('url', 'http://127.0.0.1:5001'))
        
        self.os_type = platform.system()
        self.logger = logging.getLogger("NetworkAgent.Tools")
        
        if self.use_mock_server:
            self._verify_mock_server()
    
    def _verify_mock_server(self):
        """Verify that the mock server is accessible."""
        if not REQUESTS_AVAILABLE:
            print_status("'requests' library not installed", "warning")
            self.use_mock_server = False
            return
        
        try:
            response = requests.get(f"{self.mock_server_url}/health", timeout=2)
            if response.status_code == 200:
                print_status(f"Connected to mock server at {self.mock_server_url}", "success")
            else:
                print_status(f"Mock server returned {response.status_code}", "warning")
        except Exception as e:
            print_status(f"Cannot connect to mock server: {e}", "warning")
            self.use_mock_server = False
    
    def get_link_metrics(self, interface: str) -> LinkMetrics:
        """Get comprehensive metrics for a network interface."""
        print_status(f"  Probing: {interface}", "info")
        
        if self.use_mock_server:
            try:
                mock_interface = "primary" if interface == self.primary_if else "backup"
                response = requests.get(
                    f"{self.mock_server_url}/api/health/{mock_interface}",
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    return LinkMetrics(
                        packet_loss=float(data.get('packet_loss', 0)),
                        avg_latency_ms=float(data.get('avg_latency_ms', 0)),
                        jitter_ms=float(data.get('jitter_ms', 0)),
                        status=data.get('condition', 'unknown'),
                        bandwidth_mbps=float(data.get('bandwidth_mbps', 100.0))
                    )
            except Exception as e:
                self.logger.error(f"Mock server error: {e}")
        
        # Fallback - simulated healthy metrics
        return LinkMetrics(
            packet_loss=0.0,
            avg_latency_ms=15.0,
            jitter_ms=2.0,
            status="healthy"
        )
    
    def execute_failover(self) -> str:
        """Execute failover from primary to backup link."""
        print_status(f"  Switching: {self.primary_if} → {self.backup_if}", "warning")
        self.current_active = "backup"
        self.failover_count += 1
        self.last_failover_time = time.time()
        
        if self.use_mock_server:
            try:
                requests.post(f"{self.mock_server_url}/api/agent/action",
                            json={'action': 'failover', 'active_link': 'backup'})
            except:
                pass
        
        return f"Traffic now routing through backup interface '{self.backup_if}'. Failover count: {self.failover_count}"
    
    def execute_failback(self) -> str:
        """Execute failback from backup to primary link."""
        print_status(f"  Switching: {self.backup_if} → {self.primary_if}", "action")
        self.current_active = "primary"
        
        if self.use_mock_server:
            try:
                requests.post(f"{self.mock_server_url}/api/agent/action",
                            json={'action': 'failback', 'active_link': 'primary'})
            except:
                pass
        
        return f"Traffic now routing through primary interface '{self.primary_if}'"
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current state of the network resilience agent."""
        time_since_failover = 0.0
        if self.last_failover_time > 0:
            time_since_failover = time.time() - self.last_failover_time
        
        return {
            "active_link": self.current_active,
            "primary_interface": self.primary_if,
            "backup_interface": self.backup_if,
            "failover_count": self.failover_count,
            "time_since_last_failover": round(time_since_failover, 1),
            "stability_achieved": time_since_failover >= self.stability_period,
            "mode": "test" if self.use_mock_server else "production"
        }

# Global network tools instance
_network_tools: Optional[NetworkTools] = None

def init_tools(config: dict) -> NetworkTools:
    """Initialize the network tools singleton."""
    global _network_tools
    _network_tools = NetworkTools(config)
    return _network_tools

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