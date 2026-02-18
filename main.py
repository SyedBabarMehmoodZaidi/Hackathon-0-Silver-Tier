#!/usr/bin/env python3
"""
Personal AI Employee - Main Entry Point

Coordinates the entire system: Watchers → Needs_Action → Claude → Plan → Approval → MCP → Done → Logs
"""

import os
import sys
import time
import argparse
from pathlib import Path
import subprocess
import threading
import signal
from threading import Event

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Add the watchers directory to Python path
sys.path.append(str(Path(__file__).parent / "Watchers"))

import orchestrator
from base_watcher import FileDropWatcher
from mcp_interface import MCPServerManager


def setup_environment():
    """Set up the environment and directories"""
    base_path = Path(__file__).parent

    # Create necessary directories if they don't exist
    dirs_to_create = [
        base_path / "Needs_Action",
        base_path / "Approved",
        base_path / "Done",
        base_path / "Logs",
        base_path / "Vault" / "Daily",
        base_path / "Vault" / "Weekly",
        base_path / "Vault" / "Monthly",
        base_path / "Incoming_Files"
    ]

    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Ensured directory exists: {dir_path}")


def start_watchers():
    """Start all configured watchers"""
    base_path = Path(__file__).parent
    needs_action_path = base_path / "Needs_Action"
    incoming_files_path = base_path / "Incoming_Files"

    # Create and start file drop watcher
    file_watcher = FileDropWatcher(needs_action_path, incoming_files_path)

    # Run the watcher in a separate thread
    watcher_thread = threading.Thread(target=file_watcher.start_monitoring, daemon=True)
    watcher_thread.start()

    print("Started file drop watcher")
    return watcher_thread


def start_orchestrator():
    """Start the main orchestrator in a separate thread"""
    stop_event = Event()
    orchestrator_thread = threading.Thread(target=orchestrator.main, args=(stop_event,), daemon=True)
    orchestrator_thread.start()
    print("Started orchestrator in background thread")
    return orchestrator_thread, stop_event


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Personal AI Employee')
    parser.add_argument('--mode', choices=['full', 'watcher', 'orchestrator'],
                       default='full', help='Run mode: full system, just watchers, or just orchestrator')
    parser.add_argument('--setup', action='store_true', help='Setup environment only')

    args = parser.parse_args()

    print("[SYSTEM] Starting Personal AI Employee System")

    # Setup environment
    setup_environment()

    if args.setup:
        print("[SUCCESS] Environment setup complete!")
        return

    print(f"Running in {args.mode} mode...")

    threads = []

    if args.mode in ['full', 'watcher']:
        print("Starting watchers...")
        watcher_thread = start_watchers()
        threads.append(watcher_thread)

    orchestrator_thread = None
    stop_event = None

    if args.mode in ['full', 'orchestrator']:
        print("Starting orchestrator...")
        orchestrator_thread, stop_event = start_orchestrator()
        threads.append(orchestrator_thread)

    try:
        print("System running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Shutting down Personal AI Employee...")
        if stop_event:
            stop_event.set()  # Signal the orchestrator to stop

        # Wait for threads to finish (with a timeout)
        for thread in threads:
            thread.join(timeout=2)  # Wait up to 2 seconds for each thread


if __name__ == "__main__":
    main()