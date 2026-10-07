"""Допоміжні функції для тестів: збирають пакети, які «прийшли б» з мережі."""

import socket
import struct

from pyping.packet import (
    ICMP_ECHO_REPLY,
    ICMP_HEADER_FORMAT,
    IP_HEADER_FORMAT,
    checksum,
)


def make_ip_packet(
    icmp_message: bytes, ttl: int = 64, source: str = "10.0.0.2", ihl: int = 5
) -> bytes:
    """Загортає ICMP-повідомлення в IPv4-пакет (version=4, protocol=ICMP)."""
    header = struct.pack(
        IP_HEADER_FORMAT,
        (4 << 4) | ihl, 0, 20 + len(icmp_message), 0, 0, ttl, socket.IPPROTO_ICMP, 0,
        socket.inet_aton(source), socket.inet_aton("10.0.0.1"),
    )
    # Якщо IHL > 5, після 20 байтів ідуть опції. Для тесту достатньо нулів.
    return header + bytes((ihl - 5) * 4) + icmp_message


def make_icmp_message(
    type_: int, code: int, identifier: int, sequence: int, payload: bytes = b""
) -> bytes:
    """Збирає ICMP-повідомлення з правильною контрольною сумою."""
    header = struct.pack(ICMP_HEADER_FORMAT, type_, code, 0, identifier, sequence)
    csum = checksum(header + payload)
    return struct.pack(ICMP_HEADER_FORMAT, type_, code, csum, identifier, sequence) + payload


def make_echo_reply(
    identifier: int, sequence: int, payload: bytes = b"", ttl: int = 64, source: str = "10.0.0.2"
) -> bytes:
    """Повний IP-пакет з Echo Reply, як його повертає raw-сокет."""
    message = make_icmp_message(ICMP_ECHO_REPLY, 0, identifier, sequence, payload)
    return make_ip_packet(message, ttl=ttl, source=source)
