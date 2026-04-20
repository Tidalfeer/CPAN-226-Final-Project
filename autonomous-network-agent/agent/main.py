#!/usr/bin/env python3
"""
Autonomous Network Resilience Agent - Main Entry Point
AI-Enhanced with Rule-Based Safety Enforcement
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.utils import print_banner, print_status, load_config, setup_logging
from agent.tools import init_tools, get_link_metrics, get_current_status, execute_failover, execute_failback

# Optional AI import
try:
    from agent.agent_core import NetworkResilienceAgent
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print_status("AI module not available - using rule-based only", "warning")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Network Resilience Agent - AI + Rule-Based Safety"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, help="Override check interval")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI entirely (rule-based only)")
    parser.add_argument("--ai-only", action="store_true", help="AI only - no rule-based safety (testing only)")
    return parser.parse_args()

def check_health(metrics, config, debug=False):
    """Check if metrics indicate healthy link."""
    packet_loss = metrics.get('packet_loss', 0)
    latency = metrics.get('avg_latency_ms', 0)
    status = metrics.get('status', 'unknown')
    
    # DEBUG: Always print what we're checking
    print(f"    DEBUG check_health received:")
    print(f"      packet_loss: {packet_loss}")
    print(f"      latency: {latency}")
    print(f"      status: '{status}'")
    
    loss_ok = packet_loss <= config['thresholds']['packet_loss_max']
    latency_ok = latency <= config['thresholds']['latency_max_ms']
    status_ok = status == 'healthy'
    
    is_healthy = loss_ok and latency_ok and status_ok
    
    if debug:
        print(f"    DEBUG: packet_loss={packet_loss:.2f}% (threshold={config['thresholds']['packet_loss_max']}%) -> {'OK' if loss_ok else 'FAIL'}")
        print(f"    DEBUG: latency={latency:.2f}ms (threshold={config['thresholds']['latency_max_ms']}ms) -> {'OK' if latency_ok else 'FAIL'}")
        print(f"    DEBUG: status='{status}' -> {'OK' if status_ok else 'FAIL'}")
        print(f"    DEBUG: Overall healthy = {is_healthy}")
    
    return is_healthy

def get_rule_based_decision(active_link, current_healthy, other_healthy, stability_achieved, time_since_failover, stability_period):
    """
    Get the rule-based decision that should be made.
    Returns: (decision, reason)
    """
    if active_link == 'primary':
        if not current_healthy and other_healthy:
            return 'failover', "Primary degraded/down AND backup healthy"
        elif not current_healthy and not other_healthy:
            return 'wait', "Both links degraded/down - staying on primary"
        else:
            return 'wait', "Primary healthy - no action needed"
    else:  # active_link == 'backup'
        if other_healthy and stability_achieved:
            return 'failback', f"Primary healthy AND stability achieved ({time_since_failover:.0f}s)"
        elif not other_healthy:
            return 'wait', "Primary still degraded/down - staying on backup"
        elif not stability_achieved:
            remaining = stability_period - time_since_failover
            return 'wait', f"Waiting for stability period ({remaining:.0f}s remaining)"
        else:
            return 'wait', "Monitoring - no action needed"

def parse_ai_decision(ai_response):
    """Parse AI response to extract decision."""
    ai_response_lower = ai_response.lower()
    
    if 'failover' in ai_response_lower:
        return 'failover'
    elif 'failback' in ai_response_lower:
        return 'failback'
    else:
        return 'wait'

def main():
    """Main execution loop with AI monitoring and rule-based enforcement."""
    args = parse_args()
    print_banner()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print_status(str(e), "error")
        sys.exit(1)
    
    # Setup logging
    logger = setup_logging(config['agent']['verbose'])
    
    # Initialize network tools
    tools = init_tools(config)
    print_status(f"Primary interface: {tools.primary_if}", "info")
    print_status(f"Backup interface: {tools.backup_if}", "info")
    print_status(f"Test target: {tools.test_target}", "info")
    
    # Initialize AI agent if available and not disabled
    agent = None
    use_ai = AI_AVAILABLE and not args.no_ai
    
    if use_ai:
        try:
            agent = NetworkResilienceAgent(args.config)
            print_status("🤖 AI agent initialized - Enhanced monitoring active", "success")
        except Exception as e:
            print_status(f"AI initialization failed: {e}", "warning")
            print_status("Falling back to rule-based only", "info")
            use_ai = False
    else:
        if args.no_ai:
            print_status("📋 Rule-based mode only (AI disabled by flag)", "info")
        else:
            print_status("📋 Rule-based mode only", "info")
    
    if args.ai_only:
        print_status("⚠️  AI-ONLY MODE - Rule-based safety DISABLED (testing only)", "warning")
    
    if args.debug:
        print_status("🐛 DEBUG MODE ENABLED", "warning")
        print_status(f"Thresholds: Loss={config['thresholds']['packet_loss_max']}%, Latency={config['thresholds']['latency_max_ms']}ms", "info")
        print_status(f"Stability period: {config['agent']['stability_period_seconds']}s", "info")
        print_status(f"Mode: {'AI + Rules' if use_ai else 'Rules Only'}", "info")
    
    print_status("✅ Agent ready. Beginning network monitoring...", "success")
    print("-" * 60)
    
    interval = args.interval or config['agent']['check_interval_seconds']
    stability_period = config['agent']['stability_period_seconds']
    
    # Statistics tracking
    stats = {
        'cycles': 0,
        'ai_recommendations': 0,
        'ai_overrides': 0,
        'failovers': 0,
        'failbacks': 0
    }
    
    try:
        while True:
            stats['cycles'] += 1
            print_status(f"=== MONITORING CYCLE {stats['cycles']} ===", "action")
            
            # Get current status
            status = get_current_status()
            active_link = status['active_link']
            time_since_failover = status.get('time_since_last_failover', 0)
            stability_achieved = status.get('stability_achieved', False)
            
            print_status(f"Active link: {active_link.upper()} | Failovers: {status.get('failover_count', 0)}", "info")
            
            # Determine interfaces
            primary_if = tools.primary_if
            backup_if = tools.backup_if
            current_if = primary_if if active_link == 'primary' else backup_if
            other_if = backup_if if active_link == 'primary' else primary_if
            other_link_name = 'backup' if active_link == 'primary' else 'primary'
            
            # Get metrics for BOTH links
            print_status(f"Checking CURRENT link ({active_link.upper()} - {current_if})...", "action")
            current_metrics = get_link_metrics(current_if)
            
            print_status(f"Checking OTHER link ({other_link_name.upper()} - {other_if})...", "action")
            other_metrics = get_link_metrics(other_if)
            
            # Check health
            current_healthy = check_health(current_metrics, config, args.debug)
            other_healthy = check_health(other_metrics, config, args.debug)
            
            # Display health status
            current_status_icon = "✅ HEALTHY" if current_healthy else "❌ DEGRADED/DOWN"
            other_status_icon = "✅ HEALTHY" if other_healthy else "❌ DEGRADED/DOWN"
            
            print_status(f"Current ({active_link}): {current_status_icon}", 
                        "success" if current_healthy else "error")
            print_status(f"Other ({other_link_name}): {other_status_icon}", 
                        "success" if other_healthy else "error")
            
            # ==================================================================
            # GET RULE-BASED DECISION (The Safety Net)
            # ==================================================================
            rule_decision, rule_reason = get_rule_based_decision(
                active_link, current_healthy, other_healthy, 
                stability_achieved, time_since_failover, stability_period
            )
            
            # ==================================================================
            # GET AI RECOMMENDATION (If enabled)
            # ==================================================================
            ai_decision = None
            ai_reason = None
            
            if use_ai and agent:
                try:
                    print_status("🤖 Consulting AI agent...", "action")
                    ai_response = agent.get_decision(current_metrics, status, other_metrics)
                    ai_decision = parse_ai_decision(ai_response)
                    stats['ai_recommendations'] += 1
                    
                    # Extract AI's reasoning (everything after the decision word)
                    ai_reason = ai_response.replace('execute_failover', '').replace('execute_failback', '').replace('wait_and_observe', '').strip()
                    if not ai_reason:
                        ai_reason = "No reason provided"
                    
                    if args.debug:
                        print(f"    DEBUG AI full response: {ai_response}")
                        print(f"    DEBUG AI parsed decision: {ai_decision}")
                    
                    print_status(f"🤖 AI recommends: {ai_decision.upper()}", "info")
                    print_status(f"🤖 AI reasoning: {ai_reason}", "info")
                    
                except Exception as e:
                    print_status(f"AI consultation failed: {e}", "warning")
                    use_ai = False  # Disable AI for future cycles
            
            # ==================================================================
            # DECISION RECONCILIATION
            # ==================================================================
            print("-" * 40)
            
            if args.ai_only:
                # AI-only mode (testing only - no safety net)
                final_decision = ai_decision if ai_decision else rule_decision
                final_reason = ai_reason if ai_reason else "AI recommendation"
                print_status(f"⚠️  AI-ONLY MODE - Following AI: {final_decision.upper()}", "warning")
                
            elif use_ai and ai_decision:
                # AI + Rules mode - Compare and use safety net if needed
                print_status(f"📋 Rule-based says: {rule_decision.upper()}", "info")
                print_status(f"   Reason: {rule_reason}", "info")
                print_status(f"🤖 AI recommends: {ai_decision.upper()}", "info")
                
                if ai_decision == rule_decision:
                    # AI and rules agree
                    final_decision = rule_decision
                    final_reason = f"AI and rules agree: {rule_reason}"
                    print_status(f"✅ AI and rules AGREE on: {final_decision.upper()}", "success")
                    
                else:
                    # AI disagrees with rules - Safety override
                    stats['ai_overrides'] += 1
                    final_decision = rule_decision
                    final_reason = rule_reason
                    
                    print_status(f"⚠️  AI DISAGREES with rule-based decision!", "warning")
                    print_status(f"⚠️  SAFETY OVERRIDE: Using rule-based decision", "warning")
                    print_status(f"   Rule-based: {rule_decision.upper()} - {rule_reason}", "success")
                    print_status(f"   AI wanted: {ai_decision.upper()} - {ai_reason}", "error")
                    
                    # Log the disagreement for analysis
                    if args.debug:
                        print(f"    DEBUG Disagreement details:")
                        print(f"      - Current health: {current_healthy}, Other health: {other_healthy}")
                        print(f"      - Active link: {active_link}")
                        print(f"      - AI wanted to {ai_decision} but rules require {rule_decision}")
            else:
                # Rule-based only
                final_decision = rule_decision
                final_reason = rule_reason
                print_status(f"📋 Rule-based decision: {final_decision.upper()}", "info")
                print_status(f"   Reason: {final_reason}", "info")
            
            # ==================================================================
            # EXECUTE FINAL DECISION
            # ==================================================================
            print_status(f"🎯 FINAL DECISION: {final_decision.upper()}", "action")
            print_status(f"📝 REASON: {final_reason}", "info")
            
            if final_decision == 'failover':
                print_status("⚠️  EXECUTING FAILOVER TO BACKUP LINK", "warning")
                result = execute_failover()
                print_status(f"✅ {result}", "success")
                stats['failovers'] += 1
                
            elif final_decision == 'failback':
                print_status("↩️  EXECUTING FAILBACK TO PRIMARY LINK", "action")
                result = execute_failback()
                print_status(f"✅ {result}", "success")
                stats['failbacks'] += 1
                
            else:  # decision == 'wait'
                print_status("⏸️  No action taken - continuing to monitor", "info")
            
            # Single run mode
            if args.once:
                print_status("Single run complete. Exiting.", "info")
                break
            
            # Wait for next cycle
            print_status(f"⏱️  Waiting {interval}s until next check...", "info")
            print("-" * 60)
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n")
        print_status("🛑 Shutdown requested by user.", "warning")
        
        # Print statistics
        print("\n" + "="*60)
        print_status("📊 SESSION STATISTICS", "action")
        print(f"   Total cycles: {stats['cycles']}")
        print(f"   Failovers executed: {stats['failovers']}")
        print(f"   Failbacks executed: {stats['failbacks']}")
        if use_ai:
            print(f"   AI recommendations: {stats['ai_recommendations']}")
            print(f"   AI overrides (safety): {stats['ai_overrides']}")
            if stats['ai_recommendations'] > 0:
                override_rate = (stats['ai_overrides'] / stats['ai_recommendations']) * 100
                print(f"   Safety override rate: {override_rate:.1f}%")
        print("="*60)
        
        print_status(f"Total failovers during session: {tools.failover_count}", "info")
        sys.exit(0)
        
    except Exception as e:
        print_status(f"❌ Unexpected error: {e}", "error")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()