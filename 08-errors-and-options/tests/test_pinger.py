"""Тести Pinger без мережі й без root: сокет замінено на Mock."""

import unittest
from unittest.mock import Mock

from pyping.packet import (
    ICMP_DEST_UNREACHABLE,
    ICMP_ECHO_REQUEST,
    ICMP_TIME_EXCEEDED,
    build_echo_request,
)
from pyping.pinger import EchoReply, IcmpError, Pinger

from .helpers import make_echo_reply, make_icmp_error, make_icmp_message, make_ip_packet

IDENTIFIER = 0x1234
ADDRESS = "10.0.0.2"


def make_pinger(transport: Mock) -> Pinger:
    # Годинник завжди показує 0.0: тайм-аут не спливає сам, а момент
    # отримання кожного пакета задає тест.
    return Pinger(
        transport=transport,
        address=ADDRESS,
        identifier=IDENTIFIER,
        payload=b"",
        timeout=1.0,
        clock=lambda: 0.0,
    )


class PingerTest(unittest.TestCase):
    def test_sends_echo_request(self) -> None:
        transport = Mock()
        transport.receive.return_value = None

        make_pinger(transport).ping(sequence=5)

        transport.send.assert_called_once_with(
            build_echo_request(IDENTIFIER, 5, b""), ADDRESS
        )

    def test_returns_reply(self) -> None:
        transport = Mock()
        transport.receive.return_value = (make_echo_reply(IDENTIFIER, 1, ttl=58), 0.0123)

        reply = make_pinger(transport).ping(sequence=1)

        self.assertEqual(
            reply, EchoReply(source=ADDRESS, sequence=1, ttl=58, size=8, rtt_ms=12.3)
        )

    def test_returns_none_on_timeout(self) -> None:
        transport = Mock()
        transport.receive.return_value = None

        self.assertIsNone(make_pinger(transport).ping(sequence=1))

    def test_skips_foreign_packets(self) -> None:
        transport = Mock()
        # side_effect: кожен виклик receive() повертає наступний елемент списку.
        transport.receive.side_effect = [
            (make_echo_reply(identifier=0x9999, sequence=1), 0.001),  # чужий identifier
            (make_echo_reply(IDENTIFIER, sequence=7), 0.002),  # старий sequence
            (make_ip_packet(make_icmp_message(ICMP_ECHO_REQUEST, 0, IDENTIFIER, 1)), 0.003),  # наш запит на loopback
            (b"\x45\x00\x00", 0.004),  # обрізаний пакет
            (make_echo_reply(IDENTIFIER, sequence=1), 0.005),  # наш!
        ]

        reply = make_pinger(transport).ping(sequence=1)

        assert isinstance(reply, EchoReply)
        self.assertAlmostEqual(reply.rtt_ms, 5.0)
        self.assertEqual(transport.receive.call_count, 5)

    def test_returns_time_exceeded(self) -> None:
        # Маршрутизатор 10.0.0.2 цитує наш запит з sequence=3.
        our_request = make_ip_packet(build_echo_request(IDENTIFIER, 3, b""))
        transport = Mock()
        transport.receive.return_value = (
            make_icmp_error(ICMP_TIME_EXCEEDED, 0, our_request, source="10.0.0.2"), 0.001
        )

        error = make_pinger(transport).ping(sequence=3)

        self.assertEqual(
            error, IcmpError(source="10.0.0.2", sequence=3, message="Time to live exceeded")
        )

    def test_skips_errors_about_foreign_requests(self) -> None:
        foreign_request = make_ip_packet(build_echo_request(0x9999, 3, b""))
        our_request = make_ip_packet(build_echo_request(IDENTIFIER, 3, b""))
        transport = Mock()
        transport.receive.side_effect = [
            (make_icmp_error(ICMP_DEST_UNREACHABLE, 1, foreign_request), 0.001),
            (make_icmp_error(ICMP_DEST_UNREACHABLE, 1, our_request), 0.002),
        ]

        error = make_pinger(transport).ping(sequence=3)

        assert isinstance(error, IcmpError)
        self.assertEqual(error.message, "Destination Host Unreachable")
        self.assertEqual(transport.receive.call_count, 2)


if __name__ == "__main__":
    unittest.main()
