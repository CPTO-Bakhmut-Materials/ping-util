# Урок 1. Знайомство з ping і скелет програми

[← До змісту](../README.md) · [Урок 2 →](../02-icmp-packet/README.md)

## Мета уроку

- Зрозуміти, що робить системна утиліта `ping`, і навчитися читати її вивід.
- Створити скелет нашої програми: аргументи командного рядка, перетворення імені на IP-адресу, перший рядок виводу та коди завершення.
- Додати до коду анотації типів (type hints) і навчитися перевіряти їх за допомогою `mypy`.

Наприкінці уроку маємо програму, яка поводиться як перший рядок справжнього `ping`:

```console
$ python3 ping.py example.com
PING example.com (104.20.23.154)
```

---

## Частина 1. Що таке ping

`ping` — утиліта, яка перевіряє, чи досяжний вузол у мережі, і скільки часу
займає дорога пакета туди й назад. Вона використовує протокол **ICMP**
(Internet Control Message Protocol, [RFC 792](https://www.rfc-editor.org/rfc/rfc792)):

1. Відправник надсилає повідомлення **Echo Request** (ICMP type 8).
2. Отримувач за правилами [RFC 1122, розд. 3.2.2.6](https://www.rfc-editor.org/rfc/rfc1122#section-3.2.2.6) **зобов'язаний** відповісти повідомленням **Echo Reply** (ICMP type 0) з тими самими даними.
3. Відправник вимірює, скільки часу минуло між запитом і відповіддю.

```
  наш комп'ютер                                    example.com
       │  ── ICMP Echo Request (type 8, seq=1) ──▶       │
       │                                                 │
       │  ◀── ICMP Echo Reply  (type 0, seq=1) ──        │
       │                                                 │
       └─────────── RTT = 12.1 ms ───────────────────────┘
```

Цей проміжок називають **round-trip time (RTT)**. Його формальне визначення як метрики
дано в [RFC 2681](https://www.rfc-editor.org/rfc/rfc2681).

Повний список типів ICMP-повідомлень веде IANA: [ICMP Parameters](https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml).

### Запускаємо системний ping

У Linux зазвичай встановлено `ping` з пакета [iputils](https://github.com/iputils/iputils).
Його документація — [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html), або
`man ping` у терміналі. Перевірити версію можна так:

```console
$ ping -V
ping from iputils 20250605
```

Відправимо 3 запити (`-c 3`, count):

```console
$ ping -c 3 example.com
PING example.com (104.20.23.154) 56(84) bytes of data.
64 bytes from 104.20.23.154: icmp_seq=1 ttl=58 time=12.1 ms
64 bytes from 104.20.23.154: icmp_seq=2 ttl=58 time=12.2 ms
64 bytes from 104.20.23.154: icmp_seq=3 ttl=58 time=11.4 ms

--- example.com ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2002ms
rtt min/avg/max/mdev = 11.416/11.895/12.165/0.340 ms
```

Без `-c` ping працює, доки його не зупинять клавішами **Ctrl+C**.

### Розбираємо вивід рядок за рядком

#### Рядок-заголовок

```
PING example.com (104.20.23.154) 56(84) bytes of data.
```

| Фрагмент | Значення | Джерело |
|---|---|---|
| `example.com` | ім'я, яке ввів користувач | |
| `(104.20.23.154)` | IPv4-адреса, отримана через DNS або `/etc/hosts`. **Пакети завжди йдуть на адресу, а не на ім'я.** | [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034), [`hosts(5)`](https://man7.org/linux/man-pages/man5/hosts.5.html) |
| `56` | розмір **даних** (payload) у кожному ICMP-пакеті. Змінюється опцією `-s`. | [`ping(8)`, опція `-s`](https://man7.org/linux/man-pages/man8/ping.8.html) |
| `(84)` | повний розмір IP-пакета: 56 байтів даних + 8 байтів заголовка ICMP ([RFC 792](https://www.rfc-editor.org/rfc/rfc792)) + 20 байтів заголовка IPv4 без опцій ([RFC 791, розд. 3.1](https://www.rfc-editor.org/rfc/rfc791#section-3.1)) | |

```
┌──────────────────┬──────────────┬─────────────────────────┐
│ IPv4 header 20 B │ ICMP hdr 8 B │      payload 56 B       │
└──────────────────┴──────────────┴─────────────────────────┘
                   └──────────── 64 B ──────────────────────┘
└──────────────────────────── 84 B ─────────────────────────┘
```

#### Рядок відповіді

```
64 bytes from 104.20.23.154: icmp_seq=1 ttl=58 time=12.1 ms
```

| Поле | Значення | Джерело |
|---|---|---|
| `64 bytes` | розмір отриманого ICMP-повідомлення: 8 байтів заголовка + 56 байтів даних. IP-заголовок сюди не входить. | [RFC 792, Echo Reply](https://www.rfc-editor.org/rfc/rfc792) |
| `from 104.20.23.154` | адреса, з якої прийшла відповідь (поле Source Address заголовка IPv4) | [RFC 791, розд. 3.1](https://www.rfc-editor.org/rfc/rfc791#section-3.1) |
| `icmp_seq=1` | **Sequence Number**: порядковий номер запиту. Дає змогу зіставити відповідь із запитом і помітити втрачені пакети. | [RFC 792, Echo](https://www.rfc-editor.org/rfc/rfc792) |
| `ttl=58` | **Time To Live** з IP-заголовка **відповіді**. Кожен маршрутизатор зменшує TTL на 1, а пакет із TTL=0 знищується. Типові початкові значення — 64 (Linux), 128 (Windows), 255. Отже, 58 означає, що відповідь пройшла приблизно 64 − 58 = 6 маршрутизаторів. | [RFC 791, розд. 3.1 (Time to Live)](https://www.rfc-editor.org/rfc/rfc791#section-3.1), [RFC 1700 (рекомендований TTL = 64)](https://www.rfc-editor.org/rfc/rfc1700) |
| `time=12.1 ms` | RTT: час від відправки запиту до отримання відповіді | [RFC 2681](https://www.rfc-editor.org/rfc/rfc2681) |

#### Підсумкова статистика

```
--- example.com ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2002ms
rtt min/avg/max/mdev = 11.416/11.895/12.165/0.340 ms
```

| Поле | Значення |
|---|---|
| `3 packets transmitted` | скільки Echo Request відправлено |
| `3 received` | скільки Echo Reply отримано |
| `0% packet loss` | частка запитів без відповіді: `(transmitted − received) / transmitted × 100`. Метрику втрат описано в [RFC 6673](https://www.rfc-editor.org/rfc/rfc6673). |
| `time 2002ms` | загальна тривалість роботи. За замовчуванням ping робить паузу 1 с між запитами (опція `-i`), тому 3 запити займають близько 2 с. |
| `min/avg/max` | мінімальний, середній і максимальний RTT |
| `mdev` | середнє відхилення RTT: наскільки «стрибає» затримка. iputils рахує його як `sqrt(avg(rtt²) − avg(rtt)²)`, див. функцію `finish()` у [`ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c). |

### Коли щось іде не так

**Невідоме ім'я.** Ім'я не вдалося перетворити на адресу:

```console
$ ping -c 2 nonexistent.invalid
ping: nonexistent.invalid: Name or service not known
```

Домен `.invalid` зарезервовано саме для таких прикладів ([RFC 6761, розд. 6.4](https://www.rfc-editor.org/rfc/rfc6761#section-6.4)).

**Відповідь-помилка від маршрутизатора.** Замість Echo Reply прийшло інше ICMP-повідомлення:

```console
$ ping -c 3 -W 1 10.255.255.1
PING 10.255.255.1 (10.255.255.1) 56(84) bytes of data.
From 194.44.212.246 icmp_seq=1 Time to live exceeded
From 194.44.212.246 icmp_seq=2 Time to live exceeded
From 194.44.212.246 icmp_seq=3 Time to live exceeded

--- 10.255.255.1 ping statistics ---
3 packets transmitted, 0 received, +3 errors, 100% packet loss, time 2003ms
```

Тут маршрутизатор `194.44.212.246` повідомив, що TTL пакета дійшов до нуля.
Це ICMP **Time Exceeded** (type 11, [RFC 792](https://www.rfc-editor.org/rfc/rfc792)).
Такі повідомлення ми навчимося обробляти в уроці 8.

### Коди завершення

Програми повідомляють результат роботи не лише текстом, а й **кодом завершення**
(exit status). Його можна використати в скриптах. За [`ping(8)`, розділ EXIT STATUS](https://man7.org/linux/man-pages/man8/ping.8.html):

| Код | Коли |
|---|---|
| `0` | отримано хоча б одну відповідь |
| `1` | жодної відповіді не отримано |
| `2` | інша помилка, наприклад невідоме ім'я або неправильні аргументи |

```console
$ ping -c 1 nonexistent.invalid; echo $?
ping: nonexistent.invalid: Name or service not known
2
```

> У `fish` замість `$?` пишіть `$status`.

### Корисні опції (знадобляться в наступних уроках)

| Опція | Значення | Урок |
|---|---|---|
| `-c N` | відправити N запитів і завершитися | 5 |
| `-i S` | пауза між запитами в секундах | 5 |
| `-W S` | скільки чекати на відповідь | 8 |
| `-t N` | TTL вихідних пакетів | 8 |
| `-s N` | розмір даних у пакеті | 8 |

---

## Частина 2. Скелет нашої програми

### Крок 1. Аргументи командного рядка

Для розбору аргументів використовуємо модуль [`argparse`](https://docs.python.org/3/library/argparse.html)
зі стандартної бібліотеки. Він сам формує довідку (`-h`), перевіряє, чи є обов'язкові
аргументи, і при помилці завершує програму з кодом `2`. Це збігається з поведінкою
`ping`.

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Розбирає аргументи командного рядка."""
    parser = argparse.ArgumentParser(
        prog="ping",
        description="Надсилає ICMP ECHO_REQUEST до мережевого вузла.",
    )
    parser.add_argument("host", help="ім'я або IPv4-адреса вузла")
    return parser.parse_args(argv)
```

- [`argparse.ArgumentParser(prog=..., description=...)`](https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser) створює парсер. `prog` — ім'я програми в довідці, `description` — опис програми.
- [`add_argument("host", help=...)`](https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument): ім'я без `-` означає **позиційний** (обов'язковий) аргумент.
- [`parse_args(argv)`](https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.parse_args) повертає об'єкт [`Namespace`](https://docs.python.org/3/library/argparse.html#argparse.Namespace), тож значення доступне як `args.host`. Якщо `argv` дорівнює `None`, аргументи беруться з [`sys.argv`](https://docs.python.org/3/library/sys.html#sys.argv). Параметр `argv` ми додали, щоб функцію можна було викликати з тестів зі своїм списком аргументів.

### Крок 2. Перетворюємо ім'я на IP-адресу

Мережеві пакети адресуються IP-адресою, тому ім'я на кшталт `example.com` спочатку
треба перетворити на адресу (*name resolution*). Це робить системна функція
`getaddrinfo` ([RFC 3493, розд. 6.1](https://www.rfc-editor.org/rfc/rfc3493#section-6.1),
[`getaddrinfo(3)`](https://man7.org/linux/man-pages/man3/getaddrinfo.3.html)). Вона
переглядає `/etc/hosts`, DNS ([RFC 1034](https://www.rfc-editor.org/rfc/rfc1034),
[RFC 1035](https://www.rfc-editor.org/rfc/rfc1035)) та інші джерела в порядку,
заданому в [`nsswitch.conf(5)`](https://man7.org/linux/man-pages/man5/nsswitch.conf.5.html).
Якщо передати їй готову IP-адресу, вона поверне цю саму адресу.

У Python ця функція доступна як [`socket.getaddrinfo`](https://docs.python.org/3/library/socket.html#socket.getaddrinfo):

```python
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
```

Навіщо тут `assert isinstance(...)`, пояснено нижче, у [кроці 4](#крок-4-анотації-типів-type-hints).

Розберімо аргументи:

- `host` — ім'я або адреса.
- `None` на місці порту: ICMP не має портів, на відміну від TCP/UDP.
- `family=socket.AF_INET` — нас цікавлять лише IPv4-адреси ([константи `AF_*`](https://docs.python.org/3/library/socket.html#socket.AF_INET)). IPv6 потребує ICMPv6 ([RFC 4443](https://www.rfc-editor.org/rfc/rfc4443)), а це вже окрема тема.
- `type=socket.SOCK_RAW` — тип сокета, який ми використаємо в уроці 3 ([константи `SOCK_*`](https://docs.python.org/3/library/socket.html#socket.SOCK_STREAM)). Без цього параметра функція повертає ту саму адресу кілька разів, по одному запису на кожен тип сокета.

Перевіримо в інтерактивному Python:

```pycon
>>> import socket
>>> socket.getaddrinfo("localhost", None, family=socket.AF_INET, type=socket.SOCK_RAW)[0]
(<AddressFamily.AF_INET: 2>, <SocketKind.SOCK_RAW: 3>, 0, '', ('127.0.0.1', 0))
```

Ім'я може мати кілька адрес. Як і системний ping, ми беремо першу.

### Крок 3. Обробка помилок і коди завершення

Якщо ім'я не знайдено, `getaddrinfo` кидає виняток [`socket.gaierror`](https://docs.python.org/3/library/socket.html#socket.gaierror).
Це підклас [`OSError`](https://docs.python.org/3/library/exceptions.html#OSError),
тому текст помилки доступний в атрибуті [`strerror`](https://docs.python.org/3/library/exceptions.html#OSError.strerror).
Отримуємо таке саме повідомлення, як у системного ping:

```python
EXIT_OK = 0
EXIT_ERROR = 2


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
```

- Помилки виводимо в **stderr** ([`sys.stderr`](https://docs.python.org/3/library/sys.html#sys.stderr), параметр `file` у [`print`](https://docs.python.org/3/library/functions.html#print)), а не в stdout. Так їх не змішано з корисним виводом, наприклад коли вивід перенаправлено у файл ([`stdio(3)`](https://man7.org/linux/man-pages/man3/stdio.3.html)).
- [f-рядки](https://docs.python.org/3/reference/lexical_analysis.html#f-strings) (`f"..."`) підставляють значення виразів у фігурних дужках.
- `main()` **повертає** код завершення, а [`sys.exit(code)`](https://docs.python.org/3/library/sys.html#sys.exit) передає його операційній системі. Завдяки цьому `main()` можна викликати з тестів, і програма не завершиться.
- Умова [`if __name__ == "__main__":`](https://docs.python.org/3/library/__main__.html) виконується лише тоді, коли файл запущено як програму, а не імпортовано як модуль. Це знадобиться в уроці 2, де тести імпортують `ping.py`.

### Крок 4. Анотації типів (type hints)

У сигнатурах усіх функцій ми вказали типи параметрів і результату:

```python
def resolve(host: str) -> str: ...
def parse_args(argv: list[str] | None = None) -> argparse.Namespace: ...
def main(argv: list[str] | None = None) -> int: ...
```

Це **анотації типів** ([PEP 484](https://peps.python.org/pep-0484/),
[глосарій: annotation](https://docs.python.org/3/glossary.html#term-annotation),
модуль [`typing`](https://docs.python.org/3/library/typing.html)). Вони описують,
які значення функція приймає і що повертає. Далі в курсі **кожна** функція матиме анотації.

#### Синтаксис, який використовуємо в курсі

| Запис | Значення | Джерело |
|---|---|---|
| `host: str` | параметр `host` — рядок | [PEP 484](https://peps.python.org/pep-0484/) |
| `-> str` | функція повертає рядок | [PEP 3107](https://peps.python.org/pep-3107/) |
| `-> None` | функція нічого не повертає | [PEP 484, «Using None»](https://peps.python.org/pep-0484/#using-none) |
| `list[str]` | список рядків. Вбудовані колекції можна параметризувати з Python 3.9. | [PEP 585](https://peps.python.org/pep-0585/) |
| `list[str] \| None` | список рядків **або** `None`. Запис через `\|` працює з Python 3.10, і саме тому курс потребує 3.10+. | [PEP 604](https://peps.python.org/pep-0604/) |
| `argparse.Namespace` | будь-який клас теж є типом | [`argparse.Namespace`](https://docs.python.org/3/library/argparse.html#argparse.Namespace) |

#### Python не перевіряє типи під час виконання

Анотації — це лише підказки. Інтерпретатор їх **не перевіряє**: він запам'ятовує їх
у функції й виконує код як звичайно. Якщо передати не той тип, помилка виникне
пізніше і глибше в коді, і з неї важко зрозуміти, де справжня причина:

```pycon
>>> import ping
>>> ping.resolve(8888)
Traceback (most recent call last):
  ...
    for res in _socket.getaddrinfo(host, port, family, type, proto, flags):
               ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: getaddrinfo() argument 1 must be string or None
```

#### Як переглянути анотації

Анотації доступні під час виконання, і їх показують інструменти документації:

```pycon
>>> import ping, inspect, typing
>>> help(ping.resolve)
Help on function resolve in module ping:

resolve(host: str) -> str
    Повертає IPv4-адресу вузла у вигляді рядка, наприклад '8.8.8.8'.
    ...
>>> inspect.signature(ping.parse_args)
<Signature (argv: list[str] | None = None) -> argparse.Namespace>
>>> typing.get_type_hints(ping.main)
{'argv': list[str] | None, 'return': <class 'int'>}
```

- [`help()`](https://docs.python.org/3/library/functions.html#help) показує сигнатуру разом із docstring.
- [`inspect.signature()`](https://docs.python.org/3/library/inspect.html#inspect.signature) повертає об'єкт сигнатури.
- [`typing.get_type_hints()`](https://docs.python.org/3/library/typing.html#typing.get_type_hints) повертає словник «ім'я параметра → тип».
- Як Python зберігає анотації, описано в [Annotations Best Practices](https://docs.python.org/3/howto/annotations.html).

#### Перевіряємо типи за допомогою mypy

Щоб знайти помилки з типами **до** запуску, використовують статичний аналізатор.
Він читає код, але не виконує його. Найпоширеніший аналізатор —
[mypy](https://mypy.readthedocs.io/en/stable/).

> **mypy і правило «без сторонніх бібліотек».** mypy — це інструмент розробника,
> як редактор чи `tcpdump`. Наша програма його не імпортує і без нього працює
> так само. Тому правило курсу не порушується.

**Встановлення.** Встановлювати пакети в системний Python не варто. У багатьох
дистрибутивах (Arch, Debian, Ubuntu, Fedora) системний `pip` це навіть забороняє
([PEP 668](https://peps.python.org/pep-0668/)). Тому створюємо віртуальне
середовище ([`venv`](https://docs.python.org/3/library/venv.html)) у корені курсу:

```console
$ cd lesson-ping
$ python3 -m venv .venv
$ .venv/bin/pip install mypy
$ .venv/bin/mypy --version
mypy 2.4.0 (compiled: yes)
```

> Можна активувати середовище (`source .venv/bin/activate`, а у fish —
> `source .venv/bin/activate.fish`) і писати просто `mypy`.
> Папку `.venv` уже додано до [`.gitignore`](../.gitignore).

**Запуск:**

```console
$ cd 01-cli-skeleton
$ ../.venv/bin/mypy --strict ping.py
Success: no issues found in 1 source file
```

Прапорець [`--strict`](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict)
вмикає всі суворі перевірки, зокрема вимогу, щоб кожна функція мала анотації.
Список усіх прапорців — у [документації mypy](https://mypy.readthedocs.io/en/stable/command_line.html).

#### Що mypy знаходить: приклад з нашого коду

Перша версія `resolve()` закінчувалася рядком `return sockaddr[0]`. Програма
працювала, але mypy повідомив про помилку:

```console
$ ../.venv/bin/mypy --strict ping.py
ping.py:36: error: Incompatible return value type (got "str | int", expected "str")  [return-value]
Found 1 error in 1 file (checked 1 source file)
```

Ми пообіцяли повернути `str`. Але `getaddrinfo` описано для **всіх** сімейств адрес
([typeshed](https://github.com/python/typeshed), звідки mypy бере типи стандартної
бібліотеки). Для деяких сімейств, наприклад `AF_CAN`, перший елемент адреси є числом.
mypy не знає, що ми запитали лише `AF_INET`, і тому вважає тип `str | int`.

Виправлення — **звуження типу** ([type narrowing](https://mypy.readthedocs.io/en/stable/type_narrowing.html)):

```python
    address = sockaddr[0]
    assert isinstance(address, str)
    return address
```

- Після [`isinstance(address, str)`](https://docs.python.org/3/library/functions.html#isinstance) mypy знає, що `address` має тип `str`.
- [`assert`](https://docs.python.org/3/reference/simple_stmts.html#the-assert-statement) під час виконання кидає `AssertionError`, якщо умова хибна. Тобто ми не просто «заспокоюємо» mypy, а явно перевіряємо своє припущення.

Друга користь — помилки у **викликах** функцій. Файл `check.py`:

```python
from ping import resolve

address = resolve(8888)
print(address + 1)
```

```console
$ ../.venv/bin/mypy check.py
check.py:3: error: Argument 1 to "resolve" has incompatible type "int"; expected "str"  [arg-type]
check.py:4: error: Unsupported operand types for + ("str" and "int")  [operator]
Found 2 errors in 1 file (checked 1 source file)
```

Обидві помилки знайдено без запуску програми і без доступу до мережі. Тут
указано точний рядок виклику, а не місце глибоко всередині `socket`.

#### Анотації в редакторі

VS Code з розширенням [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
(до нього входить Pylance) використовує анотації одразу:

- показує типи параметрів, коли наводиш курсор на функцію або набираєш виклик;
- доповнює методи: після `address.` пропонує методи `str`;
- підкреслює помилки типів, якщо в налаштуваннях указати
  `"python.analysis.typeCheckingMode": "standard"` або `"strict"`
  ([налаштування Python у VS Code](https://code.visualstudio.com/docs/python/settings-reference#_python-language-server-settings)).

#### Правило курсу

1. Кожна функція має анотації всіх параметрів і результату.
2. Перед завершенням уроку код проходить `mypy --strict` без помилок.

## Повний код

Див. [`ping.py`](ping.py).

## Перевірка

```console
$ python3 ping.py example.com
PING example.com (104.20.23.154)
$ echo $?
0

$ python3 ping.py 8.8.8.8
PING 8.8.8.8 (8.8.8.8)

$ python3 ping.py nonexistent.invalid
ping: nonexistent.invalid: Name or service not known
$ echo $?
2

$ python3 ping.py
usage: ping [-h] host
ping: error: the following arguments are required: host
$ echo $?
2

$ python3 ping.py -h
usage: ping [-h] host

Надсилає ICMP ECHO_REQUEST до мережевого вузла.

positional arguments:
  host        ім'я або IPv4-адреса вузла

options:
  -h, --help  show this help message and exit
```

> IP-адреса `example.com` у вас може бути іншою. Великі сайти мають кілька адрес
> і можуть віддавати різні з них у різний час.

Перевірка типів:

```console
$ ../.venv/bin/mypy --strict ping.py
Success: no issues found in 1 source file
```

## Використані функції та модулі

| Що | Документація |
|---|---|
| `argparse.ArgumentParser` | <https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser> |
| `ArgumentParser.add_argument` | <https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument> |
| `ArgumentParser.parse_args` | <https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.parse_args> |
| `socket.getaddrinfo` | <https://docs.python.org/3/library/socket.html#socket.getaddrinfo> |
| `socket.AF_INET` | <https://docs.python.org/3/library/socket.html#socket.AF_INET> |
| `socket.SOCK_RAW` | <https://docs.python.org/3/library/socket.html#socket.SOCK_STREAM> |
| `socket.gaierror` | <https://docs.python.org/3/library/socket.html#socket.gaierror> |
| `OSError.strerror` | <https://docs.python.org/3/library/exceptions.html#OSError.strerror> |
| `print` | <https://docs.python.org/3/library/functions.html#print> |
| `sys.stderr` | <https://docs.python.org/3/library/sys.html#sys.stderr> |
| `sys.exit` | <https://docs.python.org/3/library/sys.html#sys.exit> |
| `sys.argv` | <https://docs.python.org/3/library/sys.html#sys.argv> |
| `__main__` | <https://docs.python.org/3/library/__main__.html> |
| `isinstance` | <https://docs.python.org/3/library/functions.html#isinstance> |
| `assert` | <https://docs.python.org/3/reference/simple_stmts.html#the-assert-statement> |
| `help` | <https://docs.python.org/3/library/functions.html#help> |
| `inspect.signature` | <https://docs.python.org/3/library/inspect.html#inspect.signature> |
| `typing.get_type_hints` | <https://docs.python.org/3/library/typing.html#typing.get_type_hints> |
| `venv` | <https://docs.python.org/3/library/venv.html> |
| mypy: командний рядок | <https://mypy.readthedocs.io/en/stable/command_line.html> |

## Вправи

1. Запустіть `ping -c 5 8.8.8.8` і `ping -c 5 localhost`. Порівняйте TTL і RTT. Чому для `localhost` TTL дорівнює 64, а час менший за 0.1 мс?
2. Запустіть `ping -c 3 -s 1000 example.com`. Як змінився рядок-заголовок? Порахуйте `1000(????)` вручну.
3. Знайдіть в [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html), що робить опція `-q`, і перевірте її.
4. Змініть `resolve()` так, щоб вона повертала **всі** унікальні адреси вузла, і виведіть їх. Перевірте на `google.com`.
5. Що виведе `python3 ping.py ''` (порожній рядок)? А системний `ping ''`?
6. Приберіть з `resolve()` рядок `assert isinstance(address, str)` і запустіть `mypy --strict`. Потім приберіть анотацію `-> int` у `main()`. Які помилки показує mypy в кожному випадку?
7. Викличте `ping.main(["example.com"])` в інтерактивному Python. Що вона повертає? Навіщо `main()` має параметр `argv`?

## Джерела

- [RFC 792](https://www.rfc-editor.org/rfc/rfc792) — ICMP
- [RFC 791](https://www.rfc-editor.org/rfc/rfc791) — IPv4
- [RFC 1122, розд. 3.2.2.6](https://www.rfc-editor.org/rfc/rfc1122#section-3.2.2.6) — обов'язок хоста відповідати на Echo Request
- [RFC 2681](https://www.rfc-editor.org/rfc/rfc2681) — метрика Round-trip Delay
- [RFC 6673](https://www.rfc-editor.org/rfc/rfc6673) — метрика Round-trip Packet Loss
- [RFC 3493, розд. 6.1](https://www.rfc-editor.org/rfc/rfc3493#section-6.1) — `getaddrinfo`
- [RFC 1034](https://www.rfc-editor.org/rfc/rfc1034), [RFC 1035](https://www.rfc-editor.org/rfc/rfc1035) — DNS
- [RFC 6761](https://www.rfc-editor.org/rfc/rfc6761) — зарезервовані доменні імена (`.invalid`, `localhost`)
- [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html), [iputils](https://github.com/iputils/iputils)
- [PEP 484](https://peps.python.org/pep-0484/) — Type Hints; [PEP 585](https://peps.python.org/pep-0585/), [PEP 604](https://peps.python.org/pep-0604/) — синтаксис `list[str]` і `X | None`
- [mypy documentation](https://mypy.readthedocs.io/en/stable/), [typing — Support for type hints](https://docs.python.org/3/library/typing.html)
