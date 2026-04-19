Autonomous Network Resilience Agent
Overview

An agentic AI system that monitors network health and automatically orchestrates failover to a backup connection during link degradation. The agent uses rule-based logic with optional AI-enhanced monitoring to ensure network reliability.
Features

    Real-time network health monitoring (packet loss, latency, jitter)

    Automatic failover to backup link when primary degrades

    Automatic failback when primary recovers and stabilizes

    Rule-based decision engine with configurable thresholds

    Optional AI-powered monitoring using Ollama

    Safety enforcement prevents failover to unhealthy backup links

    Mock network server for testing without affecting real networks

    Web dashboard for monitoring and manual control

Requirements

    Python 3.8 or higher

    Ollama (optional, for AI features)

    Windows, macOS, or Linux

Installation

    Clone or extract the project to your desired location

    Install Python dependencies:

	pip install -r requirements.txt

(Optional) Install Ollama for AI features:

    Download from https://ollama.com

    Start Ollama and pull the model:

	ollama pull llama3.2:1b





