from __future__ import annotations

import asyncio
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse
from xml.etree import ElementTree

import aiohttp

from lgtv_remote.constants import (
    ARP_SETTLE_DELAY_SECS,
    MSEARCH_REPEAT_COUNT,
    MSEARCH_SEND_DELAY_SECS,
    SSDP_RECV_DEADLINE_SECS,
    SSDP_RECV_TIMEOUT_SECS,
    WEBOS_PORT,
)

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
LG_SEARCH_TARGET = "urn:lge-com:service:webos-second-screen:1"
SSDP_ALL = "ssdp:all"


@dataclass
class DiscoveredTv:
    host: str
    friendly_name: str
    model_name: str = ""
    location: str = ""


def build_msearch(search_target: str) -> bytes:
    return (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        f"ST: {search_target}\r\n"
        "\r\n"
    ).encode()


def parse_ssdp_response(data: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in data.split("\r\n"):
        if ":" in line and not line.startswith("HTTP"):
            key, _, value = line.partition(":")
            headers[key.strip().upper()] = value.strip()
    return headers


def _is_lg_webos(headers: dict[str, str]) -> bool:
    server = headers.get("SERVER", "").lower()
    return "lg" in server or "webos" in server


async def _fetch_device_description(
    session: aiohttp.ClientSession, location: str
) -> DiscoveredTv | None:
    try:
        async with session.get(
            location, timeout=aiohttp.ClientTimeout(total=3), ssl=False
        ) as resp:
            text = await resp.text()
        root = ElementTree.fromstring(text)
        upnp_ns = {"d": "urn:schemas-upnp-org:device-1-0"}
        device = root.find(".//d:device", upnp_ns)
        if device is None:
            device = root.find(".//{urn:schemas-upnp-org:device-1-0}device")
        if device is None:
            return None

        def _find_text(tag: str) -> str:
            el = device.find(f"d:{tag}", upnp_ns)
            if el is None:
                el = device.find(f"{{urn:schemas-upnp-org:device-1-0}}{tag}")
            return el.text if el is not None and el.text else ""

        friendly_name = _find_text("friendlyName")
        model_name = _find_text("modelName")

        host = urlparse(location).hostname or ""
        return DiscoveredTv(
            host=host,
            friendly_name=friendly_name or model_name or host,
            model_name=model_name,
            location=location,
        )
    except Exception:
        return None


async def discover_tvs(
    timeout: float = 5.0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[DiscoveredTv]:
    search_targets = (LG_SEARCH_TARGET, SSDP_ALL)
    total_steps = len(search_targets) * MSEARCH_REPEAT_COUNT + 2
    current_step = 0

    def _report() -> None:
        nonlocal current_step
        current_step += 1
        if progress_callback is not None:
            progress_callback(current_step, total_steps)

    seen_hosts: set[str] = set()
    locations: set[str] = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    sock.bind(("", 0))

    loop = asyncio.get_running_loop()

    for search_target in search_targets:
        msg = build_msearch(search_target)
        for _ in range(MSEARCH_REPEAT_COUNT):
            try:
                sock.sendto(msg, (SSDP_ADDR, SSDP_PORT))
            except OSError:
                pass
            await asyncio.sleep(MSEARCH_SEND_DELAY_SECS)
            _report()

    deadline = loop.time() + SSDP_RECV_DEADLINE_SECS
    while loop.time() < deadline:
        try:
            data = await asyncio.wait_for(
                loop.sock_recv(sock, 4096), timeout=SSDP_RECV_TIMEOUT_SECS
            )
            text = data.decode(errors="replace")
            headers = parse_ssdp_response(text)
            location = headers.get("LOCATION", "")
            if not location:
                continue
            search_target_value = headers.get("ST", "")
            if search_target_value == LG_SEARCH_TARGET or _is_lg_webos(headers):
                if location not in locations:
                    locations.add(location)
        except (TimeoutError, OSError):
            pass

    sock.close()
    _report()

    tvs: list[DiscoveredTv] = []
    if locations:
        async with aiohttp.ClientSession() as session:
            tasks = [_fetch_device_description(session, loc) for loc in locations]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, DiscoveredTv) and result.host not in seen_hosts:
                    seen_hosts.add(result.host)
                    tvs.append(result)
    _report()
    return tvs


def parse_ip_neigh_line(line: str) -> tuple[str, str] | None:
    match = re.search(r"^(\S+)\s.*lladdr\s+([0-9a-fA-F:]{17})", line)
    if match:
        return match.group(1), match.group(2)
    return None


async def resolve_mac(ip: str) -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect_ex((ip, WEBOS_PORT))
        finally:
            sock.close()
    except OSError:
        pass

    await asyncio.sleep(ARP_SETTLE_DELAY_SECS)

    proc = await asyncio.create_subprocess_exec(
        "ip", "neigh", "show", ip,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    for line in stdout.decode().strip().splitlines():
        result = parse_ip_neigh_line(line)
        if result and result[0] == ip:
            return result[1]
    return None
