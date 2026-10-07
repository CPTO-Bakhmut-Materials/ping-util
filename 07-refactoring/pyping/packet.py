"""Формат пакетів: ICMP (RFC 792), заголовок IPv4 (RFC 791), контрольна сума (RFC 1071).

Модуль нічого не знає про сокети й час: він лише перетворює байти
на структури і навпаки. Тому його легко тестувати.
"""

import socket
import struct
from dataclasses import dataclass

# Типи ICMP-повідомлень (RFC 792).
ICMP_ECHO_REPLY = 0
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_CODE = 0

# Заголовок ICMP Echo: type, code, checksum, identifier, sequence number.
ICMP_HEADER_FORMAT = "!BBHHH"
ICMP_HEADER_SIZE = struct.calcsize(ICMP_HEADER_FORMAT)  # 8 байтів

# Заголовок IPv4 без опцій (RFC 791, розділ 3.1): version+IHL, type of service,
# total length, identification, flags+fragment offset, time to live, protocol,
# header checksum, source address, destination address.
IP_HEADER_FORMAT = "!BBHHHBBH4s4s"
IP_HEADER_SIZE = struct.calcsize(IP_HEADER_FORMAT)  # 20 байтів

# Найбільший розмір даних: 65535 (максимум IPv4) - 20 (IP) - 8 (ICMP).
MAX_PAYLOAD_SIZE = 65535 - IP_HEADER_SIZE - ICMP_HEADER_SIZE


@dataclass(frozen=True)
class IPv4Header:
    """Поля заголовка IPv4, які потрібні ping."""

    header_length: int
    ttl: int
    protocol: int
    source: str
    destination: str


@dataclass(frozen=True)
class IcmpHeader:
    """Заголовок ICMP. Для Echo останні 4 байти — identifier і sequence."""

    type: int
    code: int
    identifier: int
    sequence: int


@dataclass(frozen=True)
class IcmpPacket:
    """Отриманий IP-пакет з ICMP-повідомленням усередині."""

    ip: IPv4Header
    icmp: IcmpHeader
    size: int  # розмір ICMP-повідомлення в байтах, без IP-заголовка


def checksum(data: bytes) -> int:
    """Обчислює Internet Checksum за RFC 1071."""
    if len(data) % 2:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) + data[i + 1]

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return ~total & 0xFFFF


def build_payload(size: int) -> bytes:
    """Повертає дані пакета: байти 0x00, 0x01, 0x02, ... довжиною size."""
    return bytes(i & 0xFF for i in range(size))


def build_echo_request(identifier: int, sequence: int, payload: bytes) -> bytes:
    """Збирає ICMP Echo Request (RFC 792) з правильною контрольною сумою."""
    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, ICMP_ECHO_CODE, 0, identifier, sequence
    )
    csum = checksum(header + payload)
    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, ICMP_ECHO_CODE, csum, identifier, sequence
    )
    return header + payload


def parse_ipv4_header(data: bytes) -> IPv4Header:
    """Розбирає заголовок IPv4 на початку data."""
    (
        version_ihl, _tos, _total_length, _identification, _flags_offset,
        ttl, protocol, _header_checksum, source, destination,
    ) = struct.unpack(IP_HEADER_FORMAT, data[:IP_HEADER_SIZE])
    return IPv4Header(
        # IHL — довжина заголовка в 32-бітних словах (молодші 4 біти першого байта).
        header_length=(version_ihl & 0x0F) * 4,
        ttl=ttl,
        protocol=protocol,
        source=socket.inet_ntoa(source),
        destination=socket.inet_ntoa(destination),
    )


def parse_icmp_header(data: bytes) -> IcmpHeader:
    """Розбирає перші 8 байтів ICMP-повідомлення."""
    type_, code, _checksum, identifier, sequence = struct.unpack(
        ICMP_HEADER_FORMAT, data[:ICMP_HEADER_SIZE]
    )
    return IcmpHeader(type=type_, code=code, identifier=identifier, sequence=sequence)


def parse_packet(data: bytes) -> IcmpPacket | None:
    """Розбирає IP-пакет, отриманий з raw-сокета.

    Повертає None для обрізаних пакетів і пакетів з неправильною контрольною сумою.
    """
    if len(data) < IP_HEADER_SIZE:
        return None
    ip = parse_ipv4_header(data)

    message = data[ip.header_length :]
    if len(message) < ICMP_HEADER_SIZE:
        return None
    # Сума всього повідомлення разом із полем checksum дає 0 (RFC 1071).
    if checksum(message) != 0:
        return None

    return IcmpPacket(ip=ip, icmp=parse_icmp_header(message), size=len(message))
