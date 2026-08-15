from __future__ import annotations

import ipaddress
import re
import socket
import struct

from lgtv_remote.constants import SIOCGIFADDR, SIOCGIFNETMASK, SOCKADDR_IP_OFFSET, WOL_PORTS


def normalize_mac(mac: str) -> str:
    raw = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(raw) != 12:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    return ":".join(raw[i : i + 2].lower() for i in range(0, 12, 2))


def mac_to_bytes(mac: str) -> bytes:
    return bytes.fromhex(normalize_mac(mac).replace(":", ""))


def build_magic_packet(mac: str) -> bytes:
    return b"\xff" * 6 + mac_to_bytes(mac) * 16


def get_subnet_broadcast(tv_ip: str) -> str | None:
    try:
        import fcntl

        tv_addr = ipaddress.ip_address(tv_ip)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for ifname in _get_interface_names():
                try:
                    addr_raw = fcntl.ioctl(
                        sock.fileno(),
                        SIOCGIFADDR,
                        struct.pack("256s", ifname.encode()[:15]),
                        False,
                    )
                    addr_ip: bytes = addr_raw[SOCKADDR_IP_OFFSET]  # type: ignore[assignment]
                    ifaddr = socket.inet_ntoa(addr_ip)
                    mask_raw = fcntl.ioctl(
                        sock.fileno(),
                        SIOCGIFNETMASK,
                        struct.pack("256s", ifname.encode()[:15]),
                        False,
                    )
                    mask_ip: bytes = mask_raw[SOCKADDR_IP_OFFSET]  # type: ignore[assignment]
                    netmask = socket.inet_ntoa(mask_ip)
                    network = ipaddress.IPv4Network(
                        f"{ifaddr}/{netmask}", strict=False
                    )
                    if tv_addr in network:
                        return str(network.broadcast_address)
                except OSError:
                    continue
        finally:
            sock.close()
    except Exception:
        pass
    return None


def _get_interface_names() -> list[str]:
    names: list[str] = []
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" in line:
                    name = line.split(":")[0].strip()
                    if name != "lo":
                        names.append(name)
    except OSError:
        pass
    return names


def send_wol(mac: str, tv_ip: str | None = None) -> None:
    packet = build_magic_packet(mac)
    broadcast_addrs = ["255.255.255.255"]
    if tv_ip:
        subnet_bcast = get_subnet_broadcast(tv_ip)
        if subnet_bcast and subnet_bcast not in broadcast_addrs:
            broadcast_addrs.append(subnet_bcast)

    for addr in broadcast_addrs:
        for port in WOL_PORTS:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.sendto(packet, (addr, port))
            except OSError:
                pass
