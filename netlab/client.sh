#!/bin/sh
# Клієнт тестової мережі. Запускається з netlab.sh усередині нових user і network
# namespace, тому тут ми root і бачимо лише власні мережеві інтерфейси.
#
# Аргумент: команда, яку треба виконати в мережі клієнта.

set -e
ip link set lo up

# Маршрутизатор живе в окремому мережевому просторі імен, який тримає процес sleep.
unshare --net sleep infinity &
ROUTER=$!
trap 'kill $ROUTER' EXIT
sleep 0.2

# Пара віртуальних інтерфейсів: a0 у клієнта, b0 у маршрутизатора.
ip link add a0 type veth peer name b0 netns "$ROUTER"
ip addr add 10.0.0.1/24 dev a0
ip link set a0 up
ip route add default via 10.0.0.2

nsenter --net="/proc/$ROUTER/ns/net" "$NETLAB_DIR/router.sh"
sleep 0.5

set +e
sh -c "$1"
