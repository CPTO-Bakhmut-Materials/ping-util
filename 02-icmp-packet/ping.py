"""Урок 2: формування пакета ICMP Echo Request.

До скелета з уроку 1 додано збирання ICMP-пакета та обчислення
контрольної суми за RFC 1071. Пакет ще не відправляється,
програма лише показує його вміст.
"""

import argparse
import os
import socket
import struct
import sys

EXIT_OK = 0
EXIT_ERROR = 2

# Тип і код повідомлення Echo Request (RFC 792, сторінка 14).
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_CODE = 0

# Заголовок ICMP Echo: type (1 байт), code (1 байт), checksum (2 байти),
# identifier (2 байти), sequence number (2 байти). '!' означає мережевий
# порядок байтів (big-endian).
ICMP_HEADER_FORMAT = "!BBHHH"
ICMP_HEADER_SIZE = struct.calcsize(ICMP_HEADER_FORMAT)  # 8 байтів

# Розмір IPv4-заголовка без опцій (RFC 791, розділ 3.1).
IP_HEADER_SIZE = 20

# Стільки байтів даних за замовчуванням відправляє системний ping.
DEFAULT_PAYLOAD_SIZE = 56


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
    # Для AF_INET адреса завжди є рядком, але тип sockaddr описано для всіх
    # сімейств адрес (str | int), тому явно звужуємо його до str.
    assert isinstance(address, str)
    return address


def checksum(data: bytes) -> int:
    """Обчислює Internet Checksum за RFC 1071.

    Дані розглядаються як послідовність 16-бітних слів. Слова додаються
    в арифметиці з доповненням до одиниці (переноси зі старших розрядів
    повертаються в молодші), а результатом є інверсія суми.
    """
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
    # Спочатку пакуємо заголовок з нульовою контрольною сумою:
    # за RFC 792 поле checksum під час обчислення має дорівнювати нулю.
    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, ICMP_ECHO_CODE, 0, identifier, sequence
    )
    csum = checksum(header + payload)
    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, ICMP_ECHO_CODE, csum, identifier, sequence
    )
    return header + payload


def hexdump(data: bytes, width: int = 16) -> str:
    """Повертає рядки виду '0000  08 00 a7 3f ...' по width байтів у кожному."""
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        lines.append(f"{offset:04x}  {chunk.hex(' ')}")
    return "\n".join(lines)


def describe_packet(packet: bytes) -> str:
    """Повертає опис полів заголовка ICMP у читабельному вигляді."""
    type_, code, csum, identifier, sequence = struct.unpack(
        ICMP_HEADER_FORMAT, packet[:ICMP_HEADER_SIZE]
    )
    return (
        f"type={type_} code={code} checksum=0x{csum:04x} "
        f"id={identifier} seq={sequence} payload={len(packet) - ICMP_HEADER_SIZE} bytes"
    )


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

    # Identifier має 16 біт, тому залишаємо лише молодші 16 біт PID.
    identifier = os.getpid() & 0xFFFF
    packet = build_echo_request(identifier, 1, build_payload(payload_size))

    print(describe_packet(packet))
    print(hexdump(packet))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
