# Урок 3. Перший справжній ping

[← Урок 2](../02-icmp-packet/README.md) · [До змісту](../README.md) · [Урок 4 →](../04-reliability/README.md)

## Мета уроку

- Відкрити raw-сокет і відправити в мережу пакет, зібраний в уроці 2.
- Отримати відповідь і розібрати заголовок IPv4 ([RFC 791](https://www.rfc-editor.org/rfc/rfc791)), щоб дістати TTL та адресу відправника.
- Виміряти час обміну (RTT) і надрукувати рядок відповіді, як системний ping.

```console
$ sudo python3 ping.py 10.0.0.2
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.068 ms
```

## Що змінилося порівняно з уроком 2

| Було | Стало |
|---|---|
| пакет лише друкувався | пакет відправляється через raw-сокет |
| — | константи `ICMP_ECHO_REPLY`, `IP_HEADER_FORMAT`, `RECV_BUFFER_SIZE` |
| — | функції `parse_ip_header()`, `parse_icmp_header()`, `format_rtt()` |
| `describe_packet()`, `hexdump()` | прибрано: це був налагоджувальний вивід уроку 2 |
| `IP_HEADER_SIZE = 20` | обчислюється з формату: `struct.calcsize(IP_HEADER_FORMAT)` |
| `main()` друкує пакет | `main()` відправляє запит, чекає відповідь і друкує результат |

---

## Теорія

### Сокети

**Сокет** — це інтерфейс операційної системи для обміну даними через мережу
([`socket(2)`](https://man7.org/linux/man-pages/man2/socket.2.html),
[`socket(7)`](https://man7.org/linux/man-pages/man7/socket.7.html)). У Python його
створює клас [`socket.socket(family, type, proto)`](https://docs.python.org/3/library/socket.html#socket.socket):

| Аргумент | Значення | Що означає |
|---|---|---|
| `family` | [`socket.AF_INET`](https://docs.python.org/3/library/socket.html#socket.AF_INET) | адреси IPv4 ([`ip(7)`](https://man7.org/linux/man-pages/man7/ip.7.html)) |
| `type` | [`socket.SOCK_RAW`](https://docs.python.org/3/library/socket.html#socket.SOCK_STREAM) | «сирий» сокет: ми самі формуємо повідомлення протоколу ([`raw(7)`](https://man7.org/linux/man-pages/man7/raw.7.html)) |
| `proto` | [`socket.IPPROTO_ICMP`](https://docs.python.org/3/library/socket.html#socket.IPPROTO_RAW) | протокол ICMP. Його номер у полі Protocol заголовка IPv4 дорівнює 1 ([IANA Protocol Numbers](https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml)). |

Звичні програми використовують `SOCK_STREAM` (TCP) або `SOCK_DGRAM` (UDP). Тоді
заголовки протоколу формує ядро, а програма передає лише дані. У ICMP немає ні портів,
ні з'єднань, тому ping працює рівнем нижче: ми самі збираємо ICMP-повідомлення
(урок 2), а ядро додає до нього лише заголовок IPv4.

### Чому потрібен root

За [`raw(7)`](https://man7.org/linux/man-pages/man7/raw.7.html) raw-сокет може відкрити
лише процес з ефективним UID 0 (root) або з правом `CAP_NET_RAW`
([`capabilities(7)`](https://man7.org/linux/man-pages/man7/capabilities.7.html)).
Raw-сокет дає змогу відправити довільний пакет і бачити чужий ICMP-трафік, тому
звичайним користувачам він недоступний.

Як запустити програму:

| Спосіб | Команда | Коментар |
|---|---|---|
| `sudo` | `sudo python3 ping.py example.com` | найпростіший спосіб, працює зі справжньою мережею |
| тестова мережа курсу | `../netlab.sh 'python3 ping.py 10.0.0.2'` | **root не потрібен**. Скрипт створює ізольовану віртуальну мережу ([`netlab.sh`](../netlab.sh), докладніше в [уроці 8](../08-errors-and-options/README.md#тестова-мережа-netlabsh)). |

> Системний `ping` працює без `sudo`, бо використовує ICMP-сокет типу `SOCK_DGRAM`
> ([`icmp(7)`](https://man7.org/linux/man-pages/man7/icmp.7.html)) або має право
> `CAP_NET_RAW`, встановлене на файл ([`setcap(8)`](https://man7.org/linux/man-pages/man8/setcap.8.html)).
> Перевірте: `getcap $(which ping)`.

### Що отримує raw-сокет

Ось головне з [`raw(7)`](https://man7.org/linux/man-pages/man7/raw.7.html):

1. **Під час відправки** ядро саме додає заголовок IPv4. Ми передаємо лише ICMP-повідомлення.
2. **Під час отримання** ми отримуємо **весь IP-пакет разом із заголовком IPv4**.
3. Raw-сокет з `IPPROTO_ICMP` отримує **копію кожного** ICMP-пакета, що надходить на комп'ютер. Серед них є відповіді іншим програмам і навіть наш власний запит, якщо пінгуємо `127.0.0.1`: на loopback-інтерфейсі вихідний пакет одразу стає вхідним.

Тому відповідь треба спочатку «розпакувати»:

```
recvfrom() повертає:
┌──────────────────────┬──────────────────────────────────────┐
│ IPv4 header (20+ B)  │ ICMP message (8 B header + payload)  │
└──────────────────────┴──────────────────────────────────────┘
 ▲ TTL, Source Address   ▲ Type, Code, Identifier, Sequence
```

### Заголовок IPv4

Формат з [RFC 791, розд. 3.1](https://www.rfc-editor.org/rfc/rfc791#section-3.1):

```
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |Version|  IHL  |Type of Service|          Total Length         |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |         Identification        |Flags|      Fragment Offset    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |  Time to Live |    Protocol   |         Header Checksum       |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                       Source Address                          |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    Destination Address                        |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    Options                    |    Padding    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

| Поле | Розмір | Формат `struct` | Використовуємо? |
|---|---|---|---|
| Version + IHL | 4 + 4 біти | `B` (1 байт на обидва поля) | **так**: IHL — довжина заголовка |
| Type of Service | 1 байт | `B` | ні |
| Total Length | 2 байти | `H` | ні |
| Identification | 2 байти | `H` | ні |
| Flags + Fragment Offset | 3 + 13 біт | `H` | ні |
| Time to Live | 1 байт | `B` | **так**: виводимо як `ttl=` |
| Protocol | 1 байт | `B` | ні (буде в уроці 8) |
| Header Checksum | 2 байти | `H` | ні: заголовок IP перевіряє ядро |
| Source Address | 4 байти | `4s` (4 сирі байти) | **так**: адреса відповідача |
| Destination Address | 4 байти | `4s` | ні |

Звідси формат `"!BBHHHBBH4s4s"`. Символ `4s` означає «рядок байтів довжиною 4»
([Format Characters](https://docs.python.org/3/library/struct.html#format-characters)).

#### IHL: довжина заголовка

Заголовок IPv4 може містити **опції**, тому його довжина змінна. Поле **IHL**
(Internet Header Length) зберігає її в 32-бітних словах. Без опцій IHL = 5, тобто 5 × 4 = 20 байтів.
IHL займає молодші 4 біти першого байта, а Version — старші:

```
перший байт 0x45 = 0100 0101
                   ──── ────
                   Ver=4 IHL=5   →  (0x45 & 0x0F) * 4 = 20 байтів
```

Тому ICMP-повідомлення починається не з 20-го байта «завжди», а з `IHL * 4`.

#### Адреса: 4 байти → рядок

[`socket.inet_ntoa(b)`](https://docs.python.org/3/library/socket.html#socket.inet_ntoa)
перетворює 4 байти адреси на звичний запис («dotted-quad»): `b"\x08\x08\x08\x08"` → `"8.8.8.8"`.
Зворотну операцію виконує [`socket.inet_aton`](https://docs.python.org/3/library/socket.html#socket.inet_aton).

### Вимірювання часу

RTT — це різниця між моментом отримання відповіді й моментом відправки запиту
([RFC 2681](https://www.rfc-editor.org/rfc/rfc2681)). Для вимірювання проміжків
використовуємо [`time.perf_counter()`](https://docs.python.org/3/library/time.html#time.perf_counter),
а не `time.time()`:

| Функція | Що повертає | Для чого |
|---|---|---|
| `time.time()` | системний час, який можна перевести (NTP, вручну) | дата й час подій |
| `time.perf_counter()` | **монотонний** лічильник найвищої точності | вимірювання проміжків |

Якщо системний годинник переведуть між відправкою і відповіддю, `time.time()` дасть
неправильний або навіть від'ємний RTT. Чому так, пояснено в [PEP 418](https://peps.python.org/pep-0418/).

---

## Практика

### Крок 1. Константи

```python
ICMP_ECHO_REPLY = 0
ICMP_ECHO_REQUEST = 8

IP_HEADER_FORMAT = "!BBHHHBBH4s4s"
IP_HEADER_SIZE = struct.calcsize(IP_HEADER_FORMAT)  # 20 байтів

# Поле Total Length заголовка IPv4 має 16 біт, тому більшого пакета не буває.
RECV_BUFFER_SIZE = 65535
```

`RECV_BUFFER_SIZE` — розмір буфера для `recvfrom`. Якщо пакет більший за буфер,
решту байтів буде втрачено ([`recv(2)`](https://man7.org/linux/man-pages/man2/recv.2.html)).
65535 — максимальний розмір IPv4-пакета, тож у такий буфер вміститься будь-який.

### Крок 2. Розбір заголовка IPv4

```python
def parse_ip_header(data: bytes) -> tuple[int, int, str]:
    """Розбирає заголовок IPv4 на початку data.

    Повертає (довжину заголовка в байтах, TTL, адресу відправника).
    """
    (
        version_ihl, _tos, _total_length, _identification, _flags_offset,
        ttl, _protocol, _header_checksum, source, _destination,
    ) = struct.unpack(IP_HEADER_FORMAT, data[:IP_HEADER_SIZE])
    header_length = (version_ihl & 0x0F) * 4
    return header_length, ttl, socket.inet_ntoa(source)
```

- [`struct.unpack`](https://docs.python.org/3/library/struct.html#struct.unpack) повертає кортеж із 10 значень. Ми [розпаковуємо його](https://docs.python.org/3/tutorial/datastructures.html#tuples-and-sequences) в змінні.
- Префікс `_` в імені (`_tos`) — домовленість «значення не використовується» ([PEP 8](https://peps.python.org/pep-0008/#descriptive-naming-styles)). Однак усі поля названо, тож видно, що де лежить.
- Анотація `tuple[int, int, str]` — кортеж із трьох елементів саме цих типів ([`tuple` в анотаціях](https://docs.python.org/3/library/typing.html#annotating-tuples)).

### Крок 3. Розбір заголовка ICMP

```python
def parse_icmp_header(data: bytes) -> tuple[int, int, int, int]:
    """Повертає (type, code, identifier, sequence) ICMP-повідомлення."""
    type_, code, _checksum, identifier, sequence = struct.unpack(
        ICMP_HEADER_FORMAT, data[:ICMP_HEADER_SIZE]
    )
    return type_, code, identifier, sequence
```

Це та сама логіка, що й `describe_packet()` з уроку 2, але функція повертає значення,
а не рядок. Echo Reply має той самий формат, що й Echo Request, лише `type = 0`
([RFC 792](https://www.rfc-editor.org/rfc/rfc792), с. 14).

### Крок 4. Форматування RTT

```python
def format_rtt(rtt_ms: float) -> str:
    """Форматує RTT як iputils: приблизно 3 значущі цифри."""
    if rtt_ms >= 99.95:
        return f"{rtt_ms:.0f}"
    if rtt_ms >= 9.995:
        return f"{rtt_ms:.1f}"
    if rtt_ms >= 1:
        return f"{rtt_ms:.2f}"
    return f"{rtt_ms:.3f}"
```

Системний ping друкує `time=0.068 ms`, `time=12.1 ms`, `time=112 ms`: кількість знаків
після коми залежить від величини числа. Правило взято з функції `gather_statistics()` у
[`ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c).
Межі `99.95` і `9.995` потрібні, щоб, наприклад, 99.97 надрукувалося як `100`, а не `100.0`.

### Крок 5. Відправка та отримання

```python
    identifier = os.getpid() & 0xFFFF
    sequence = 1
    packet = build_echo_request(identifier, sequence, build_payload(payload_size))

    with socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP) as sock:
        send_time = time.perf_counter()
        sock.sendto(packet, (address, 0))

        while True:
            data, _ = sock.recvfrom(RECV_BUFFER_SIZE)
            receive_time = time.perf_counter()

            ip_header_length, ttl, source = parse_ip_header(data)
            icmp = data[ip_header_length:]
            type_, code, reply_id, reply_seq = parse_icmp_header(icmp)

            if type_ == ICMP_ECHO_REPLY:
                break

    rtt_ms = (receive_time - send_time) * 1000
    print(
        f"{len(icmp)} bytes from {source}: icmp_seq={reply_seq} ttl={ttl} "
        f"time={format_rtt(rtt_ms)} ms"
    )
```

| Виклик | Що робить | Документація |
|---|---|---|
| `with socket.socket(...) as sock:` | сокет автоматично закривається після виходу з блоку, навіть якщо виникла помилка | [`socket` як context manager](https://docs.python.org/3/library/socket.html#socket.socket), [оператор `with`](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement) |
| `sock.sendto(packet, (address, 0))` | відправляє байти на адресу. Для `AF_INET` адреса — пара `(host, port)`. ICMP не має портів, тому порт `0`. | [`socket.sendto`](https://docs.python.org/3/library/socket.html#socket.socket.sendto), [`sendto(2)`](https://man7.org/linux/man-pages/man2/sendto.2.html) |
| `sock.recvfrom(RECV_BUFFER_SIZE)` | **блокує** програму, доки не прийде пакет. Повертає `(bytes, address)`. | [`socket.recvfrom`](https://docs.python.org/3/library/socket.html#socket.socket.recvfrom), [`recv(2)`](https://man7.org/linux/man-pages/man2/recv.2.html) |
| `time.perf_counter()` | момент часу в секундах (float) | [`time.perf_counter`](https://docs.python.org/3/library/time.html#time.perf_counter) |
| `data[ip_header_length:]` | зріз: усе після IP-заголовка, тобто ICMP-повідомлення | [операції над послідовностями](https://docs.python.org/3/library/stdtypes.html#common-sequence-operations) |

Цикл `while True` потрібен через властивість 3 raw-сокета: першим може прийти не
Echo Reply, а, наприклад, наш власний Echo Request на loopback. Пропускаємо все,
що не має `type == 0`.

`len(icmp)` дає розмір ICMP-повідомлення: 8 + 56 = **64 bytes**, як у системного ping.

---

## Запуск

### У тестовій мережі (без root)

```console
$ ../netlab.sh 'python3 ping.py 10.0.0.2'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.068 ms

$ ../netlab.sh 'python3 ping.py localhost'
PING localhost (127.0.0.1) 56(84) bytes of data.
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.055 ms
```

Порівняйте з системним ping у тій самій мережі:

```console
$ ../netlab.sh 'ping -c 1 127.0.0.1'
PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.036 ms
```

### Зі справжньою мережею

```console
$ sudo python3 ping.py example.com
PING example.com (104.20.23.154) 56(84) bytes of data.
64 bytes from 104.20.23.154: icmp_seq=1 ttl=58 time=12.1 ms
```

(Адреса, TTL і час у вас будуть інші.)

### Без прав root

```console
$ python3 ping.py example.com
PING example.com (172.66.147.243) 56(84) bytes of data.
Traceback (most recent call last):
  File ".../03-first-ping/ping.py", line 171, in <module>
    sys.exit(main())
             ~~~~^^
  File ".../03-first-ping/ping.py", line 144, in main
    with socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP) as sock:
         ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.14/socket.py", line 236, in __init__
    _socket.socket.__init__(self, family, type, proto, fileno)
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
PermissionError: [Errno 1] Operation not permitted
```

Програма падає з traceback. Це перша з проблем, які виправимо в наступному уроці.

## Відомі проблеми (виправимо в уроці 4)

Ця версія працює лише в ідеальних умовах.

**1. Якщо відповіді немає, програма чекає вічно.** `recvfrom` блокує виконання, доки
не прийде пакет. Адреса `10.1.0.99` у тестовій мережі не відповідає ніколи:

```console
$ ../netlab.sh 'python3 ping.py 10.1.0.99'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
                                  ← програма «зависла», допоможе лише Ctrl+C
```

**2. Програма приймає чужі відповіді.** Ми перевіряємо лише `type == 0`. Запустимо
паралельно системний ping до іншого вузла, а нашою програмою пінгуємо «мовчазну» адресу:

```console
$ ../netlab.sh 'ping -q -c 40 -i 0.05 10.0.0.2 >/dev/null & sleep 0.2; python3 ping.py 10.1.0.99'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=8 ttl=64 time=44.5 ms
```

Ми пінгували `10.1.0.99`, а отримали «відповідь» від `10.0.0.2` з `icmp_seq=8`. Це
відповідь системному ping, і програма не помітила підміни.

**3. Контрольна сума відповіді не перевіряється.** Пошкоджений пакет буде прийнято як правильний.

**4. Немає зрозумілих повідомлень про помилки.** Без root користувач бачить traceback.

---

## Тести

До тестів з уроку 2 додано тести нових функцій ([`test_ping.py`](test_ping.py)):

```python
def make_ip_header(ttl: int, source: str, ihl: int = 5) -> bytes:
    """Збирає заголовок IPv4 для тестів (version=4, protocol=1, тобто ICMP)."""
    header = struct.pack(
        IP_HEADER_FORMAT,
        (4 << 4) | ihl, 0, 84, 0, 0, ttl, socket.IPPROTO_ICMP, 0,
        socket.inet_aton(source), socket.inet_aton("10.0.0.1"),
    )
    return header + bytes((ihl - 5) * 4)


class ParseTest(unittest.TestCase):
    def test_ip_header(self) -> None:
        header = make_ip_header(ttl=58, source="8.8.8.8")
        self.assertEqual(parse_ip_header(header), (20, 58, "8.8.8.8"))

    def test_ip_header_with_options(self) -> None:
        header = make_ip_header(ttl=64, source="127.0.0.1", ihl=6)
        self.assertEqual(parse_ip_header(header)[0], 24)
```

Допоміжна функція `make_ip_header` збирає заголовок «вручну». Так ми перевіряємо
розбір, не відправляючи нічого в мережу і без прав root. `(4 << 4) | ihl` складає
перший байт: Version у старших 4 бітах, IHL у молодших.

Відправку й отримання (`main()`) поки що автоматично не тестуємо: для цього потрібні
мережа і root. Як це виправити, побачимо в [уроці 7](../07-refactoring/README.md).

```console
$ python3 -m unittest -v
...
Ran 11 tests in 0.001s

OK
$ ../.venv/bin/mypy --strict .
Success: no issues found in 2 source files
```

## Повний код

- [`ping.py`](ping.py)
- [`test_ping.py`](test_ping.py)

## Використані функції та модулі

| Що | Документація |
|---|---|
| `socket.socket` | <https://docs.python.org/3/library/socket.html#socket.socket> |
| `socket.SOCK_RAW` | <https://docs.python.org/3/library/socket.html#socket.SOCK_STREAM> |
| `socket.IPPROTO_ICMP` | <https://docs.python.org/3/library/socket.html#socket.IPPROTO_RAW> |
| `socket.sendto` | <https://docs.python.org/3/library/socket.html#socket.socket.sendto> |
| `socket.recvfrom` | <https://docs.python.org/3/library/socket.html#socket.socket.recvfrom> |
| `socket.inet_ntoa` | <https://docs.python.org/3/library/socket.html#socket.inet_ntoa> |
| `socket.inet_aton` | <https://docs.python.org/3/library/socket.html#socket.inet_aton> |
| `time.perf_counter` | <https://docs.python.org/3/library/time.html#time.perf_counter> |
| оператор `with` | <https://docs.python.org/3/reference/compound_stmts.html#the-with-statement> |
| `struct`: символ `s` | <https://docs.python.org/3/library/struct.html#format-characters> |
| `tuple` в анотаціях | <https://docs.python.org/3/library/typing.html#annotating-tuples> |
| `PermissionError` | <https://docs.python.org/3/library/exceptions.html#PermissionError> |

Функції попередніх уроків описано в [уроці 1](../01-cli-skeleton/README.md#використані-функції-та-модулі)
та [уроці 2](../02-icmp-packet/README.md#використані-функції-та-модулі).

## Вправи

1. Пропінгуйте `localhost` і `8.8.8.8` (через `sudo`). Порівняйте TTL. Скільки маршрутизаторів між вами і `8.8.8.8`, якщо його початковий TTL дорівнює 128? А якщо 64?
2. Тимчасово приберіть умову `if type_ == ICMP_ECHO_REPLY` і виконайте `ping.py 127.0.0.1` у тестовій мережі. Що ви отримали і чому?
3. Надрукуйте `data.hex(" ")` для отриманого пакета. Знайдіть у ньому Version/IHL, TTL, Protocol, Source Address і початок ICMP-повідомлення.
4. Чому `time=` у нашої програми трохи більший, ніж у системного ping на тому самому вузлі? (Підказка: що відбувається між `perf_counter()` і фактичною відправкою?)
5. Прочитайте розділ про `SOCK_DGRAM` в [`icmp(7)`](https://man7.org/linux/man-pages/man7/icmp.7.html). Що доведеться змінити в програмі, щоб вона працювала без root? (Підказка: ядро саме підставляє identifier і не віддає IP-заголовок.)

## Джерела

- [RFC 791, розд. 3.1](https://www.rfc-editor.org/rfc/rfc791#section-3.1) — заголовок IPv4
- [RFC 792](https://www.rfc-editor.org/rfc/rfc792) — Echo / Echo Reply
- [RFC 2681](https://www.rfc-editor.org/rfc/rfc2681) — Round-trip Delay
- [`raw(7)`](https://man7.org/linux/man-pages/man7/raw.7.html), [`ip(7)`](https://man7.org/linux/man-pages/man7/ip.7.html), [`icmp(7)`](https://man7.org/linux/man-pages/man7/icmp.7.html), [`socket(7)`](https://man7.org/linux/man-pages/man7/socket.7.html)
- [`capabilities(7)`](https://man7.org/linux/man-pages/man7/capabilities.7.html) — `CAP_NET_RAW`
- [IANA Protocol Numbers](https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml) — ICMP = 1
- [PEP 418](https://peps.python.org/pep-0418/) — монотонні годинники в Python
- [iputils `ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c) — форматування `time=`
