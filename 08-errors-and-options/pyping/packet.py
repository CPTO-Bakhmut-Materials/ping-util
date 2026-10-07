"""Формат пакетів: ICMP (RFC 792), заголовок IPv4 (RFC 791), контрольна сума (RFC 1071).

Модуль нічого не знає про сокети й час: він лише перетворює байти
на структури і навпаки. Тому його легко тестувати.
"""

import socket
import struct
from dataclasses import dataclass

# Типи ICMP-повідомлень (RFC 792).
ICMP_ECHO_REPLY = 0
ICMP_DEST_UNREACHABLE = 3
ICMP_ECHO_REQUEST = 8
ICMP_TIME_EXCEEDED = 11
ICMP_ECHO_CODE = 0

# Destination Unreachable, code 4: потрібна фрагментація, але встановлено DF.
# У такому повідомленні молодші 16 біт поля «unused» містять MTU (RFC 1191, розділ 4).
ICMP_FRAG_NEEDED = 4

# Тексти повідомлень такі самі, як у iputils (функція pr_icmph у ping/ping.c).
# Коди 0-5: RFC 792; 6-12: RFC 1122, розділ 3.2.2.1; 13-15: RFC 1812, розділ 5.2.7.1.
DEST_UNREACHABLE_MESSAGES = {
    0: "Destination Net Unreachable",
    1: "Destination Host Unreachable",
    2: "Destination Protocol Unreachable",
    3: "Destination Port Unreachable",
    4: "Frag needed and DF set",
    5: "Source Route Failed",
    6: "Destination Net Unknown",
    7: "Destination Host Unknown",
    8: "Source Host Isolated",
    9: "Destination Net Prohibited",
    10: "Destination Host Prohibited",
    11: "Destination Net Unreachable for Type of Service",
    12: "Destination Host Unreachable for Type of Service",
    13: "Packet filtered",
    14: "Precedence Violation",
    15: "Precedence Cutoff",
}
TIME_EXCEEDED_MESSAGES = {
    0: "Time to live exceeded",
    1: "Frag reassembly time exceeded",
}

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
    """Заголовок ICMP.

    Для Echo останні 4 байти — identifier і sequence. У повідомленнях про
    помилки ці 4 байти називаються «unused» (RFC 792), і їх значення
    зазвичай не має сенсу (виняток — MTU для ICMP_FRAG_NEEDED).
    """

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
    body: bytes  # усе, що йде після 8 байтів заголовка ICMP


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

    return IcmpPacket(
        ip=ip,
        icmp=parse_icmp_header(message),
        size=len(message),
        body=message[ICMP_HEADER_SIZE:],
    )


def parse_quoted_header(body: bytes) -> IcmpHeader | None:
    """Дістає заголовок нашого запиту з повідомлення про помилку.

    За RFC 792 повідомлення Destination Unreachable і Time Exceeded містять
    IP-заголовок пакета, що спричинив помилку, і перші 64 біти (8 байтів) його
    даних. Для Echo Request ці 8 байтів — увесь заголовок ICMP з identifier і sequence.
    """
    if len(body) < IP_HEADER_SIZE:
        return None
    quoted_ip = parse_ipv4_header(body)
    quoted = body[quoted_ip.header_length :]
    if quoted_ip.protocol != socket.IPPROTO_ICMP or len(quoted) < ICMP_HEADER_SIZE:
        return None
    return parse_icmp_header(quoted)


def describe_error(header: IcmpHeader) -> str | None:
    """Повертає текст помилки, як у iputils, або None, якщо це не помилка."""
    if header.type == ICMP_DEST_UNREACHABLE:
        if header.code == ICMP_FRAG_NEEDED:
            return f"Frag needed and DF set (mtu = {header.sequence})"
        return DEST_UNREACHABLE_MESSAGES.get(
            header.code, f"Dest Unreachable, Bad Code: {header.code}"
        )
    if header.type == ICMP_TIME_EXCEEDED:
        return TIME_EXCEEDED_MESSAGES.get(header.code, f"Time exceeded, Bad Code: {header.code}")
    return None
