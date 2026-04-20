"""
Core Agentic AI logic - uses Ollama directly without external LLM libraries.
"""

import json
import logging
import requests
from .utils import print_status, load_config

class NetworkResilienceAgent:
    """
    Autonomous agent that monitors network health and orchestrates failover.
    Uses Ollama's native API directly.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.logger = logging.getLogger("NetworkAgent")
        
        # Ollama configuration
        self.ollama_base_url = "http://localhost:11434"
        self.model_name = self.config['agent'].get('llm_model', 'llama3.2:1b')
        
        # Verify Ollama is accessible
        self._verify_ollama()
        
        print_status(f"Using Ollama model: {self.model_name}", "success")
    
    def _verify_ollama(self):
        """Verify that Ollama is running and accessible."""
        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                if self.model_name not in model_names:
                    print_status(f"Model {self.model_name} not found. Pulling...", "warning")
                    self._pull_model()
                else:
                    print_status(f"Model {self.model_name} is available", "success")
            else:
                print_status("Cannot connect to Ollama API", "warning")
        except Exception as e:
            print_status(f"Ollama connection error: {e}", "error")
            print_status("Make sure Ollama is running: ollama serve", "info")
    
    def _pull_model(self):
        """Pull the required model from Ollama."""
        try:
            response = requests.post(
                f"{self.ollama_base_url}/api/pull",
                json={"name": self.model_name, "stream": False},
                timeout=300
            )
            if response.status_code == 200:
                print_status(f"Model {self.model_name} pulled successfully", "success")
            else:
                print_status(f"Failed to pull model: {response.text}", "error")
        except Exception as e:
            print_status(f"Error pulling model: {e}", "error")
    
    def _call_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """Call Ollama API directly using the generate endpoint."""
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = requests.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 200,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                self.logger.error(f"Ollama API error: {response.status_code}")
                return f"ERROR: LLM returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            self.logger.error("Ollama request timeout")
            return "ERROR: LLM request timed out"
        except requests.exceptions.ConnectionError:
            self.logger.error("Cannot connect to Ollama")
            return "ERROR: Cannot connect to Ollama. Is it running?"
        except Exception as e:
            self.logger.error(f"Unexpected error calling Ollama: {e}")
            return f"ERROR: {str(e)}"
    
    def get_decision(self, metrics: dict, current_status: dict, backup_metrics: dict = None) -> str:
        """
        Get a decision from the LLM based on current metrics and status.
        
        Args:
            metrics: Current link metrics
            current_status: Current agent status
            backup_metrics: Optional metrics for the backup link
        
        Returns:
            The LLM's decision as a string
        """
        active_link = current_status.get('active_link', 'primary')
        other_link = 'backup' if active_link == 'primary' else 'primary'
        
        # Determine health explicitly
        current_healthy = (
            metrics.get('packet_loss', 0) <= self.config['thresholds']['packet_loss_max'] and
            metrics.get('avg_latency_ms', 0) <= self.config['thresholds']['latency_max_ms'] and
            metrics.get('status') == 'healthy'
        )
        
        other_healthy = False
        other_status = "unknown"
        if backup_metrics:
            other_healthy = (
                backup_metrics.get('packet_loss', 0) <= self.config['thresholds']['packet_loss_max'] and
                backup_metrics.get('avg_latency_ms', 0) <= self.config['thresholds']['latency_max_ms'] and
                backup_metrics.get('status') == 'healthy'
            )
            other_status = backup_metrics.get('status', 'unknown')
        
        # Pre-calculate the correct answer based on rules
        if active_link == 'primary':
            if not current_healthy and other_healthy:
                forced_answer = "execute_failover"
                forced_reason = f"Primary is {metrics.get('status')} but backup is healthy"
            elif not current_healthy and not other_healthy:
                forced_answer = "wait_and_observe"
                forced_reason = f"Primary is {metrics.get('status')} but backup is also {other_status} - cannot failover"
            else:
                forced_answer = "wait_and_observe"
                forced_reason = "Primary is healthy"
        else:  # active_link == 'backup'
            stability_achieved = current_status.get('stability_achieved', False)
            if other_healthy and stability_achieved:
                forced_answer = "execute_failback"
                forced_reason = "Primary is healthy and stability achieved"
            elif not other_healthy:
                forced_answer = "wait_and_observe"
                forced_reason = f"Primary is {other_status} - must stay on backup"
            elif not stability_achieved:
                forced_answer = "wait_and_observe"
                time_elapsed = current_status.get('time_since_last_failover', 0)
                forced_reason = f"Waiting for stability ({time_elapsed:.0f}s elapsed)"
            else:
                forced_answer = "wait_and_observe"
                forced_reason = "Monitoring"
        
        # Build prompt that tells the AI the situation
        prompt = f"""NETWORK STATUS:
- Active link: {active_link.upper()}
- Primary link: {metrics.get('status') if active_link == 'primary' else other_status}
- Backup link: {other_status if active_link == 'primary' else metrics.get('status')}
- Primary metrics: loss={metrics.get('packet_loss', 0):.1f}%, latency={metrics.get('avg_latency_ms', 0):.1f}ms
"""

        if backup_metrics:
            prompt += f"- Backup metrics: loss={backup_metrics.get('packet_loss', 0):.1f}%, latency={backup_metrics.get('avg_latency_ms', 0):.1f}ms\n"
        
        prompt += f"""
THRESHOLDS: Loss max={self.config['thresholds']['packet_loss_max']}%, Latency max={self.config['thresholds']['latency_max_ms']}ms

Based on the rules:
- If active is primary AND primary is NOT healthy AND backup IS healthy → failover
- If active is primary AND primary is NOT healthy AND backup is NOT healthy → wait (cannot failover)
- If active is backup AND primary IS healthy AND stability achieved → failback
- Otherwise → wait

The CORRECT action is: {forced_answer}
Because: {forced_reason}

What action should be taken? Answer with ONLY ONE:
execute_failover
execute_failback
wait_and_observe

Action:"""
        
        return self._call_ollama(prompt)