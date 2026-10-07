# Урок 4. Надійність

[← Урок 3](../03-first-ping/README.md) · [До змісту](../README.md) · [Урок 5 →](../05-loop/README.md)

## Мета уроку

Виправити чотири проблеми, знайдені в [уроці 3](../03-first-ping/README.md#відомі-проблеми-виправимо-в-уроці-4):

| Проблема | Рішення |
|---|---|
| без відповіді програма чекає вічно | тайм-аут з «дедлайном» |
| приймаються чужі відповіді | перевірка `type`, `identifier` і `sequence` |
| контрольна сума не перевіряється | `checksum(icmp) == 0` ([RFC 1071](https://www.rfc-editor.org/rfc/rfc1071)) |
| traceback замість повідомлення | обробка `PermissionError` і `OSError`, коди завершення 0/1/2 |

```console
$ ../netlab/netlab.sh 'python3 ping.py 10.1.0.99'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
no answer yet for icmp_seq=1

$ python3 ping.py example.com
ping: socket: Operation not permitted
ping: raw-сокет потребує прав root, запустіть через sudo
```

## Що змінилося порівняно з уроком 3

| Було | Стало |
|---|---|
| увесь обмін у `main()` | функції `send_echo_request()` і `receive_reply()` |
| `recvfrom` без обмеження часу | `settimeout()` + дедлайн, константа `DEFAULT_TIMEOUT = 1.0` |
| перевірка лише `type == 0` | перевірка довжини, контрольної суми, `type`, `identifier`, `sequence` |
| traceback без root | повідомлення та код `2` |
| — | код `EXIT_NO_REPLY = 1`, якщо відповіді немає |

---

## Теорія

### Як зіставляти запит і відповідь

У [RFC 792](https://www.rfc-editor.org/rfc/rfc792) (с. 14) про поля Echo сказано:

> The data received in the echo message must be returned in the echo reply message.
> The identifier and sequence number may be used by the echo sender to aid in
> matching the replies with the echo requests.

Тобто відповідач **повертає identifier і sequence без змін**. Наша відповідь — це пакет, де:

| Поле | Значення | Чому |
|---|---|---|
| `type` | `0` (Echo Reply) | відкидаємо запити, помилки та інші ICMP |
| `identifier` | наш `os.getpid() & 0xFFFF` | відкидаємо відповіді іншим програмам ping |
| `sequence` | номер нашого запиту | відкидаємо запізнілі відповіді на попередні запити (знадобиться в уроці 5) |

### Перевірка контрольної суми

В [уроці 2](../02-icmp-packet/README.md#як-отримувач-перевіряє-пакет) ми з'ясували:
сума правильного повідомлення **разом із полем checksum** дає 0. Тому перевірка
займає один рядок: `checksum(icmp) != 0` означає, що пакет пошкоджено, і його треба
відкинути. Заголовок IPv4 має окрему контрольну суму, яку перевіряє ядро
([RFC 791, Header Checksum](https://www.rfc-editor.org/rfc/rfc791#section-3.1)).

### Тайм-аут сокета

[`socket.settimeout(seconds)`](https://docs.python.org/3/library/socket.html#socket.socket.settimeout)
обмежує час очікування для операцій сокета. Якщо за цей час пакет не прийшов,
`recvfrom` кидає [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError).
До Python 3.10 цей виняток називався `socket.timeout`, тепер це псевдонім
([документація](https://docs.python.org/3/library/socket.html#socket.timeout)).

#### Чому потрібен дедлайн, а не просто `settimeout(1.0)`

`settimeout(1.0)` обмежує **кожен** виклик `recvfrom` окремо. Уявімо, що кожні 0.5 с
приходить чужий пакет:

```
settimeout(1.0) один раз:
 0.0  recvfrom ─ 0.5 чужий ─ recvfrom ─ 1.0 чужий ─ recvfrom ─ 1.5 чужий ─ ...  ← чекаємо вічно

дедлайн = старт + 1.0:
 0.0  recvfrom(1.0) ─ 0.5 чужий ─ recvfrom(0.5) ─ 1.0 чужий ─ залишок 0 → тайм-аут ✓
```

Тому перед кожним `recvfrom` рахуємо, скільки часу **залишилося** до дедлайну.

### Помилки операційної системи

Помилки системних викликів Python перетворює на винятки — підкласи
[`OSError`](https://docs.python.org/3/library/exceptions.html#OSError). Атрибут
`strerror` містить текст помилки, а `errno` — її номер
([модуль `errno`](https://docs.python.org/3/library/errno.html), [`errno(3)`](https://man7.org/linux/man-pages/man3/errno.3.html)):

| Ситуація | Виняток | errno | Текст |
|---|---|---|---|
| raw-сокет без root | [`PermissionError`](https://docs.python.org/3/library/exceptions.html#PermissionError) | `EPERM` | Operation not permitted |
| немає маршруту до адреси | `OSError` | `ENETUNREACH` | Network is unreachable |
| тайм-аут | [`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError) | — | — |

### Повідомлення «no answer yet»

Системний ping за замовчуванням нічого не друкує, якщо відповідь не прийшла. З опцією
`-O` ([`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html)) він друкує
`no answer yet for icmp_seq=N`. Ми друкуємо цей рядок завжди: так видно, що програма
працює, а не «зависла».

---

## Практика

### Крок 1. Відправка — окрема функція

```python
def send_echo_request(
    sock: socket.socket, address: str, identifier: int, sequence: int, payload: bytes
) -> float:
    """Відправляє Echo Request і повертає момент відправки (time.perf_counter)."""
    packet = build_echo_request(identifier, sequence, payload)
    send_time = time.perf_counter()
    sock.sendto(packet, (address, 0))
    return send_time
```

Анотація `sock: socket.socket` означає «об'єкт класу [`socket.socket`](https://docs.python.org/3/library/socket.html#socket.socket)».

### Крок 2. Очікування своєї відповіді

```python
def receive_reply(
    sock: socket.socket, identifier: int, sequence: int, timeout: float
) -> tuple[str, int, int, float] | None:
    deadline = time.perf_counter() + timeout

    while True:
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

        if checksum(icmp) != 0:
            continue

        type_, code, reply_id, reply_seq = parse_icmp_header(icmp)
        if type_ != ICMP_ECHO_REPLY or reply_id != identifier or reply_seq != sequence:
            continue

        return source, ttl, len(icmp), receive_time
```

- **Перевірки довжини** йдуть перед розбором. Без них [`struct.unpack`](https://docs.python.org/3/library/struct.html#struct.unpack) на обрізаному пакеті кинув би [`struct.error`](https://docs.python.org/3/library/struct.html#struct.error).
- [`continue`](https://docs.python.org/3/reference/simple_stmts.html#the-continue-statement) — перейти до наступної ітерації, тобто чекати далі.
- Тип результату `tuple[...] | None`: функція повертає або кортеж, або `None`. mypy змусить того, хто викликає, перевірити `None`, перш ніж розпаковувати кортеж ([Optional types](https://mypy.readthedocs.io/en/stable/kinds_of_types.html#optional-types-and-the-none-type)).

### Крок 3. Зрозумілі помилки в `main()`

```python
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError as exc:
        print(f"ping: socket: {exc.strerror}", file=sys.stderr)
        print("ping: raw-сокет потребує прав root, запустіть через sudo", file=sys.stderr)
        return EXIT_ERROR
    ...
    with sock:
        try:
            send_time = send_echo_request(
                sock, address, identifier, sequence, build_payload(payload_size)
            )
        except OSError as exc:
            print(f"ping: sendto: {exc.strerror}", file=sys.stderr)
            return EXIT_ERROR

        reply = receive_reply(sock, identifier, sequence, DEFAULT_TIMEOUT)

    if reply is None:
        print(f"no answer yet for icmp_seq={sequence}")
        return EXIT_NO_REPLY

    source, ttl, size, receive_time = reply
    rtt_ms = (receive_time - send_time) * 1000
    print(f"{size} bytes from {source}: icmp_seq={sequence} ttl={ttl} time={format_rtt(rtt_ms)} ms")
    return EXIT_OK
```

- Сокет створюється **до** рядка `PING ...`, тож без root програма не друкує зайвого.
- `with sock:` — створений раніше сокет теж можна використати як context manager.
- Коди завершення тепер такі самі, як у [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html): `0` — є відповідь, `1` — немає відповіді, `2` — помилка.

---

## Запуск

Усі приклади запущено в тестовій мережі [`netlab.sh`](../netlab/netlab.sh) (root не потрібен).

```console
$ ../netlab/netlab.sh 'python3 ping.py 10.0.0.2; echo "exit code: $?"'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.166 ms
exit code: 0

$ ../netlab/netlab.sh 'python3 ping.py 10.1.0.99; echo "exit code: $?"'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
no answer yet for icmp_seq=1
exit code: 1
```

**Чужий трафік більше не заважає.** Повторимо експеримент з уроку 3:

```console
$ ../netlab/netlab.sh 'ping -q -c 40 -i 0.05 10.0.0.2 >/dev/null & sleep 0.2; python3 ping.py 10.1.0.99'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
no answer yet for icmp_seq=1
```

**Без root і без маршруту:**

```console
$ python3 ping.py 127.0.0.1; echo "exit code: $?"
ping: socket: Operation not permitted
ping: raw-сокет потребує прав root, запустіть через sudo
exit code: 2

$ unshare -rn python3 ping.py 8.8.8.8     # мережевий простір без жодного маршруту
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
ping: sendto: Network is unreachable
```

## Тести

Нові функції `send_echo_request()` і `receive_reply()` приймають справжній
`socket.socket`, тому протестувати їх без мережі й root важко. Тести з уроку 3
лишилися без змін і проходять. До цієї проблеми повернемося в
[уроці 7](../07-refactoring/README.md), де навчимося підміняти сокет.

```console
$ python3 -m unittest
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
| `socket.settimeout` | <https://docs.python.org/3/library/socket.html#socket.socket.settimeout> |
| `TimeoutError` | <https://docs.python.org/3/library/exceptions.html#TimeoutError> |
| `socket.timeout` (псевдонім) | <https://docs.python.org/3/library/socket.html#socket.timeout> |
| `OSError`, `strerror`, `errno` | <https://docs.python.org/3/library/exceptions.html#OSError> |
| `PermissionError` | <https://docs.python.org/3/library/exceptions.html#PermissionError> |
| модуль `errno` | <https://docs.python.org/3/library/errno.html> |
| `struct.error` | <https://docs.python.org/3/library/struct.html#struct.error> |
| `continue` | <https://docs.python.org/3/reference/simple_stmts.html#the-continue-statement> |
| `try` / `except` | <https://docs.python.org/3/reference/compound_stmts.html#the-try-statement> |
| mypy: `X \| None` | <https://mypy.readthedocs.io/en/stable/kinds_of_types.html#optional-types-and-the-none-type> |

## Вправи

1. Приберіть дедлайн і залиште `sock.settimeout(DEFAULT_TIMEOUT)` перед циклом. Повторіть експеримент з чужим трафіком (`-i 0.05`). Скільки часу тепер працює програма? Чому?
2. Додайте прапорець `-v`: якщо його вказано, друкуйте в stderr кожен відкинутий пакет з причиною (`bad checksum`, `foreign id` …). (У [уроці 7](../07-refactoring/README.md) зробимо це через `logging`.)
3. Що станеться, якщо приберемо перевірку `reply_seq != sequence`? Опишіть сценарій, у якому це дасть неправильний результат. (Відповідь знадобиться в уроці 5.)
4. Виконайте `ping -O -c 3 10.1.0.99` у тестовій мережі та порівняйте вивід з нашим.

## Джерела

- [RFC 792](https://www.rfc-editor.org/rfc/rfc792) — identifier і sequence для зіставлення запитів і відповідей (с. 14)
- [RFC 1071](https://www.rfc-editor.org/rfc/rfc1071) — перевірка контрольної суми
- [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html) — коди завершення, опція `-O`
- [`errno(3)`](https://man7.org/linux/man-pages/man3/errno.3.html) — коди помилок `EPERM`, `ENETUNREACH`
- [Notes on socket timeouts](https://docs.python.org/3/library/socket.html#notes-on-socket-timeouts) — як Python реалізує тайм-аути (неблокуючий режим + [`poll(2)`](https://man7.org/linux/man-pages/man2/poll.2.html))
