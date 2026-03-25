#!/usr/bin/env python3
"""
TravelOps Demo Scenarios
========================
Run all 4 demo scenarios back-to-back for hackathon video recording.
Each scenario shows a different approval level.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

from agent import TravelOpsAgent


def pause(msg: str):
    print(f"\n{'─'*60}")
    print(f"  NEXT: {msg}")
    print(f"{'─'*60}")
    input("  Press Enter to continue...")


def main():
    print("\n" + "="*60)
    print("  TravelOps Agent — Demo Scenarios")
    print("  4 trips showing different approval levels")
    print("="*60)

    # Scenario 1: Budget trip — auto-approve
    pause("Scenario 1: Budget Berlin trip (auto-approve)")
    agent1 = TravelOpsAgent(
        traveler="intern@company.com",
        destination="berlin",
        purpose="Team offsite",
        nights=2,
    )
    agent1.run(flight_class="economy", override_flight_price=420, override_hotel_price=95)

    # Scenario 2: Mid-range — manager approval
    pause("Scenario 2: London business class (manager approval)")
    agent2 = TravelOpsAgent(
        traveler="alice@company.com",
        destination="london",
        purpose="Client meeting",
        nights=2,
    )
    agent2.run(flight_class="business", override_flight_price=1400, override_hotel_price=110)

    # Scenario 3: Expensive — step-up CFO
    pause("Scenario 3: NYC business class (step-up: manager + CFO)")
    agent3 = TravelOpsAgent(
        traveler="cto@company.com",
        destination="new york",
        purpose="AWS re:Invent",
        nights=5,
    )
    agent3.run(flight_class="business", override_flight_price=3200, override_hotel_price=650)

    # Scenario 4: Visa required
    pause("Scenario 4: Tokyo trip with visa reminder")
    agent4 = TravelOpsAgent(
        traveler="engineer@company.com",
        destination="new york",
        purpose="Google I/O",
        nights=4,
    )
    agent4.run(flight_class="economy", override_flight_price=890, override_hotel_price=130)

    print("\n" + "="*60)
    print("  All scenarios complete!")
    print("="*60)


if __name__ == "__main__":
    main()
