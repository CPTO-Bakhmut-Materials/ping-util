#!/bin/sh
# Тестова мережа для курсу. Права root НЕ потрібні.
#
# Створює ізольовані мережеві простори імен (network namespaces):
#
#   [клієнт 10.0.0.1] --veth-- [маршрутизатор 10.0.0.2 | 10.1.0.1] --> 10.1.0.0/24 (dummy)
#
# і запускає команду в «клієнті». Усередині ми root у власному user namespace,
# тому raw-сокети працюють без sudo і не впливають на справжню мережу.
#
# Що можна перевірити:
#   10.0.0.2, 10.1.0.1   відповідають на ping
#   10.1.0.99            пакети зникають без відповіді (тайм-аут)
#   10.1.0.99 з -t 1     маршрутизатор повертає Time to live exceeded
#   10.9.9.9             маршрутизатор повертає Destination Net Unreachable
#   10.0.0.77            клієнт сам повертає Destination Host Unreachable (через ~3 с)
#
# Використання:
#   ./netlab.sh 'python3 03-first-ping/ping.py 10.0.0.2'
#   ./netlab.sh          # інтерактивна оболонка всередині мережі (вихід: exit)

COMMAND="${1:-${SHELL:-/bin/sh}}"

exec unshare --map-root-user --net sh -c '
set -e
ip link set lo up

# Маршрутизатор живе в окремому мережевому просторі імен, який тримає процес sleep.
unshare --net sleep infinity &
ROUTER=$!
trap "kill $ROUTER" EXIT
sleep 0.2

# Пара віртуальних інтерфейсів: a0 у клієнта, b0 у маршрутизатора.
ip link add a0 type veth peer name b0 netns "$ROUTER"
ip addr add 10.0.0.1/24 dev a0
ip link set a0 up
ip route add default via 10.0.0.2

nsenter --net="/proc/$ROUTER/ns/net" sh -c "
    ip link set lo up
    ip addr add 10.0.0.2/24 dev b0
    ip link set b0 up
    # dummy-інтерфейс: мережа 10.1.0.0/24 існує, але пакети туди зникають.
    ip link add d0 type dummy
    ip addr add 10.1.0.1/24 dev d0
    ip link set d0 up
    # Маршрутизатор пересилає пакети між інтерфейсами.
    echo 1 > /proc/sys/net/ipv4/ip_forward
"
sleep 0.5

set +e
sh -c "$1"
' netlab "$COMMAND"
