"""Utility functions for logging and configuration."""
import logging
import yaml
from pathlib import Path
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init(autoreset=True)

def setup_logging(verbose: bool = True):
    """Configure logging for the agent."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "agent.log"
    
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("NetworkAgent")

def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def print_banner():
    """Display a nice ASCII banner."""
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}
╔══════════════════════════════════════════════════════════════╗
║     AUTONOMOUS NETWORK RESILIENCE AGENT (ANRA) v1.0          ║
║                  Agentic AI Class Project                    ║
╚══════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}
    """
    print(banner)

def print_status(message: str, status: str = "info"):
    """Pretty print status messages."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "info": Fore.WHITE,
        "success": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error": Fore.RED,
        "action": Fore.MAGENTA + Style.BRIGHT
    }
    color = colors.get(status, Fore.WHITE)
    print(f"{color}[{timestamp}] {message}{Style.RESET_ALL}")