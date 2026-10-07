# Урок 7. Рефакторинг

[← Урок 6](../06-statistics/README.md) · [До змісту](../README.md) · [Урок 8 →](../08-errors-and-options/README.md)

## Мета уроку

**Рефакторинг** — це зміна структури коду без зміни його поведінки
([Martin Fowler, Refactoring](https://refactoring.com/)). Після цього уроку
програма друкує те саме, що й в уроці 6, але:

- код розкладено по модулях, і кожен модуль відповідає за одну річ;
- кортежі з позиційними полями замінено на `dataclasses` з іменованими полями;
- логіку очікування відповіді можна протестувати **без мережі й без root** завдяки `unittest.mock`;
- є налагоджувальний режим `-v` на основі `logging`.

Окупиться це в [уроці 8](../08-errors-and-options/README.md): там нові можливості
додаються точково, у потрібний модуль.

## Що було не так в уроці 6

| Проблема | Приклад |
|---|---|
| усе в одному файлі на 337 рядків | формат пакетів, сокет, цикл, статистика й вивід перемішані |
| `main()` на 64 рядки робить усе | щоб змінити вивід, треба розібратися з сокетами |
| кортежі з позиційними полями | `source, ttl, size, receive_time = reply`: переплутаєте порядок — і mypy не допоможе, бо `ttl` і `size` обидва `int` |
| `receive_reply()` не має тестів | приймає `socket.socket`, тож для тесту потрібні мережа і root |
| немає способу подивитися, що відбувається | чому програма не бачить відповідь? Відкинуто через checksum? Чужий id? |

## Нова структура

```
07-refactoring/
├── ping.py              ← точка входу: python3 ping.py ... (як раніше)
├── pyping/              ← пакет з логікою
│   ├── __init__.py
│   ├── __main__.py      ← запуск як python3 -m pyping ...
│   ├── packet.py        ← байти ↔ структури: ICMP, IPv4, checksum
│   ├── socket_io.py     ← raw-сокет: send / receive з тайм-аутом
│   ├── pinger.py        ← один обмін: відправити запит, дочекатися своєї відповіді
│   ├── stats.py         ← Statistics
│   └── cli.py           ← аргументи, головний цикл, форматування виводу
└── tests/
    ├── __init__.py
    ├── helpers.py       ← збирання «вхідних» пакетів для тестів
    ├── test_packet.py
    ├── test_pinger.py   ← тести з Mock замість сокета
    ├── test_stats.py
    └── test_cli.py
```

Залежності між модулями (стрілка означає «імпортує»):

```
cli.py ──┬──▶ pinger.py ──▶ packet.py
         ├──▶ socket_io.py
         ├──▶ stats.py
         └──▶ packet.py

pinger.py працює з будь-яким об'єктом, що відповідає протоколу Transport.
IcmpSocket з socket_io.py — один із таких об'єктів, але pinger.py його НЕ імпортує.
```

| Модуль | Відповідальність | Знає про мережу? | Тестується без root? |
|---|---|---|---|
| `packet.py` | формат байтів (RFC 791, 792, 1071) | ні | так |
| `socket_io.py` | системні виклики сокета | **так** | ні (тому він мінімальний) |
| `pinger.py` | логіка зіставлення запиту й відповіді | ні, працює з `Transport` | **так, з Mock** |
| `stats.py` | підрахунок статистики | ні | так |
| `cli.py` | аргументи, цикл, вивід | через інші модулі | частково |

Принцип: **ізолювати код, що працює із зовнішнім світом** (сокет, годинник), в
маленьких модулях. Усе інше тоді стає «чистою» логікою, яку легко тестувати.

---

## Теорія

### Модулі та пакети

**Модуль** — це файл `.py`, а **пакет** — папка з модулями та файлом `__init__.py`
([Python Tutorial: Modules](https://docs.python.org/3/tutorial/modules.html),
[Packages](https://docs.python.org/3/tutorial/modules.html#packages)).

- **Відносний імпорт** `from .packet import checksum` означає «з модуля `packet` того самого пакета» ([Intra-package References](https://docs.python.org/3/tutorial/modules.html#intra-package-references)).
- **`__main__.py`** виконується командою `python3 -m pyping` ([`__main__.py` у пакетах](https://docs.python.org/3/library/__main__.html#main-py-in-python-packages), [`-m`](https://docs.python.org/3/using/cmdline.html#cmdoption-m)).
- `ping.py` у корені лишився, тому запуск такий самий, як у попередніх уроках.

### dataclasses

Декоратор [`@dataclass`](https://docs.python.org/3/library/dataclasses.html)
([PEP 557](https://peps.python.org/pep-0557/)) генерує `__init__`, `__repr__` і
`__eq__` за анотаціями полів:

```python
@dataclass(frozen=True)
class EchoReply:
    source: str
    sequence: int
    ttl: int
    size: int
    rtt_ms: float
```

Порівняйте:

```python
# Урок 6: кортеж
source, ttl, size, receive_time = reply           # порядок треба пам'ятати
print(f"... ttl={ttl} ...")

# Урок 7: dataclass
print(f"... ttl={reply.ttl} ...")                 # ім'я замість позиції
>>> reply
EchoReply(source='10.0.0.2', sequence=1, ttl=64, size=64, rtt_ms=0.134)   # читабельний repr
>>> reply == EchoReply(source='10.0.0.2', sequence=1, ttl=64, size=64, rtt_ms=0.134)
True                                              # __eq__ — зручно в тестах
```

- `frozen=True` робить об'єкт **незмінним** ([frozen instances](https://docs.python.org/3/library/dataclasses.html#frozen-instances)). Отриманий пакет чи відповідь не мають змінюватися після створення.
- `Statistics` — звичайний (не frozen) `@dataclass` з [значеннями за замовчуванням](https://docs.python.org/3/library/dataclasses.html#dataclasses.field): ручний `__init__` з уроку 6 більше не потрібен.
- Поле `IcmpHeader.type` не конфліктує з вбудованою функцією `type`, бо це атрибут об'єкта (`header.type`), а не змінна. Тому підкреслення, як у локальній змінній `type_` з уроку 2, тут не потрібне.

### Протоколи та підстановка залежностей

`Pinger` потребує від сокета лише два методи. Опишемо їх як **протокол**
([`typing.Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol),
[PEP 544](https://peps.python.org/pep-0544/)):

```python
class Transport(Protocol):
    def send(self, packet: bytes, address: str) -> None: ...
    def receive(self, timeout: float) -> tuple[bytes, float] | None: ...
```

Будь-який об'єкт з такими методами підходить як `Transport`. Наслідувати нічого не
потрібно: mypy перевіряє **структуру** ([structural subtyping](https://mypy.readthedocs.io/en/stable/protocols.html)).
`IcmpSocket` має ці методи, тому підходить, хоча `pinger.py` про нього не знає.

`Pinger` не створює сокет сам, а **отримує** його в конструкторі. Це називається
**підстановка залежностей** ([dependency injection](https://en.wikipedia.org/wiki/Dependency_injection)).
У програмі передаємо справжній `IcmpSocket`, а в тесті — `Mock`.

Так само підставляємо годинник: `clock: Callable[[], float] = time.perf_counter`
([`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)).
У тесті передаємо `lambda: 0.0`, і час «не йде».

### unittest.mock

[`unittest.mock.Mock`](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock) —
об'єкт, який приймає будь-які виклики методів і запам'ятовує їх:

| Можливість | Приклад | Документація |
|---|---|---|
| задати результат | `transport.receive.return_value = None` | [return_value](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.return_value) |
| послідовність результатів | `transport.receive.side_effect = [пакет1, пакет2]` | [side_effect](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.side_effect) |
| перевірити виклик | `transport.send.assert_called_once_with(packet, "10.0.0.2")` | [assert_called_once_with](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.assert_called_once_with) |
| кількість викликів | `transport.receive.call_count` | [call_count](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock.call_count) |

### logging

Модуль [`logging`](https://docs.python.org/3/library/logging.html)
([Logging HOWTO](https://docs.python.org/3/howto/logging.html)) — стандартний спосіб
друкувати діагностику:

- `logger = logging.getLogger(__name__)` — окремий логер для кожного модуля, з ім'ям на зразок `pyping.pinger` ([рекомендація з HOWTO](https://docs.python.org/3/howto/logging.html#advanced-logging-tutorial));
- `logger.debug("... %s", value)` — повідомлення рівня DEBUG. Рядок форматується **лише якщо** повідомлення буде показано ([optimization](https://docs.python.org/3/howto/logging.html#optimization));
- [`logging.basicConfig(level=..., format=...)`](https://docs.python.org/3/library/logging.html#logging.basicConfig) — налаштування в одному місці (`cli.main`): з `-v` показуємо DEBUG, без нього лише WARNING і вище. Вивід іде в stderr.

### Оператор `:=`

```python
while (remaining := deadline - self.clock()) > 0:
```

[Вираз присвоєння](https://docs.python.org/3/reference/expressions.html#assignment-expressions)
(«моржовий оператор», [PEP 572](https://peps.python.org/pep-0572/)) обчислює значення,
записує його в змінну і тут же використовує в умові. Він замінює зв'язку
`while True: remaining = ...; if remaining <= 0: break` з уроку 4.

---

## Практика: модуль за модулем

### `packet.py`: байти ↔ структури

Сюди переїхали константи, `checksum()`, `build_payload()`, `build_echo_request()`.
Функції розбору тепер повертають dataclasses:

```python
@dataclass(frozen=True)
class IcmpPacket:
    """Отриманий IP-пакет з ICMP-повідомленням усередині."""

    ip: IPv4Header
    icmp: IcmpHeader
    size: int  # розмір ICMP-повідомлення в байтах, без IP-заголовка


def parse_packet(data: bytes) -> IcmpPacket | None:
    if len(data) < IP_HEADER_SIZE:
        return None
    ip = parse_ipv4_header(data)

    message = data[ip.header_length :]
    if len(message) < ICMP_HEADER_SIZE:
        return None
    if checksum(message) != 0:
        return None

    return IcmpPacket(ip=ip, icmp=parse_icmp_header(message), size=len(message))
```

Перевірки довжини й контрольної суми з `receive_reply()` (урок 4) зібрано в
`parse_packet()`. Тепер це одне місце, яке відповідає на питання «чи це коректний
ICMP-пакет?».

Також додано `MAX_PAYLOAD_SIZE = 65535 - 20 - 8`, який знадобиться в уроці 8.

### `socket_io.py`: тонка обгортка над сокетом

```python
class IcmpSocket:
    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    def send(self, packet: bytes, address: str) -> None:
        self._sock.sendto(packet, (address, 0))

    def receive(self, timeout: float) -> tuple[bytes, float] | None:
        self._sock.settimeout(timeout)
        try:
            data, _ = self._sock.recvfrom(RECV_BUFFER_SIZE)
        except TimeoutError:
            return None
        return data, time.perf_counter()

    def close(self) -> None: ...
    def __enter__(self) -> "IcmpSocket": ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
```

- У модулі **немає логіки**, лише системні виклики. Тому його не потрібно тестувати з mock: тестувати тут нічого.
- `_sock` з підкресленням — «внутрішній» атрибут ([PEP 8](https://peps.python.org/pep-0008/#method-names-and-instance-variables)).
- `__enter__` / `__exit__` роблять `IcmpSocket` context manager, тож `with sock:` працює як раніше ([протокол context manager](https://docs.python.org/3/reference/datamodel.html#context-managers)). Анотація `"IcmpSocket"` у лапках — [forward reference](https://peps.python.org/pep-0484/#forward-references), бо клас ще не визначено повністю.

### `pinger.py`: логіка одного обміну

Колишні `send_echo_request()` і `receive_reply()` разом:

```python
class Pinger:
    def __init__(self, transport: Transport, address: str, identifier: int,
                 payload: bytes, timeout: float,
                 clock: Callable[[], float] = time.perf_counter) -> None: ...

    def ping(self, sequence: int) -> EchoReply | None:
        packet = build_echo_request(self.identifier, sequence, self.payload)
        send_time = self.clock()
        self.transport.send(packet, self.address)
        logger.debug("sent echo request id=%d seq=%d to %s", self.identifier, sequence, self.address)

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
```

Тепер `rtt_ms` рахує `Pinger`, і результат — готовий `EchoReply`. Тому `cli.py` не
займається арифметикою часу.

### `stats.py`

Клас `Statistics` з уроку 6 став `@dataclass`. Методи не змінилися.

### `cli.py`

`parse_args()`, `resolve()`, `format_rtt()` і головний цикл. Вивід одного рядка
винесено в окрему функцію `format_reply(reply: EchoReply) -> str`, яку легко тестувати.
Новий прапорець:

```python
    parser.add_argument(
        "-v", dest="verbose", action="store_true",
        help="друкувати налагоджувальні повідомлення в stderr",
    )
```

[`action="store_true"`](https://docs.python.org/3/library/argparse.html#action) —
опція без значення: є `-v` → `True`, немає → `False`.

```python
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return run(args)
```

---

## Тести з mock

Найважливіше в уроці: тест, який було неможливо написати в уроках 4–6.

```python
def make_pinger(transport: Mock) -> Pinger:
    return Pinger(transport=transport, address=ADDRESS, identifier=IDENTIFIER,
                  payload=b"", timeout=1.0, clock=lambda: 0.0)


class PingerTest(unittest.TestCase):
    def test_skips_foreign_packets(self) -> None:
        transport = Mock()
        transport.receive.side_effect = [
            (make_echo_reply(identifier=0x9999, sequence=1), 0.001),  # чужий identifier
            (make_echo_reply(IDENTIFIER, sequence=7), 0.002),  # старий sequence
            (make_ip_packet(make_icmp_message(ICMP_ECHO_REQUEST, 0, IDENTIFIER, 1)), 0.003),  # наш запит на loopback
            (b"\x45\x00\x00", 0.004),  # обрізаний пакет
            (make_echo_reply(IDENTIFIER, sequence=1), 0.005),  # наш!
        ]

        reply = make_pinger(transport).ping(sequence=1)

        assert reply is not None
        self.assertAlmostEqual(reply.rtt_ms, 5.0)
        self.assertEqual(transport.receive.call_count, 5)
```

Усі сценарії з уроків 3–4 (чужі відповіді, свій запит на loopback, обрізані пакети)
перевіряються за мілісекунди, без мережі та без root. Годинник «стоїть» на 0.0, тому
RTT дорівнює моменту отримання, який задав тест: `0.005 с = 5.0 мс`.

`tests/helpers.py` збирає пакети, які «прийшли б» з мережі: `make_ip_packet()`,
`make_icmp_message()`, `make_echo_reply()`.

`assert reply is not None` — звуження типу для mypy ([урок 1](../01-cli-skeleton/README.md#що-mypy-знаходить-приклад-з-нашого-коду)):
після нього mypy знає, що `reply` має тип `EchoReply`, і дозволяє звернутися до `reply.rtt_ms`.

Запуск усіх тестів з папки уроку ([test discovery](https://docs.python.org/3/library/unittest.html#test-discovery)):

```console
$ python3 -m unittest
...........................
Ran 27 tests in 0.004s
OK
$ ../.venv/bin/mypy --strict .
Success: no issues found in 14 source files
```

---

## Запуск

Поведінка **не змінилася**:

```console
$ ../netlab/netlab.sh 'python3 ping.py -c 2 10.0.0.2'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.134 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=0.132 ms

--- 10.0.0.2 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1000ms
rtt min/avg/max/mdev = 0.132/0.133/0.134/0.001 ms

$ ../netlab/netlab.sh 'python3 -m pyping -c 1 10.0.0.2'     # те саме через -m
```

**Новий режим `-v`.** Паралельно працює системний ping, а наш пінгує «мовчазну» адресу:

```console
$ ../netlab/netlab.sh 'ping -q -c 30 -i 0.05 10.0.0.2 >/dev/null & sleep 0.2; python3 ping.py -c 1 -v 10.1.0.99'
DEBUG pyping.pinger: sent echo request id=61122 seq=1 to 10.1.0.99
DEBUG pyping.pinger: ignored packet from 10.0.0.2: type=0 code=0 id=61120 seq=8
DEBUG pyping.pinger: ignored packet from 10.0.0.2: type=0 code=0 id=61120 seq=9
DEBUG pyping.pinger: ignored packet from 10.0.0.2: type=0 code=0 id=61120 seq=10
...
DEBUG pyping.pinger: no reply for seq=1 within 1.0 s
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
no answer yet for icmp_seq=1
...
```

Видно, що прийшли чужі Echo Reply з `id=61120` (PID системного ping), і чому їх
відкинуто. Зверніть увагу: PID обох процесів відрізняються лише на 2. Саме тому
identifier потрібно перевіряти точно.

(DEBUG-рядки йдуть у stderr, а звичайний вивід у stdout, тому в терміналі вони можуть
перемішатися в іншому порядку.)

## Підсумок: що дав рефакторинг

| | Урок 6 | Урок 7 |
|---|---|---|
| файлів коду | 1 (337 рядків) | 6 модулів, найбільший — 162 рядки |
| тестів | 22 | 27 |
| логіка очікування відповіді під тестами | ні | **так** (`test_pinger.py`) |
| налагоджувальний вивід | немає | `-v` |
| поведінка | — | **та сама** |

## Повний код

- [`ping.py`](ping.py)
- [`pyping/packet.py`](pyping/packet.py), [`pyping/socket_io.py`](pyping/socket_io.py), [`pyping/pinger.py`](pyping/pinger.py), [`pyping/stats.py`](pyping/stats.py), [`pyping/cli.py`](pyping/cli.py), [`pyping/__main__.py`](pyping/__main__.py)
- [`tests/`](tests/)

## Використані функції та модулі

| Що | Документація |
|---|---|
| модулі та пакети | <https://docs.python.org/3/tutorial/modules.html> |
| відносні імпорти | <https://docs.python.org/3/tutorial/modules.html#intra-package-references> |
| `__main__.py`, `python -m` | <https://docs.python.org/3/library/__main__.html#main-py-in-python-packages> |
| `dataclasses.dataclass` | <https://docs.python.org/3/library/dataclasses.html#dataclasses.dataclass> |
| `frozen=True` | <https://docs.python.org/3/library/dataclasses.html#frozen-instances> |
| `typing.Protocol` | <https://docs.python.org/3/library/typing.html#typing.Protocol> |
| `collections.abc.Callable` | <https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable> |
| `types.TracebackType` | <https://docs.python.org/3/library/types.html#types.TracebackType> |
| `__enter__` / `__exit__` | <https://docs.python.org/3/reference/datamodel.html#context-managers> |
| `:=` | <https://docs.python.org/3/reference/expressions.html#assignment-expressions> |
| `lambda` | <https://docs.python.org/3/reference/expressions.html#lambda> |
| `logging.getLogger` | <https://docs.python.org/3/library/logging.html#logging.getLogger> |
| `Logger.debug` | <https://docs.python.org/3/library/logging.html#logging.Logger.debug> |
| `logging.basicConfig` | <https://docs.python.org/3/library/logging.html#logging.basicConfig> |
| argparse `action="store_true"` | <https://docs.python.org/3/library/argparse.html#action> |
| `unittest.mock.Mock` | <https://docs.python.org/3/library/unittest.mock.html#unittest.mock.Mock> |
| test discovery | <https://docs.python.org/3/library/unittest.html#test-discovery> |
| `bytearray` (у тесті пошкодження пакета) | <https://docs.python.org/3/library/stdtypes.html#bytearray> |

## Вправи

1. Напишіть тест для `Pinger`, у якому після першого чужого пакета годинник «перескакує» за дедлайн. Перевірте, що `ping()` повертає `None` і більше не викликає `receive`. (Підказка: `clock=Mock(side_effect=[0.0, 0.0, 1.5])`.)
2. Перепишіть `IcmpSocket` на `SOCK_DGRAM` ([`icmp(7)`](https://man7.org/linux/man-pages/man7/icmp.7.html)) як окремий клас `DgramIcmpSocket`. Які модулі довелося змінити? Чи змінився `pinger.py`?
3. Додайте до `-v` повідомлення в `cli.py`, наприклад розв'язану адресу і identifier. Як змінити `format` у `basicConfig`, щоб показувати час кожного повідомлення?
4. Спробуйте передати в `Pinger` об'єкт без методу `receive`. Що скаже mypy?

## Джерела

- [Refactoring (Martin Fowler)](https://refactoring.com/)
- [PEP 557](https://peps.python.org/pep-0557/) — Data Classes
- [PEP 544](https://peps.python.org/pep-0544/) — Protocols: Structural subtyping
- [PEP 572](https://peps.python.org/pep-0572/) — Assignment Expressions
- [PEP 8](https://peps.python.org/pep-0008/) — стиль коду
- [Logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [unittest.mock — getting started](https://docs.python.org/3/library/unittest.mock-examples.html)
