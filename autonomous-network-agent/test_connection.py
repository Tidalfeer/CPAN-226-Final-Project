#!/usr/bin/env python3
"""Connection diagnostic tool"""
import requests
import socket

print("\n🔍 NETWORK DIAGNOSTIC")
print("="*60)

# Test FastAPI server
print("\nTesting FastAPI Server (http://127.0.0.1:5001)...")
try:
    r = requests.get("http://127.0.0.1:5001/health", timeout=3)
    print(f"✓ Server responding: {r.json()}")
except Exception as e:
    print(f"✗ Server error: {e}")
    print("  Start server with: python run_mock_server.py")

# Test Ollama
print("\nTesting Ollama (http://127.0.0.1:11434)...")
try:
    r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
    if r.status_code == 200:
        print("✓ Ollama running")
    else:
        print(f"✗ Ollama status: {r.status_code}")
except Exception as e:
    print(f"✗ Ollama error: {e}")

print("\n" + "="*60)