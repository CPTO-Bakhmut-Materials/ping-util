# Урок 8. ICMP-помилки та опції

[← Урок 7](../07-refactoring/README.md) · [До змісту](../README.md)

## Мета уроку

- Розпізнавати повідомлення про помилки **Destination Unreachable** і **Time Exceeded** ([RFC 792](https://www.rfc-editor.org/rfc/rfc792)) та друкувати їх, як системний ping.
- Додати опції `-t ttl`, `-s size`, `-W timeout`.
- Побачити на практиці, наскільки легше розширювати код після рефакторингу з [уроку 7](../07-refactoring/README.md).

```console
$ ../netlab.sh 'python3 ping.py -c 3 -t 1 10.1.0.99'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
From 10.0.0.2 icmp_seq=1 Time to live exceeded
From 10.0.0.2 icmp_seq=2 Time to live exceeded
From 10.0.0.2 icmp_seq=3 Time to live exceeded

--- 10.1.0.99 ping statistics ---
3 packets transmitted, 0 received, +3 errors, 100% packet loss, time 2001ms
```

Це **дослівно** той самий вивід, що й у системного `ping -c 3 -t 1 10.1.0.99` (див. [Порівняння](#порівняння-з-системним-ping)).

---

## Теорія

### Повідомлення про помилки ICMP

Echo — лише два з багатьох типів ICMP. Здебільшого ICMP використовують, щоб
**повідомити відправника про проблему** з його пакетом ([RFC 792](https://www.rfc-editor.org/rfc/rfc792), Introduction).
Для ping важливі два типи:

| Type | Назва | Хто надсилає | Коли |
|---|---|---|---|
| 3 | Destination Unreachable | маршрутизатор або хост | пакет неможливо доставити: немає маршруту, хост не відповідає на ARP, фільтр … |
| 11 | Time Exceeded | маршрутизатор | TTL пакета зменшився до 0 ([RFC 791, Time to Live](https://www.rfc-editor.org/rfc/rfc791#section-3.1)) |

Формат обох однаковий ([RFC 792](https://www.rfc-editor.org/rfc/rfc792), с. 4 і 6):

```
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |     Type      |     Code      |          Checksum             |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                             unused                            |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |      Internet Header + 64 bits of Original Data Datagram      |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Головне — останнє поле: повідомлення **цитує** заголовок IP пакета, що спричинив помилку,
і перші 64 біти (8 байтів) його даних. У нашому випадку ці 8 байтів — увесь заголовок
нашого Echo Request, разом з **identifier і sequence**. Так ми дізнаємося, на який
саме запит прийшла помилка.

Ось що отримує raw-сокет, якщо маршрутизатор `10.0.0.2` повідомляє про TTL exceeded:

```
┌──────────── IP header ────────────┬───────────────────── ICMP Time Exceeded ───────────────────────┐
│ src=10.0.0.2  dst=10.0.0.1        │ type=11 code=0 checksum  unused │ ЦИТАТА:                      │
│ protocol=1                        │                                 │ ┌─ IP header нашого запиту ─┐│
│                                   │                                 │ │ src=10.0.0.1 dst=10.1.0.99││
│                                   │                                 │ │ protocol=1 ttl=1          ││
│                                   │                                 │ ├─ перші 8 байтів даних ────┤│
│                                   │                                 │ │ type=8 code=0 checksum    ││
│                                   │                                 │ │ id=<наш PID> seq=1        ││
│                                   │                                 │ └───────────────────────────┘│
└───────────────────────────────────┴─────────────────────────────────┴──────────────────────────────┘
          ▲ parse_ipv4_header           ▲ parse_icmp_header              ▲ parse_quoted_header (новий)
```

У цитаті `ttl=1`, а не 0: маршрутизатор цитує заголовок таким, яким отримав пакет,
ще до зменшення TTL.

> Сучасні маршрутизатори часто цитують більше за 8 байтів: RFC 1812 радить
> «стільки, скільки вміститься в 576 байтів»
> ([RFC 1812, розд. 4.3.2.3](https://www.rfc-editor.org/rfc/rfc1812#section-4.3.2.3)).
> Нам достатньо перших 8.

### Коди помилок

Поле **Code** уточнює причину. Тексти взято з функції `pr_icmph()` у
[`ping/ping.c`](https://github.com/iputils/iputils/blob/master/ping/ping.c) з iputils,
щоб вивід збігався з системним ping. Повний реєстр — [IANA ICMP Parameters](https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml).

**Type 3, Destination Unreachable:**

| Code | Текст | Джерело |
|---|---|---|
| 0 | Destination Net Unreachable | [RFC 792](https://www.rfc-editor.org/rfc/rfc792) |
| 1 | Destination Host Unreachable | RFC 792 |
| 2 | Destination Protocol Unreachable | RFC 792 |
| 3 | Destination Port Unreachable | RFC 792 |
| 4 | Frag needed and DF set (mtu = N) | RFC 792; MTU — [RFC 1191, розд. 4](https://www.rfc-editor.org/rfc/rfc1191#section-4) |
| 5 | Source Route Failed | RFC 792 |
| 6–12 | Destination Net Unknown … Host Unreachable for Type of Service | [RFC 1122, розд. 3.2.2.1](https://www.rfc-editor.org/rfc/rfc1122#section-3.2.2.1) |
| 13 | Packet filtered | [RFC 1812, розд. 5.2.7.1](https://www.rfc-editor.org/rfc/rfc1812#section-5.2.7.1) (Communication Administratively Prohibited) |
| 14–15 | Precedence Violation, Precedence Cutoff | RFC 1812, розд. 5.2.7.1 |

**Type 11, Time Exceeded:**

| Code | Текст | Джерело |
|---|---|---|
| 0 | Time to live exceeded | [RFC 792](https://www.rfc-editor.org/rfc/rfc792) |
| 1 | Frag reassembly time exceeded | RFC 792 |

Для коду 4 поле «unused» не порожнє: його молодші 16 біт містять MTU наступної ділянки
маршруту ([RFC 1191](https://www.rfc-editor.org/rfc/rfc1191#section-4)). У нашому
`IcmpHeader` ці біти потрапляють у поле `sequence`.

### Опції

| Опція | Що робить | Як реалізовано | Межі |
|---|---|---|---|
| `-t TTL` | TTL вихідних пакетів | [`setsockopt(IPPROTO_IP, IP_TTL, ttl)`](https://docs.python.org/3/library/socket.html#socket.socket.setsockopt), опція `IP_TTL` з [`ip(7)`](https://man7.org/linux/man-pages/man7/ip.7.html) | 1…255: поле має 8 біт, а TTL 0 означає «знищити» ([RFC 791](https://www.rfc-editor.org/rfc/rfc791#section-3.1)) |
| `-s SIZE` | розмір даних у пакеті | `build_payload(args.size)` | 0…65507 = 65535 − 20 (IP) − 8 (ICMP) |
| `-W TIMEOUT` | скільки чекати на відповідь | `Pinger(timeout=args.timeout)` | > 0 |

Опис цих опцій у системному ping — [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html).

**`-t` і traceroute.** Якщо відправити пакет з TTL = 1, його «вб'є» перший маршрутизатор
і поверне Time Exceeded зі своєю адресою. З TTL = 2 це зробить другий маршрутизатор,
і так далі. Саме так працює [`traceroute`](https://linux.die.net/man/8/traceroute)
(див. вправи).

---

## Наскільки легше після рефакторингу

Ось усі зміни уроку 8 відносно уроку 7 (`git diff --stat`):

```
 pyping/cli.py           | 52 +++++++++++++--
 pyping/packet.py        | 75 ++++++++++++++++++++-
 pyping/pinger.py        | 76 +++++++++++++++++-----
 pyping/socket_io.py     |  4 ++
 pyping/stats.py         |  7 +-
 tests/helpers.py        | 14 ++++
 tests/test_cli.py       | 38 +++++++++--
 tests/test_packet.py    | 37 ++++++++++-
 tests/test_pinger.py    | 42 ++++++++++--
 tests/test_stats.py     |  9 +++
```

Кожна зміна потрапила туди, де їй природно бути:

| Що додаємо | Куди | Чому саме туди |
|---|---|---|
| коди й тексти помилок, розбір цитати | `packet.py` | це формат байтів (RFC 792) |
| `set_ttl()` | `socket_io.py` | це системний виклик сокета, **4 рядки** |
| зіставлення помилки з нашим запитом | `pinger.py` | це логіка «чи це відповідь на мій запит» |
| лічильник `errors` | `stats.py` | це статистика, **7 рядків** |
| `-t`, `-s`, `-W`, рядок `From ...` | `cli.py` | це інтерфейс користувача |

У версії з уроку 6 ті самі зміни довелося б вносити в один файл на 337 рядків,
переважно у 64-рядковий `main()`. Перевірити обробку помилок можна було б лише вручну,
у справжній мережі з маршрутизатором.

### mypy підказує, що ще треба змінити

Після того, як `Pinger.ping()` почав повертати `EchoReply | IcmpError | None`,
mypy знайшов місце, яке про це «не знає»:

```console
$ ../.venv/bin/mypy --strict .
tests/test_pinger.py:69: error: Item "IcmpError" of "EchoReply | IcmpError" has no attribute "rtt_ms"  [union-attr]
```

Тест звертався до `reply.rtt_ms`, а в `IcmpError` такого поля немає. Виправлення:
`assert isinstance(reply, EchoReply)`. Без анотацій типів ми б дізналися про це
лише тоді, коли тест упав би з `AttributeError`, а в програмі — можливо, ніколи.

---

## Практика

### `packet.py`: коди, цитата, тексти

Нові константи й таблиці:

```python
ICMP_DEST_UNREACHABLE = 3
ICMP_TIME_EXCEEDED = 11
ICMP_FRAG_NEEDED = 4

DEST_UNREACHABLE_MESSAGES = {
    0: "Destination Net Unreachable",
    1: "Destination Host Unreachable",
    ...
}
TIME_EXCEEDED_MESSAGES = {
    0: "Time to live exceeded",
    1: "Frag reassembly time exceeded",
}
```

`IcmpPacket` отримав поле `body` — усе, що йде після 8 байтів заголовка ICMP. Для
повідомлень про помилки там лежить цитата:

```python
@dataclass(frozen=True)
class IcmpPacket:
    ip: IPv4Header
    icmp: IcmpHeader
    size: int
    body: bytes  # усе, що йде після 8 байтів заголовка ICMP
```

Розбір цитати повторно використовує вже наявні функції:

```python
def parse_quoted_header(body: bytes) -> IcmpHeader | None:
    if len(body) < IP_HEADER_SIZE:
        return None
    quoted_ip = parse_ipv4_header(body)
    quoted = body[quoted_ip.header_length :]
    if quoted_ip.protocol != socket.IPPROTO_ICMP or len(quoted) < ICMP_HEADER_SIZE:
        return None
    return parse_icmp_header(quoted)
```

Цитований IP-заголовок теж може мати опції, тому знову використовуємо `header_length`
(IHL), а не фіксовані 20 байтів. Перевірка `protocol` відкидає помилки про чужі
TCP- чи UDP-пакети: їхні перші 8 байтів мають зовсім інший формат.

```python
def describe_error(header: IcmpHeader) -> str | None:
    if header.type == ICMP_DEST_UNREACHABLE:
        if header.code == ICMP_FRAG_NEEDED:
            return f"Frag needed and DF set (mtu = {header.sequence})"
        return DEST_UNREACHABLE_MESSAGES.get(
            header.code, f"Dest Unreachable, Bad Code: {header.code}"
        )
    if header.type == ICMP_TIME_EXCEEDED:
        return TIME_EXCEEDED_MESSAGES.get(header.code, f"Time exceeded, Bad Code: {header.code}")
    return None
```

[`dict.get(key, default)`](https://docs.python.org/3/library/stdtypes.html#dict.get)
повертає `default`, якщо ключа немає. Так невідомий код не спричинить `KeyError`.

### `pinger.py`: новий тип результату

```python
@dataclass(frozen=True)
class IcmpError:
    source: str
    sequence: int
    message: str
```

`ping()` тепер повертає `EchoReply | IcmpError | None`:

```python
            if self._is_our_reply(parsed, sequence):
                return EchoReply(...)

            error = self._our_error(parsed, sequence)
            if error is not None:
                return error
```

```python
    def _our_error(self, packet: IcmpPacket, sequence: int) -> IcmpError | None:
        message = describe_error(packet.icmp)
        quoted = parse_quoted_header(packet.body) if message is not None else None
        if (
            message is not None
            and quoted is not None
            and quoted.type == ICMP_ECHO_REQUEST
            and quoted.identifier == self.identifier
            and quoted.sequence == sequence
        ):
            return IcmpError(source=packet.ip.source, sequence=sequence, message=message)
        ...
        return None
```

Помилку приймаємо, лише якщо вона цитує **наш** Echo Request з **поточним** sequence.
Це та сама логіка, що й для Echo Reply в уроці 4, лише identifier і sequence
беруться з цитати.

### `socket_io.py`: TTL

```python
    def set_ttl(self, ttl: int) -> None:
        """Встановлює TTL вихідних пакетів (поле Time to Live, RFC 791)."""
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
```

[`socket.setsockopt(level, option, value)`](https://docs.python.org/3/library/socket.html#socket.socket.setsockopt)
змінює параметр сокета ([`setsockopt(2)`](https://man7.org/linux/man-pages/man2/setsockopt.2.html)).
`IPPROTO_IP` означає параметр рівня IP, `IP_TTL` — значення поля TTL для всіх пакетів
цього сокета ([`ip(7)`](https://man7.org/linux/man-pages/man7/ip.7.html)).

### `stats.py`: лічильник помилок

```python
    errors: int = 0

    def add_error(self) -> None:
        self.errors += 1

    ...
        errors = f"+{self.errors} errors, " if self.errors else ""
```

Формат `+N errors` взято з iputils (функція `finish()` у [`ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c)).
Помилка не вважається отриманою відповіддю, тому `packet loss` лишається 100%.

### `cli.py`: опції та вивід

Для `-t` і `-s` потрібна перевірка діапазону. Замість двох майже однакових функцій
пишемо **фабрику**: функцію, яка створює й повертає іншу функцію
([замикання](https://docs.python.org/3/reference/executionmodel.html#resolution-of-names)):

```python
def int_in_range(low: int, high: int) -> Callable[[str], int]:
    """Створює тип аргументу для argparse: ціле число від low до high включно."""

    def parse(text: str) -> int:
        value = int(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"out of range {low}..{high}: {text!r}")
        return value

    return parse
```

```python
    parser.add_argument(
        "-s", dest="size", type=int_in_range(0, MAX_PAYLOAD_SIZE), default=DEFAULT_PAYLOAD_SIZE, ...
    )
    parser.add_argument(
        "-t", dest="ttl", type=int_in_range(MIN_TTL, MAX_TTL), default=None, ...
    )
    parser.add_argument(
        "-W", dest="timeout", type=positive_float, default=DEFAULT_TIMEOUT, ...
    )
```

`low <= value <= high` — [ланцюжок порівнянь](https://docs.python.org/3/reference/expressions.html#comparisons).

Вивід нового типу результату:

```python
def format_error(error: IcmpError) -> str:
    return f"From {error.source} icmp_seq={error.sequence} {error.message}"
...
                if reply is None:
                    print(f"no answer yet for icmp_seq={sequence}")
                elif isinstance(reply, IcmpError):
                    print(format_error(reply))
                    stats.add_error()
                else:
                    print(format_reply(reply))
                    stats.add_reply(reply.rtt_ms)
```

У гілці `else` mypy вже знає, що `reply` має тип `EchoReply`: `None` і `IcmpError`
відсіяно вище ([type narrowing](https://mypy.readthedocs.io/en/stable/type_narrowing.html)).

---

## Тестова мережа: netlab.sh

Щоб побачити Time Exceeded чи Destination Unreachable, потрібен маршрутизатор, який
їх надішле. У справжній мережі результат залежить від провайдера, і багато
маршрутизаторів ICMP взагалі фільтрують. Тому курс має скрипт [`netlab.sh`](../netlab.sh),
який будує віртуальну мережу **без root**:

```
  [клієнт]                          [маршрутизатор]
  a0: 10.0.0.1/24  ═══ veth ═══  b0: 10.0.0.2/24
  default via 10.0.0.2           d0: 10.1.0.1/24 (dummy) ──▶ 10.1.0.0/24, пакети зникають
                                 ip_forward = 1
```

| Адреса | Що відбувається |
|---|---|
| `10.0.0.2`, `10.1.0.1` | маршрутизатор відповідає на ping |
| `10.1.0.99` | маршрутизатор пересилає пакет у dummy-інтерфейс, де той зникає → тайм-аут |
| `10.1.0.99` з `-t 1` | маршрутизатор зменшує TTL до 0 → **Time to live exceeded** |
| `10.9.9.9` | у маршрутизатора немає маршруту → **Destination Net Unreachable** |
| `10.0.0.77` | у мережі клієнта нікого немає, ARP без відповіді ([RFC 826](https://www.rfc-editor.org/rfc/rfc826)) → клієнт через ~3 с сам генерує **Destination Host Unreachable** |

Як це влаштовано:

| Інструмент | Роль | Документація |
|---|---|---|
| user namespace | всередині ми root, але лише для власних ресурсів. Тому raw-сокети працюють без `sudo`. | [`user_namespaces(7)`](https://man7.org/linux/man-pages/man7/user_namespaces.7.html) |
| network namespace | окремий мережевий стек: свої інтерфейси, маршрути, sysctl | [`network_namespaces(7)`](https://man7.org/linux/man-pages/man7/network_namespaces.7.html) |
| `unshare` | створює нові простори імен і запускає в них команду | [`unshare(1)`](https://man7.org/linux/man-pages/man1/unshare.1.html) |
| `nsenter` | виконує команду в просторі імен іншого процесу (маршрутизатора) | [`nsenter(1)`](https://man7.org/linux/man-pages/man1/nsenter.1.html) |
| `veth` | пара віртуальних інтерфейсів, з'єднаних «кабелем» | [`veth(4)`](https://man7.org/linux/man-pages/man4/veth.4.html) |
| `dummy` | інтерфейс, який мовчки відкидає все | [`ip-link(8)`](https://man7.org/linux/man-pages/man8/ip-link.8.html) |
| `ip_forward` | дозволяє пересилати пакети між інтерфейсами, тобто бути маршрутизатором | [ip-sysctl](https://docs.kernel.org/networking/ip-sysctl.html) |

```console
$ ./netlab.sh 'python3 08-errors-and-options/ping.py -c 1 10.0.0.2'   # одна команда
$ ./netlab.sh                                                            # інтерактивна оболонка
```

---

## Запуск

### Порівняння з системним ping

**Time to live exceeded:**

```console
$ ../netlab.sh 'python3 ping.py -c 3 -t 1 10.1.0.99; echo; ping -c 3 -t 1 10.1.0.99'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
From 10.0.0.2 icmp_seq=1 Time to live exceeded
From 10.0.0.2 icmp_seq=2 Time to live exceeded
From 10.0.0.2 icmp_seq=3 Time to live exceeded

--- 10.1.0.99 ping statistics ---
3 packets transmitted, 0 received, +3 errors, 100% packet loss, time 2001ms

PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
From 10.0.0.2 icmp_seq=1 Time to live exceeded
From 10.0.0.2 icmp_seq=2 Time to live exceeded
From 10.0.0.2 icmp_seq=3 Time to live exceeded

--- 10.1.0.99 ping statistics ---
3 packets transmitted, 0 received, +3 errors, 100% packet loss, time 2027ms
```

**Destination Net Unreachable** (від маршрутизатора) і **Host Unreachable** (від власного хоста):

```console
$ ../netlab.sh 'python3 ping.py -c 2 10.9.9.9'
PING 10.9.9.9 (10.9.9.9) 56(84) bytes of data.
From 10.0.0.2 icmp_seq=1 Destination Net Unreachable
From 10.0.0.2 icmp_seq=2 Destination Net Unreachable

--- 10.9.9.9 ping statistics ---
2 packets transmitted, 0 received, +2 errors, 100% packet loss, time 1001ms

$ ../netlab.sh 'python3 ping.py -c 1 -W 4 10.0.0.77'
PING 10.0.0.77 (10.0.0.77) 56(84) bytes of data.
From 10.0.0.1 icmp_seq=1 Destination Host Unreachable

--- 10.0.0.77 ping statistics ---
1 packets transmitted, 0 received, +1 errors, 100% packet loss, time 3094ms
```

У другому прикладі `-W 4` потрібен тому, що ядро повідомляє про недоступність хоста
лише після кількох невдалих ARP-запитів, приблизно за 3 с.

**`-t` достатній:** з TTL = 2 пакет проходить маршрутизатор:

```console
$ ../netlab.sh 'python3 ping.py -c 1 -t 2 10.1.0.1 | sed -n 2p'
64 bytes from 10.1.0.1: icmp_seq=1 ttl=64 time=0.117 ms
```

**`-s`:**

```console
$ ../netlab.sh 'python3 ping.py -c 1 -s 1000 10.0.0.2 | head -2'
PING 10.0.0.2 (10.0.0.2) 1000(1028) bytes of data.
1008 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.107 ms

$ ../netlab.sh 'python3 ping.py -c 1 -s 0 10.0.0.2 | head -2'
PING 10.0.0.2 (10.0.0.2) 0(28) bytes of data.
8 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.114 ms
```

**`-W`:**

```console
$ ../netlab.sh 'python3 ping.py -c 1 -W 0.3 10.1.0.99 | tail -1'
1 packets transmitted, 0 received, 100% packet loss, time 301ms
```

**Перевірка меж:**

```console
$ python3 ping.py -t 0 example.com
usage: ping [-h] [-c COUNT] [-i INTERVAL] [-s SIZE] [-t TTL] [-W TIMEOUT] [-v]
            host
ping: error: argument -t: out of range 1..255: '0'

$ python3 ping.py -s 70000 example.com
...
ping: error: argument -s: out of range 0..65507: '70000'
```

**Довідка:**

```console
$ python3 ping.py -h
usage: ping [-h] [-c COUNT] [-i INTERVAL] [-s SIZE] [-t TTL] [-W TIMEOUT] [-v]
            host

Надсилає ICMP ECHO_REQUEST до мережевого вузла.

positional arguments:
  host         ім'я або IPv4-адреса вузла

options:
  -h, --help   show this help message and exit
  -c COUNT     зупинитися після COUNT запитів (за замовчуванням — до Ctrl+C)
  -i INTERVAL  пауза між запитами в секундах (за замовчуванням 1.0)
  -s SIZE      розмір даних у пакеті в байтах (за замовчуванням 56)
  -t TTL       TTL вихідних пакетів (за замовчуванням — системне значення)
  -W TIMEOUT   скільки секунд чекати на відповідь (за замовчуванням 1.0)
  -v           друкувати налагоджувальні повідомлення в stderr
```

## Тести

Нові сценарії перевіряються з `Mock`, як в уроці 7, без маршрутизатора й без мережі.
Допоміжна функція `make_icmp_error()` у [`tests/helpers.py`](tests/helpers.py) збирає
повідомлення про помилку, що цитує заданий пакет:

```python
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
        ...
```

Також додано тести `parse_quoted_header()`, `describe_error()` (зокрема MTU і
невідомий код), `+N errors` у статистиці, `int_in_range()` і нових опцій.

```console
$ python3 -m unittest
Ran 35 tests in 0.005s
OK
$ ../.venv/bin/mypy --strict .
Success: no issues found in 14 source files
```

## Повний код

- [`ping.py`](ping.py)
- [`pyping/packet.py`](pyping/packet.py), [`pyping/socket_io.py`](pyping/socket_io.py), [`pyping/pinger.py`](pyping/pinger.py), [`pyping/stats.py`](pyping/stats.py), [`pyping/cli.py`](pyping/cli.py)
- [`tests/`](tests/)
- [`../netlab.sh`](../netlab.sh)

## Використані функції та модулі

| Що | Документація |
|---|---|
| `socket.setsockopt` | <https://docs.python.org/3/library/socket.html#socket.socket.setsockopt> |
| `socket.IP_TTL`, `socket.IPPROTO_IP` | <https://docs.python.org/3/library/socket.html#constants> |
| `dict.get` | <https://docs.python.org/3/library/stdtypes.html#dict.get> |
| `isinstance` | <https://docs.python.org/3/library/functions.html#isinstance> |
| вкладені функції та замикання | <https://docs.python.org/3/reference/executionmodel.html#resolution-of-names> |
| ланцюжок порівнянь | <https://docs.python.org/3/reference/expressions.html#comparisons> |
| `collections.abc.Callable` | <https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable> |
| mypy: type narrowing | <https://mypy.readthedocs.io/en/stable/type_narrowing.html> |

## Вправи

1. **traceroute.** Напишіть `pyping/traceroute.py`: для TTL = 1, 2, 3 … відправляйте запит з `set_ttl(ttl)` і друкуйте адресу, з якої прийшов Time Exceeded, доки не прийде Echo Reply. Які модулі довелося змінити? (Правильна відповідь: жоден, лише новий модуль і, можливо, `cli.py`.) Перевірте в тестовій мережі: `10.1.0.1` має бути на відстані 1 кроку.
2. Перевірте, що `ping -s 2000 10.0.0.2` працює, хоча MTU інтерфейсу 1500. Що робить ядро з таким пакетом? (Підказка: фрагментація, [RFC 791](https://www.rfc-editor.org/rfc/rfc791#section-2.3).)
3. Додайте опцію `-M do` (заборонити фрагментацію, [`ip(7)`](https://man7.org/linux/man-pages/man7/ip.7.html), `IP_MTU_DISCOVER`) і отримайте `Frag needed and DF set (mtu = …)`. Для цього в `netlab.sh` треба зменшити MTU між маршрутизатором і другою мережею.
4. Додайте підтримку IPv6: ICMPv6 ([RFC 4443](https://www.rfc-editor.org/rfc/rfc4443)), `AF_INET6`. Чим відрізняються типи повідомлень? Хто рахує контрольну суму ([RFC 4443, розд. 2.3](https://www.rfc-editor.org/rfc/rfc4443#section-2.3))?
5. Пінгуйте кілька вузлів одночасно за допомогою [`selectors`](https://docs.python.org/3/library/selectors.html) або [`asyncio`](https://docs.python.org/3/library/asyncio.html). Які модулі можна використати без змін?

## Джерела

- [RFC 792](https://www.rfc-editor.org/rfc/rfc792) — Destination Unreachable, Time Exceeded
- [RFC 1122, розд. 3.2.2](https://www.rfc-editor.org/rfc/rfc1122#section-3.2.2) — вимоги до ICMP на хостах, коди 6–12
- [RFC 1812, розд. 4.3.2.3, 5.2.7.1](https://www.rfc-editor.org/rfc/rfc1812) — вимоги до маршрутизаторів, коди 13–15, розмір цитати
- [RFC 1191](https://www.rfc-editor.org/rfc/rfc1191) — Path MTU Discovery
- [RFC 826](https://www.rfc-editor.org/rfc/rfc826) — ARP
- [IANA ICMP Parameters](https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml)
- [iputils `ping/ping.c`](https://github.com/iputils/iputils/blob/master/ping/ping.c) — `pr_icmph()`: тексти помилок
- [`ip(7)`](https://man7.org/linux/man-pages/man7/ip.7.html) — `IP_TTL`
- [`user_namespaces(7)`](https://man7.org/linux/man-pages/man7/user_namespaces.7.html), [`network_namespaces(7)`](https://man7.org/linux/man-pages/man7/network_namespaces.7.html) — основа `netlab.sh`
