#!/usr/bin/env bash
# Launch waybar under a small supervisor: restart it after a crash, with
# backoff and a restart-loop guard. An intentional stop (waybar-toggle) creates
# the stop flag and kills this supervisor first, so it never triggers a restart.
set -uo pipefail

dir="$HOME/.config/waybar"
run_dir="${XDG_RUNTIME_DIR:-/tmp}/waybar-supervisor"
pid_file="$run_dir/pid"
stop_flag="$run_dir/stop"
log="${XDG_CACHE_HOME:-$HOME/.cache}/waybar.log"

max_restarts=5      # crashes allowed inside the window below ...
window_secs=60      # ... before giving up
stable_secs=30      # a run this long resets the backoff

mkdir -p -- "$run_dir" "$(dirname -- "$log")"

# Replace any previous supervisor (and its waybar) instead of stacking them.
if [[ -f "$pid_file" ]]; then
  old="$(cat -- "$pid_file" 2>/dev/null || true)"
  if [[ -n "$old" && "$old" != "$$" ]] && kill -0 "$old" 2>/dev/null; then
    kill "$old" 2>/dev/null || true
    for _ in $(seq 20); do kill -0 "$old" 2>/dev/null || break; sleep 0.1; done
  fi
fi
pkill -x waybar 2>/dev/null || true
for _ in $(seq 30); do pgrep -x waybar >/dev/null || break; sleep 0.1; done
pkill -9 -x waybar 2>/dev/null || true

rm -f -- "$stop_flag"
echo "$$" >"$pid_file"
: >"$log"

child=""
cleanup() {
  [[ -n "$child" ]] && kill "$child" 2>/dev/null
  [[ "$(cat -- "$pid_file" 2>/dev/null)" == "$$" ]] && rm -f -- "$pid_file"
  exit 0
}
trap cleanup TERM INT HUP
# `pkill -SIGUSR1 waybar` style patterns must not kill the supervisor.
trap ':' USR1 USR2

note() { printf '[%(%F %T)T] [supervisor] %s\n' -1 "$*" >>"$log"; }

wayland_alive() {
  [[ -n "${WAYLAND_DISPLAY:-}" ]] || return 1
  [[ "$WAYLAND_DISPLAY" == /* ]] && [[ -S "$WAYLAND_DISPLAY" ]] && return 0
  [[ -S "${XDG_RUNTIME_DIR:-/run/user/$UID}/$WAYLAND_DISPLAY" ]]
}

crashes=()
backoff=1
while :; do
  started=$SECONDS
  waybar -c "$dir/config.jsonc" -s "$dir/style.css" >>"$log" 2>&1 &
  child=$!
  # `wait` returns early when a trapped signal arrives; keep waiting for waybar.
  while :; do
    wait "$child"; rc=$?
    kill -0 "$child" 2>/dev/null || break
  done
  child=""

  [[ -e "$stop_flag" ]] && { note "stopped on request"; break; }
  wayland_alive || { note "compositor gone, not restarting"; break; }

  now=$SECONDS
  (( now - started >= stable_secs )) && backoff=1
  recent=()
  for t in "${crashes[@]}"; do (( now - t < window_secs )) && recent+=("$t"); done
  crashes=("${recent[@]}" "$now")
  if (( ${#crashes[@]} > max_restarts )); then
    note "waybar exited $rc; ${#crashes[@]} crashes in ${window_secs}s, giving up"
    command -v notify-send >/dev/null &&
      notify-send -u critical "Waybar" "Crashed repeatedly; supervisor gave up. Run waybar-toggle to retry."
    break
  fi
  note "waybar exited $rc; restarting in ${backoff}s"
  sleep "$backoff"
  [[ -e "$stop_flag" ]] && { note "stopped on request"; break; }
  backoff=$(( backoff * 2 > 16 ? 16 : backoff * 2 ))
done

[[ "$(cat -- "$pid_file" 2>/dev/null)" == "$$" ]] && rm -f -- "$pid_file"
exit 0
