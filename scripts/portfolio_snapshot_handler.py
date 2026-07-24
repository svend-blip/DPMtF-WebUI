#!/usr/bin/env python3
"""
Portfolio Snapshot Handler for DPMtF-WebUI

This script processes portfolio snapshot data and makes it available to the system.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for config import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

def load_portfolio_snapshot():
    """Load the portfolio snapshot from the inbox."""
    inbox_path = os.path.join(config.get_project_root(), "inbox", "pending")
    if not os.path.exists(inbox_path):
        raise FileNotFoundError(f"Inbox path does not exist: {inbox_path}")

    # Find the latest portfolio snapshot file
    files = [f for f in os.listdir(inbox_path) if f.startswith("trend01_trade_") and f.endswith(".json")]
    if not files:
        raise FileNotFoundError("No trend01_trade portfolio snapshot found in inbox")

    # Sort by modification time to get the latest
    files.sort(key=lambda x: os.path.getmtime(os.path.join(inbox_path, x)), reverse=True)
    latest_file = files[0]

    file_path = os.path.join(inbox_path, latest_file)

    with open(file_path, 'r') as f:
        return json.load(f)

def process_portfolio_snapshot():
    """Process the portfolio snapshot and save it to the database directory."""
    try:
        # Load the snapshot
        snapshot_data = load_portfolio_snapshot()

        # Save to databases directory as portfolio_snapshot.json
        output_path = os.path.join(config.get_project_root(), "databases", "portfolio_snapshot.json")

        with open(output_path, 'w') as f:
            json.dump(snapshot_data, f, indent=2)

        print(f"Portfolio snapshot saved to {output_path}")

        # Update the current-cycle.json file
        cycle_path = os.path.join(config.get_project_root(), "scripts", "docs", "bridgeV002", "current-cycle.json")
        with open(cycle_path, 'r') as f:
            cycle_data = json.load(f)

        cycle_data['updated'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        cycle_data['portfolio_snapshot_processed'] = True

        with open(cycle_path, 'w') as f:
            json.dump(cycle_data, f, indent=2)

        print(f"Current cycle updated at {cycle_path}")

        return True

    except Exception as e:
        print(f"Error processing portfolio snapshot: {str(e)}")
        return False

if __name__ == "__main__":
    success = process_portfolio_snapshot()
    sys.exit(0 if success else 1)