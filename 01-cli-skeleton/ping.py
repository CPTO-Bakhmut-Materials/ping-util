"""Урок 1: скелет утиліти ping.

Програма приймає ім'я вузла, перетворює його на IPv4-адресу
і друкує перший рядок виводу, як це робить системний ping.
Пакети ще не відправляються.
"""

import argparse
import socket
import sys

# Коди завершення такі самі, як у ping з iputils (див. man 8 ping, розділ EXIT STATUS).
EXIT_OK = 0
EXIT_ERROR = 2


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
    # Кожен елемент: (family, type, proto, canonname, sockaddr),
    # де sockaddr для IPv4 має вигляд (address, port).
    family, type_, proto, canonname, sockaddr = infos[0]
    address = sockaddr[0]
    # Для AF_INET адреса завжди є рядком, але тип sockaddr описано для всіх
    # сімейств адрес (str | int), тому явно звужуємо його до str.
    assert isinstance(address, str)
    return address


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        address = resolve(args.host)
    except socket.gaierror as exc:
        print(f"ping: {args.host}: {exc.strerror}", file=sys.stderr)
        return EXIT_ERROR

    print(f"PING {args.host} ({address})")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
