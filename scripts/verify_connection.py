#!/usr/bin/env python3
"""Minimal verification script: connect, pair, read state, switch input.

Usage:
    python scripts/verify_connection.py <TV_IP> [CLIENT_KEY]

On first run, omit CLIENT_KEY. The TV will display a pairing prompt —
accept it with the physical remote. The script prints the client key
to save for future runs.
"""
from __future__ import annotations

import asyncio
import sys

from aiowebostv import WebOsClient


async def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <TV_IP> [CLIENT_KEY]")
        sys.exit(1)

    host = sys.argv[1]
    client_key = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Connecting to {host}...")
    client = WebOsClient(host, client_key=client_key)

    async def on_state(state):
        print(f"  State update: app={state.current_app_id}, "
              f"vol={state.volume}, muted={state.muted}, on={state.is_on}")

    await client.register_state_update_callback(on_state)

    try:
        await client.connect()
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    print(f"Connected! client_key={client.client_key}")
    print(f"TV info: {client.tv_info.system}")
    print(f"Current app: {client.tv_state.current_app_id}")
    print(f"Volume: {client.tv_state.volume}, Muted: {client.tv_state.muted}")
    print(f"Power: is_on={client.tv_state.is_on}")

    if client.tv_state.apps:
        print(f"Apps ({len(client.tv_state.apps)}):")
        for app_id, info in list(client.tv_state.apps.items())[:10]:
            title = info.get("title", app_id)
            print(f"  {app_id}: {title}")

    print("\nSwitching to HDMI 2...")
    try:
        await client.launch_app("com.webos.app.hdmi2")
        await asyncio.sleep(2)
        print(f"Current app after switch: {client.tv_state.current_app_id}")
    except Exception as e:
        print(f"Switch failed: {e}")

    await client.disconnect()
    print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
