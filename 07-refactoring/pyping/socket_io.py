"""Raw-сокет для ICMP.

Єдине місце в програмі, яке працює з мережею напряму.
"""

import socket
import time
from types import TracebackType

# Поле Total Length заголовка IPv4 має 16 біт, тому більшого пакета не буває.
RECV_BUFFER_SIZE = 65535


class IcmpSocket:
    """Raw-сокет: відправляє ICMP-повідомлення і отримує IP-пакети з тайм-аутом.

    Створення потребує прав root або CAP_NET_RAW, інакше виникає PermissionError.
    """

    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    def send(self, packet: bytes, address: str) -> None:
        # Порт для ICMP не має значення, але адреса для sendto має бути парою (host, port).
        self._sock.sendto(packet, (address, 0))

    def receive(self, timeout: float) -> tuple[bytes, float] | None:
        """Чекає на пакет не довше за timeout секунд.

        Повертає (байти IP-пакета, момент отримання за time.perf_counter)
        або None, якщо час вийшов.
        """
        self._sock.settimeout(timeout)
        try:
            data, _ = self._sock.recvfrom(RECV_BUFFER_SIZE)
        except TimeoutError:
            return None
        return data, time.perf_counter()

    def close(self) -> None:
        self._sock.close()

    def __enter__(self) -> "IcmpSocket":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
