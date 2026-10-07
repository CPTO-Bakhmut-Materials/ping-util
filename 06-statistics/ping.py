"""Урок 6: статистика.

Наприкінці роботи програма друкує повний підсумок, як системний ping:
кількість запитів і відповідей, відсоток втрат, загальний час роботи
та min/avg/max/mdev часу обміну (RTT). Підрахунок винесено в клас Statistics.
Запуск потребує прав root: sudo python3 ping.py example.com
"""

import argparse
import math
import os
import socket
import struct
import sys
import time

EXIT_OK = 0
EXIT_NO_REPLY = 1
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

# Скільки секунд чекати на відповідь.
DEFAULT_TIMEOUT = 1.0

# Пауза між запитами за замовчуванням, як у системного ping.
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


class Statistics:
    """Накопичує дані про запити й відповіді та формує підсумок.

    Окремі значення RTT не зберігаються: для min/avg/max/mdev достатньо
    кількох сум, тому пам'ять не росте, навіть якщо ping працює годинами.
    """

    def __init__(self) -> None:
        self.transmitted = 0
        self.received = 0
        self.rtt_min = math.inf
        self.rtt_max = 0.0
        self.rtt_sum = 0.0
        self.rtt_sum_squares = 0.0

    def add_sent(self) -> None:
        self.transmitted += 1

    def add_reply(self, rtt_ms: float) -> None:
        self.received += 1
        self.rtt_min = min(self.rtt_min, rtt_ms)
        self.rtt_max = max(self.rtt_max, rtt_ms)
        self.rtt_sum += rtt_ms
        self.rtt_sum_squares += rtt_ms * rtt_ms

    def loss_percent(self) -> float:
        if self.transmitted == 0:
            return 0.0
        return (self.transmitted - self.received) * 100 / self.transmitted

    def rtt_avg(self) -> float:
        return self.rtt_sum / self.received

    def rtt_mdev(self) -> float:
        """Середнє відхилення RTT: sqrt(avg(rtt^2) - avg(rtt)^2), як в iputils."""
        avg = self.rtt_avg()
        variance = self.rtt_sum_squares / self.received - avg * avg
        # Через похибки округлення float дисперсія може вийти трохи меншою за 0.
        return math.sqrt(max(0.0, variance))

    def summary(self, host: str, elapsed_ms: float) -> list[str]:
        """Повертає рядки підсумку в форматі системного ping."""
        lines = [
            f"--- {host} ping statistics ---",
            f"{self.transmitted} packets transmitted, {self.received} received, "
            f"{self.loss_percent():g}% packet loss, time {elapsed_ms:.0f}ms",
        ]
        if self.received > 0:
            lines.append(
                f"rtt min/avg/max/mdev = {self.rtt_min:.3f}/{self.rtt_avg():.3f}/"
                f"{self.rtt_max:.3f}/{self.rtt_mdev():.3f} ms"
            )
        return lines


def send_echo_request(
    sock: socket.socket, address: str, identifier: int, sequence: int, payload: bytes
) -> float:
    """Відправляє Echo Request і повертає момент відправки (time.perf_counter)."""
    packet = build_echo_request(identifier, sequence, payload)
    send_time = time.perf_counter()
    sock.sendto(packet, (address, 0))
    return send_time


def receive_reply(
    sock: socket.socket, identifier: int, sequence: int, timeout: float
) -> tuple[str, int, int, float] | None:
    """Чекає на Echo Reply з нашими identifier і sequence не довше за timeout секунд.

    Повертає (адресу відправника, TTL, розмір ICMP-повідомлення, момент отримання)
    або None, якщо відповідь не прийшла вчасно. Чужі й пошкоджені пакети пропускає.
    """
    deadline = time.perf_counter() + timeout

    while True:
        # Тайм-аут рахуємо від початку очікування, а не від останнього пакета:
        # інакше потік чужих пакетів продовжував би очікування без кінця.
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return None
        sock.settimeout(remaining)

        try:
            data, _ = sock.recvfrom(RECV_BUFFER_SIZE)
        except TimeoutError:
            return None
        receive_time = time.perf_counter()

        if len(data) < IP_HEADER_SIZE:
            continue
        ip_header_length, ttl, source = parse_ip_header(data)
        icmp = data[ip_header_length:]
        if len(icmp) < ICMP_HEADER_SIZE:
            continue

        # Сума всього повідомлення разом із полем checksum дає 0 (RFC 1071).
        if checksum(icmp) != 0:
            continue

        type_, code, reply_id, reply_seq = parse_icmp_header(icmp)
        if type_ != ICMP_ECHO_REPLY or reply_id != identifier or reply_seq != sequence:
            continue

        return source, ttl, len(icmp), receive_time


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        address = resolve(args.host)
    except socket.gaierror as exc:
        print(f"ping: {args.host}: {exc.strerror}", file=sys.stderr)
        return EXIT_ERROR

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError as exc:
        print(f"ping: socket: {exc.strerror}", file=sys.stderr)
        print("ping: raw-сокет потребує прав root, запустіть через sudo", file=sys.stderr)
        return EXIT_ERROR

    payload_size = DEFAULT_PAYLOAD_SIZE
    total_size = payload_size + ICMP_HEADER_SIZE + IP_HEADER_SIZE
    print(f"PING {args.host} ({address}) {payload_size}({total_size}) bytes of data.")

    identifier = os.getpid() & 0xFFFF
    payload = build_payload(payload_size)
    stats = Statistics()
    start_time = time.perf_counter()

    with sock:
        try:
            while args.count is None or stats.transmitted < args.count:
                sequence = (stats.transmitted + 1) & SEQUENCE_MASK
                try:
                    send_time = send_echo_request(sock, address, identifier, sequence, payload)
                except OSError as exc:
                    print(f"ping: sendto: {exc.strerror}", file=sys.stderr)
                    return EXIT_ERROR
                stats.add_sent()

                reply = receive_reply(sock, identifier, sequence, DEFAULT_TIMEOUT)
                if reply is None:
                    print(f"no answer yet for icmp_seq={sequence}")
                else:
                    source, ttl, size, receive_time = reply
                    rtt_ms = (receive_time - send_time) * 1000
                    print(
                        f"{size} bytes from {source}: icmp_seq={sequence} ttl={ttl} "
                        f"time={format_rtt(rtt_ms)} ms"
                    )
                    stats.add_reply(rtt_ms)

                # Після останнього запиту чекати не потрібно.
                if args.count is not None and stats.transmitted >= args.count:
                    break
                # Інтервал рахуємо від моменту відправки: час очікування
                # відповіді вже є частиною паузи.
                elapsed = time.perf_counter() - send_time
                time.sleep(max(0.0, args.interval - elapsed))
        except KeyboardInterrupt:
            # Ctrl+C зупиняє цикл, але програма ще має надрукувати підсумок.
            pass

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    print()
    for line in stats.summary(args.host, elapsed_ms):
        print(line)
    return EXIT_OK if stats.received > 0 else EXIT_NO_REPLY


if __name__ == "__main__":
    sys.exit(main())
