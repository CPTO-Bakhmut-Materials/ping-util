"""Один обмін Echo Request / Echo Reply: відправити, дочекатися своєї відповіді."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .packet import ICMP_ECHO_REPLY, IcmpPacket, build_echo_request, parse_packet

logger = logging.getLogger(__name__)


class Transport(Protocol):
    """Те, що Pinger потребує від сокета. IcmpSocket відповідає цьому протоколу."""

    def send(self, packet: bytes, address: str) -> None: ...

    def receive(self, timeout: float) -> tuple[bytes, float] | None: ...


@dataclass(frozen=True)
class EchoReply:
    """Отримана відповідь на наш запит."""

    source: str
    sequence: int
    ttl: int
    size: int
    rtt_ms: float


class Pinger:
    """Відправляє Echo Request і чекає на Echo Reply з тими самими identifier і sequence."""

    def __init__(
        self,
        transport: Transport,
        address: str,
        identifier: int,
        payload: bytes,
        timeout: float,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.transport = transport
        self.address = address
        self.identifier = identifier
        self.payload = payload
        self.timeout = timeout
        self.clock = clock

    def ping(self, sequence: int) -> EchoReply | None:
        """Відправляє один запит. Повертає відповідь або None, якщо її не було вчасно."""
        packet = build_echo_request(self.identifier, sequence, self.payload)
        send_time = self.clock()
        self.transport.send(packet, self.address)
        logger.debug("sent echo request id=%d seq=%d to %s", self.identifier, sequence, self.address)

        # Тайм-аут рахуємо від моменту відправки, а не від останнього пакета.
        deadline = send_time + self.timeout
        while (remaining := deadline - self.clock()) > 0:
            received = self.transport.receive(remaining)
            if received is None:
                break
            data, receive_time = received

            parsed = parse_packet(data)
            if parsed is None:
                logger.debug("ignored malformed or corrupted packet (%d bytes)", len(data))
                continue
            if not self._is_our_reply(parsed, sequence):
                continue

            return EchoReply(
                source=parsed.ip.source,
                sequence=sequence,
                ttl=parsed.ip.ttl,
                size=parsed.size,
                rtt_ms=(receive_time - send_time) * 1000,
            )

        logger.debug("no reply for seq=%d within %.1f s", sequence, self.timeout)
        return None

    def _is_our_reply(self, packet: IcmpPacket, sequence: int) -> bool:
        icmp = packet.icmp
        if icmp.type == ICMP_ECHO_REPLY and icmp.identifier == self.identifier:
            if icmp.sequence == sequence:
                return True
        logger.debug(
            "ignored packet from %s: type=%d code=%d id=%d seq=%d",
            packet.ip.source, icmp.type, icmp.code, icmp.identifier, icmp.sequence,
        )
        return False
