#!/usr/bin/env bash
set -euo pipefail

image="${1:?image is required}"
name=craft-apps-smoke
volume=craft-apps-smoke-config

cleanup() {
    docker logs "$name" || true
    docker rm -f "$name" || true
    docker volume rm "$volume" || true
}
trap cleanup EXIT

docker volume create "$volume"
docker run -d --name "$name" --security-opt seccomp=unconfined --shm-size=1g \
    -e PUID=1000 -e PGID=1000 -e TZ=Etc/UTC \
    -v "${volume}:/config" -p 127.0.0.1:3001:3001 "$image"

wait_for_desktop() {
    started=$(docker inspect -f '{{.State.StartedAt}}' "$name")
    for attempt in $(seq 1 90); do
        if [[ "$(docker inspect -f '{{.State.Running}}' "$name")" != true ]]; then
            echo 'Container exited before desktop startup' >&2
            return 1
        fi
        if docker logs --since "$started" "$name" 2>&1 | grep -Fq '[ls.io-init] done.' && \
            curl --insecure --fail --silent https://127.0.0.1:3001/ -o /tmp/craft-desktop.html; then
            test -s /tmp/craft-desktop.html
            return 0
        fi
        sleep 2
    done
    echo 'Desktop startup timed out' >&2
    return 1
}

wait_for_desktop
while read -r app tag; do
    docker exec "$name" test -x "/usr/bin/${app}"
    docker exec "$name" test -f "/usr/share/applications/ai.storyteller.${app}.desktop"
    installed=$(docker exec "$name" dpkg-query -W '-f=${Version}' "$app")
    # Debian adds its packaging revision (for example 0.7.0-1) to the app version.
    upstream=${installed%-*}
    upstream=${upstream#*:}
    if [[ "$upstream" != "${tag#v}" ]]; then
        echo "${app}: installed ${installed}, expected upstream ${tag#v}" >&2
        exit 1
    fi
    echo "Verified ${app} ${installed}"
done < <(jq -r 'to_entries[] | "\(.key) \(.value)"' root/defaults/craft-releases.json)

# Confirm an existing user config survives the same container restarting.
docker exec "$name" sh -c 'printf preserved > /config/smoke-marker'
docker restart "$name"
wait_for_desktop
test "$(docker exec "$name" cat /config/smoke-marker)" = preserved
echo 'Desktop startup, installed releases and restart checks passed'
