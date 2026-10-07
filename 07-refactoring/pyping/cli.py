"""Командний рядок: аргументи, головний цикл і вивід у форматі системного ping."""

import argparse
import logging
import os
import socket
import sys
import time

from .packet import ICMP_HEADER_SIZE, IP_HEADER_SIZE, build_payload
from .pinger import EchoReply, Pinger
from .socket_io import IcmpSocket
from .stats import Statistics

EXIT_OK = 0
EXIT_NO_REPLY = 1
EXIT_ERROR = 2

DEFAULT_PAYLOAD_SIZE = 56
DEFAULT_TIMEOUT = 1.0
DEFAULT_INTERVAL = 1.0

# Sequence Number має 16 біт: після 65535 лічильник повертається до 0.
SEQUENCE_MASK = 0xFFFF


def positive_int(text: str) -> int:
    """Тип аргументу для argparse: ціле число, більше за 0."""
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0: {text!r}")
    return value


def positive_float(text: str) -> float:
    """Тип аргументу для argparse: дійсне число, більше за 0."""
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0: {text!r}")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Розбирає аргументи командного рядка."""
    parser = argparse.ArgumentParser(
        prog="ping",
        description="Надсилає ICMP ECHO_REQUEST до мережевого вузла.",
    )
    parser.add_argument("host", help="ім'я або IPv4-адреса вузла")
    parser.add_argument(
        "-c", dest="count", type=positive_int, default=None,
        help="зупинитися після COUNT запитів (за замовчуванням — до Ctrl+C)",
    )
    parser.add_argument(
        "-i", dest="interval", type=positive_float, default=DEFAULT_INTERVAL,
        help=f"пауза між запитами в секундах (за замовчуванням {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "-v", dest="verbose", action="store_true",
        help="друкувати налагоджувальні повідомлення в stderr",
    )
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


def format_rtt(rtt_ms: float) -> str:
    """Форматує RTT як iputils: приблизно 3 значущі цифри."""
    if rtt_ms >= 99.95:
        return f"{rtt_ms:.0f}"
    if rtt_ms >= 9.995:
        return f"{rtt_ms:.1f}"
    if rtt_ms >= 1:
        return f"{rtt_ms:.2f}"
    return f"{rtt_ms:.3f}"


def format_reply(reply: EchoReply) -> str:
    return (
        f"{reply.size} bytes from {reply.source}: icmp_seq={reply.sequence} "
        f"ttl={reply.ttl} time={format_rtt(reply.rtt_ms)} ms"
    )


def run(args: argparse.Namespace) -> int:
    """Головний цикл ping. Повертає код завершення."""
    try:
        address = resolve(args.host)
    except socket.gaierror as exc:
        print(f"ping: {args.host}: {exc.strerror}", file=sys.stderr)
        return EXIT_ERROR

    try:
        sock = IcmpSocket()
    except PermissionError as exc:
        print(f"ping: socket: {exc.strerror}", file=sys.stderr)
        print("ping: raw-сокет потребує прав root, запустіть через sudo", file=sys.stderr)
        return EXIT_ERROR

    payload_size = DEFAULT_PAYLOAD_SIZE
    total_size = payload_size + ICMP_HEADER_SIZE + IP_HEADER_SIZE
    print(f"PING {args.host} ({address}) {payload_size}({total_size}) bytes of data.")

    pinger = Pinger(
        transport=sock,
        address=address,
        identifier=os.getpid() & 0xFFFF,
        payload=build_payload(payload_size),
        timeout=DEFAULT_TIMEOUT,
    )
    stats = Statistics()
    start_time = time.perf_counter()

    with sock:
        try:
            while args.count is None or stats.transmitted < args.count:
                sequence = (stats.transmitted + 1) & SEQUENCE_MASK
                iteration_start = time.perf_counter()
                stats.add_sent()
                try:
                    reply = pinger.ping(sequence)
                except OSError as exc:
                    print(f"ping: sendto: {exc.strerror}", file=sys.stderr)
                    return EXIT_ERROR

                if reply is None:
                    print(f"no answer yet for icmp_seq={sequence}")
                else:
                    print(format_reply(reply))
                    stats.add_reply(reply.rtt_ms)

                if args.count is not None and stats.transmitted >= args.count:
                    break
                elapsed = time.perf_counter() - iteration_start
                time.sleep(max(0.0, args.interval - elapsed))
        except KeyboardInterrupt:
            pass

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    print()
    for line in stats.summary(args.host, elapsed_ms):
        print(line)
    return EXIT_OK if stats.received > 0 else EXIT_NO_REPLY


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return run(args)
