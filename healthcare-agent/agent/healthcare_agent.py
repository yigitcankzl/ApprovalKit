#!/usr/bin/env python3
"""
Healthcare AI Agent — CLI
==========================
Interactive command-line agent for healthcare operations.
All high-stakes actions are gated through ApprovalKit.

Usage:
    python -m agent.healthcare_agent --scenario patient-onboarding
    python -m agent.healthcare_agent --scenario controlled-substance
    python -m agent.healthcare_agent --list-scenarios
    python -m agent.healthcare_agent --interactive

Env vars:
    APPROVALKIT_URL          http://localhost:8000
    APPROVALKIT_API_KEY      (from workspace setup)
    APPROVALKIT_HMAC_SECRET  (from workspace setup)
"""
import os
import sys
import argparse
import json

import httpx

API_URL = os.environ.get("HEALTHCARE_API_URL", "http://localhost:3002").rstrip("/")


def api(method: str, path: str, body: dict | None = None):
    with httpx.Client(timeout=60) as client:
        if method == "GET":
            r = client.get(f"{API_URL}{path}")
        else:
            r = client.post(f"{API_URL}{path}", json=body)
        return r.json()


def list_scenarios():
    scenarios = api("GET", "/api/scenarios")
    print(f"\n{'='*60}")
    print(f"  Healthcare AI Agent — Available Scenarios")
    print(f"{'='*60}")
    for s in scenarios:
        approval_types = ", ".join(s["approval_types"])
        print(f"\n  [{s['id']}]")
        print(f"  Title:    {s['title']}")
        print(f"  Category: {s['category']}")
        print(f"  Approval: {approval_types}")
        print(f"  Steps:    {len(s['steps'])}")
        for i, step in enumerate(s["steps"], 1):
            print(f"    {i}. {step}")
    print(f"\n{'='*60}")


def run_scenario(scenario_id: str):
    print(f"\n{'='*60}")
    print(f"  Running Scenario: {scenario_id}")
    print(f"{'='*60}")

    # Get scenario details
    scenario = api("GET", f"/api/scenarios/{scenario_id}")
    print(f"\n  Title: {scenario['title']}")
    print(f"  Description: {scenario['description']}")
    print(f"\n  Steps:")
    for i, step in enumerate(scenario["steps"], 1):
        print(f"    {i}. {step}")

    print(f"\n  Executing...")
    result = api("POST", f"/api/scenarios/{scenario_id}/run")
    print(f"  Status: {result.get('status', 'unknown')}")
    print(f"  Message: {result.get('message', '')}")
    print(f"\n  Monitor progress at: http://localhost:3003")
    print(f"{'='*60}")


def interactive():
    print(f"\n{'='*60}")
    print(f"  Healthcare AI Agent — Interactive Mode")
    print(f"{'='*60}")
    print(f"  Hospital: MedCore General Hospital")
    print(f"  API: {API_URL}")
    print()
    print("  Commands:")
    print("    patients          — List patients")
    print("    doctors           — List doctors")
    print("    prescriptions     — List prescriptions")
    print("    billing           — List billing records")
    print("    emergencies       — Active emergencies")
    print("    stats             — Dashboard stats")
    print("    scenarios         — List scenarios")
    print("    run <scenario>    — Run a scenario")
    print("    seed              — Seed database with demo data")
    print("    quit              — Exit")
    print()

    while True:
        try:
            cmd = input("healthcare> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not cmd:
            continue

        parts = cmd.split()
        action = parts[0].lower()

        try:
            if action == "quit" or action == "exit":
                print("Goodbye!")
                break
            elif action == "patients":
                result = api("GET", "/api/patients?limit=10")
                for p in result:
                    print(f"  {p['mrn']} — {p['first_name']} {p['last_name']} ({p['status']})")
            elif action == "doctors":
                result = api("GET", "/api/staff/doctors")
                for d in result:
                    vac = " [ON VACATION]" if d["on_vacation"] else ""
                    cmo = " [CMO]" if d["is_cmo"] else ""
                    print(f"  Dr. {d['first_name']} {d['last_name']} — {d['specialty']}{cmo}{vac}")
            elif action == "prescriptions":
                result = api("GET", "/api/prescriptions?limit=10")
                for rx in result:
                    ctrl = " [CONTROLLED]" if rx["is_controlled"] else ""
                    print(f"  {rx['rx_number']} — {rx['medication_name']} {rx['dosage']} [{rx['status']}]{ctrl}")
            elif action == "billing":
                result = api("GET", "/api/billing?limit=10")
                for b in result:
                    print(f"  {b['invoice_number']} — ${b['amount']:,.2f} [{b['status']}]")
            elif action == "emergencies":
                result = api("GET", "/api/emergency/active")
                if not result:
                    print("  No active emergencies.")
                for e in result:
                    print(f"  [{e['severity']}] {e['event_type']} — {e['reason'][:60]}")
            elif action == "stats":
                result = api("GET", "/api/dashboard/stats")
                print(json.dumps(result, indent=2))
            elif action == "scenarios":
                list_scenarios()
            elif action == "run" and len(parts) > 1:
                run_scenario(parts[1])
            elif action == "seed":
                result = api("POST", "/api/seed")
                print(json.dumps(result, indent=2))
            else:
                print(f"  Unknown command: {cmd}")
        except Exception as e:
            print(f"  Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Healthcare AI Agent CLI")
    parser.add_argument("--scenario", help="Run a specific scenario")
    parser.add_argument("--list-scenarios", action="store_true", help="List available scenarios")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--seed", action="store_true", help="Seed the database")
    args = parser.parse_args()

    if args.list_scenarios:
        list_scenarios()
    elif args.scenario:
        run_scenario(args.scenario)
    elif args.seed:
        result = api("POST", "/api/seed")
        print(json.dumps(result, indent=2))
    elif args.interactive:
        interactive()
    else:
        interactive()


if __name__ == "__main__":
    main()
