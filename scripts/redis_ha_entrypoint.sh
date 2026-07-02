#!/bin/sh
# Tier E madde 31 — shared entrypoint for the `redis` (primary) and
# `redis-replica` compose services.
#
# Why this exists: a bare `redis-server` (with or without a static
# `--replicaof`) does NOT rejoin the replication topology correctly after a
# Sentinel-driven failover. Live-reproduced: kill the master, Sentinel
# promotes the replica (correct) — but when the old master's container comes
# back (`restart: unless-stopped` or a manual `docker start`), it boots with
# its ORIGINAL static command, i.e. as a bare, unreplicated master again,
# and Sentinel — which tracks replicas by the IP they were last seen at —
# has no way to notice unless the container happens to land on the exact
# same IP (it does not always, e.g. after a real restart Docker can hand out
# a different bridge-network address).
#
# Fix: on every container start, ask each Sentinel in turn for the CURRENT
# master of `mymaster`. If one is known and it isn't us, start as a replica
# of it (this correctly re-slaves a returning former master). If none is
# known yet (cold boot — Sentinels aren't up before `redis`/`redis-replica`
# on a fresh `docker compose up`), fall back to $BOOTSTRAP_ROLE.
#
# Required env:
#   BOOTSTRAP_ROLE   "master" or "replica" — what to do when Sentinel can't
#                    be reached yet (first-ever boot of the stack).
#   BOOTSTRAP_TARGET replicaof target host used only when
#                    BOOTSTRAP_ROLE=replica (e.g. "redis").
# Optional env:
#   SENTINEL_HOSTS   comma-separated host:port list (default matches
#                    docker-compose's 3-sentinel service names).

set -eu

SENTINEL_HOSTS="${SENTINEL_HOSTS:-redis-sentinel-1:26379,redis-sentinel-2:26379,redis-sentinel-3:26379}"
MASTER_NAME="${MASTER_NAME:-mymaster}"
MY_IP="$(hostname -i 2>/dev/null | awk '{print $1}')"

discover_master() {
    old_ifs="$IFS"
    IFS=','
    for hp in $SENTINEL_HOSTS; do
        IFS="$old_ifs"
        host="${hp%%:*}"
        port="${hp##*:}"
        addr="$(redis-cli -h "$host" -p "$port" -t 1 \
            sentinel get-master-addr-by-name "$MASTER_NAME" 2>/dev/null)"
        if [ -n "$addr" ]; then
            echo "$addr"
            return 0
        fi
        IFS=','
    done
    IFS="$old_ifs"
    return 1
}

MASTER_INFO="$(discover_master || true)"

if [ -n "$MASTER_INFO" ]; then
    MASTER_IP="$(echo "$MASTER_INFO" | sed -n '1p')"
    MASTER_PORT="$(echo "$MASTER_INFO" | sed -n '2p')"
    if [ "$MASTER_IP" = "$MY_IP" ]; then
        echo "redis_ha_entrypoint: Sentinel says I ($MY_IP) am already master — starting unreplicated."
        exec redis-server /etc/redis-ha.conf
    fi
    echo "redis_ha_entrypoint: Sentinel-discovered master is $MASTER_IP:$MASTER_PORT — starting as its replica."
    exec redis-server /etc/redis-ha.conf --replicaof "$MASTER_IP" "$MASTER_PORT"
fi

if [ "$BOOTSTRAP_ROLE" = "replica" ]; then
    echo "redis_ha_entrypoint: no Sentinel reachable yet (cold boot) — bootstrapping as replica of $BOOTSTRAP_TARGET."
    exec redis-server /etc/redis-ha.conf --replicaof "$BOOTSTRAP_TARGET" 6379
fi

echo "redis_ha_entrypoint: no Sentinel reachable yet (cold boot) — bootstrapping as master."
exec redis-server /etc/redis-ha.conf
