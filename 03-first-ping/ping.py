"""Урок 3: перший справжній ping.

Програма відправляє один ICMP Echo Request через raw-сокет, чекає на
Echo Reply і друкує рядок відповіді з TTL та часом обміну (RTT).
Запуск потребує прав root: sudo python3 ping.py example.com
"""

import argparse
import os
import socket
import struct
import sys
import time

EXIT_OK = 0
EXIT_ERROR = 2

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

DEFAULT_PAYLOAD_SIZE = 56

# Поле Total Length заголовка IPv4 має 16 біт, тому більшого пакета не буває.
RECV_BUFFER_SIZE = 65535


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Розбирає аргументи командного рядка."""
    parser = argparse.ArgumentParser(
        prog="ping",
        description="Надсилає ICMP ECHO_REQUEST до мережевого вузла.",
    )
    parser.add_argument("host", help="ім'я або IPv4-адреса вузла")
    return parser.parse_args(argv)


def resolve(host: str) -> str:
    """Повертає IPv4-адресу вузла у вигляді рядка, наприклад '8.8.8.8'.

    Якщо ім'я не вдалося знайти, виникає socket.gaierror.
    """
    infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_RAW)
    family, type_, proto, canonname, sockaddr = infos[0]
    address = sockaddr[0]
    assert isinstance(address, str)
    return address


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


def parse_ip_header(data: bytes) -> tuple[int, int, str]:
    """Розбирає заголовок IPv4 на початку data.

    Повертає (довжину заголовка в байтах, TTL, адресу відправника).
    """
    (
        version_ihl, _tos, _total_length, _identification, _flags_offset,
        ttl, _protocol, _header_checksum, source, _destination,
    ) = struct.unpack(IP_HEADER_FORMAT, data[:IP_HEADER_SIZE])
    # Молодші 4 біти першого байта (IHL) містять довжину заголовка
    # в 32-бітних словах. Якщо є опції, заголовок довший за 20 байтів.
    header_length = (version_ihl & 0x0F) * 4
    return header_length, ttl, socket.inet_ntoa(source)


def parse_icmp_header(data: bytes) -> tuple[int, int, int, int]:
    """Повертає (type, code, identifier, sequence) ICMP-повідомлення."""
    type_, code, _checksum, identifier, sequence = struct.unpack(
        ICMP_HEADER_FORMAT, data[:ICMP_HEADER_SIZE]
    )
    return type_, code, identifier, sequence


def format_rtt(rtt_ms: float) -> str:
    """Форматує RTT як iputils: приблизно 3 значущі цифри."""
    if rtt_ms >= 99.95:
        return f"{rtt_ms:.0f}"
    if rtt_ms >= 9.995:
        return f"{rtt_ms:.1f}"
    if rtt_ms >= 1:
        return f"{rtt_ms:.2f}"
    return f"{rtt_ms:.3f}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        address = resolve(args.host)
    except socket.gaierror as exc:
        print(f"ping: {args.host}: {exc.strerror}", file=sys.stderr)
        return EXIT_ERROR

    payload_size = DEFAULT_PAYLOAD_SIZE
    total_size = payload_size + ICMP_HEADER_SIZE + IP_HEADER_SIZE
    print(f"PING {args.host} ({address}) {payload_size}({total_size}) bytes of data.")

    identifier = os.getpid() & 0xFFFF
    sequence = 1
    packet = build_echo_request(identifier, sequence, build_payload(payload_size))

    with socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP) as sock:
        send_time = time.perf_counter()
        # Порт для ICMP не має значення, але адреса для sendto має бути парою (host, port).
        sock.sendto(packet, (address, 0))

        while True:
            data, _ = sock.recvfrom(RECV_BUFFER_SIZE)
            receive_time = time.perf_counter()

            ip_header_length, ttl, source = parse_ip_header(data)
            icmp = data[ip_header_length:]
            type_, code, reply_id, reply_seq = parse_icmp_header(icmp)

            # Raw-сокет отримує всі ICMP-пакети, що приходять на комп'ютер.
            # Чекаємо саме на Echo Reply.
            if type_ == ICMP_ECHO_REPLY:
                break

    rtt_ms = (receive_time - send_time) * 1000
    print(
        f"{len(icmp)} bytes from {source}: icmp_seq={reply_seq} ttl={ttl} "
        f"time={format_rtt(rtt_ms)} ms"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
