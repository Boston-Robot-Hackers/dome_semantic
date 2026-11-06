#!/usr/bin/env bash
# power_load_test.sh — add load to the robot one stage at a time, watch the 5 V rail.
# Author: Pito Salas and Claude Code
# Open Source Under MIT license
#
# Run from the workspace root (~/ros2_ws):
#   src/dome_semantic/tools/power_load_test.sh [--hold SECONDS]
#   src/dome_semantic/tools/power_load_test.sh --report RUN_DIR
#
# Stages run in STAGES order, each held --hold seconds (default 30). Loads
# accumulate, except `cpu`, whose stress-ng stops when its stage ends.
# Background monitors stamp each line with the current stage (read from the
# run dir's `stage` file) and append to ~/power_tests/<timestamp>/*.log one
# line at a time, so a crash keeps everything up to the last line.
#
# Every stage and monitor runs in its own process group (`set -m` around the
# launch, which also keeps SIGINT at its default). Cleanup stops stages
# newest first with SIGINT, so the semantic node saves its map, then SIGTERM
# and SIGKILL for any group still alive after STOP_WAIT_S.

set -o pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SUMMARY_AWK="$SCRIPT_DIR/power_summary.awk"
UNDERVOLT_V=4.8
RAIL_PERIOD_S=0.2
STOP_WAIT_S=10
TOPIC_WAIT_S=10
HOLD_S=30
STAGES=(idle base cpu oak subscriber semantic worst_case)
STACK_PATTERN="stress-ng|dome_vision|semantic_map|static_transform_publisher|topic hz"
STAGE_PGIDS=()
MONITOR_PGIDS=()

declare -A STAGE_DESC=(
    [idle]="nothing running (baseline)"
    [base]="dome2 drivers + battery"
    [cpu]="stress-ng on 4 cores"
    [oak]="OAK stack with depth (watch for the USB 3 switch)"
    [subscriber]="ros2 topic hz /oak/detections_3d, so inference runs"
    [semantic]="semantic node, static map->odom"
    [worst_case]="stress-ng on 4 cores with everything running"
)

die() {
    echo "power_load_test: $*" >&2
    exit 1
}

usage() {
    cat <<EOF
Usage (from the workspace root, e.g. ~/ros2_ws):
  $0 [--hold SECONDS]     run the load stages: ${STAGES[*]}
  $0 --report RUN_DIR     re-print the summary of an earlier run
EOF
}

parse_args() {
    while (($#)); do
        case $1 in
            --hold)
                [[ ${2:-} =~ ^[1-9][0-9]*$ ]] ||
                    die "--hold needs a whole number of seconds"
                HOLD_S=$2
                shift 2
                ;;
            --report)
                [[ -n ${2:-} ]] || die "--report needs a run directory"
                REPORT_DIR=$2
                shift 2
                ;;
            -h | --help)
                usage
                exit 0
                ;;
            *) die "unknown argument: $1 (try --help)" ;;
        esac
    done
}

stamp() {
    date '+%F %T.%3N'
}

set_stage() {
    # Write then rename, so a monitor never reads a half-written file.
    echo "$1" >"$STAGE_FILE.tmp" && mv "$STAGE_FILE.tmp" "$STAGE_FILE"
}

summarize() {
    local run_dir=$1 only=${2:-} name logs=()
    for name in rail kernel wifi stage_info; do
        [[ -f $run_dir/$name.log ]] && logs+=("$run_dir/$name.log")
    done
    awk -v only="$only" -v undervolt_v="$UNDERVOLT_V" -f "$SUMMARY_AWK" "${logs[@]}"
}

report() {
    [[ -f $1/rail.log ]] || die "no rail.log in $1: not a power test run directory"
    summarize "$1"
    echo "Kernel log of the boot before this one:"
    echo "  journalctl -k -b -1 | grep -iE 'voltage|usb'"
}

preflight() {
    [[ -f install/setup.bash ]] ||
        die "run from the workspace root (e.g. ~/ros2_ws): no install/setup.bash here"
    # shellcheck disable=SC1091
    source install/setup.bash
    local cmd running
    for cmd in vcgencmd bl ros2 stress-ng journalctl lsusb ping pgrep; do
        command -v "$cmd" >/dev/null || die "$cmd not found"
    done
    [[ -n ${DOME_VISION_CONFIG:-} && -f $DOME_VISION_CONFIG ]] ||
        die "DOME_VISION_CONFIG must name the dome_vision config file"
    vcgencmd pmic_read_adc EXT5V_V | grep -q EXT5V_V ||
        die "vcgencmd can't read EXT5V_V"
    lsusb | grep -q "ID 03e7:" || die "the OAK-D (USB ID 03e7) isn't on USB"
    GATEWAY=$(ip route | awk '/default/ {print $3; exit}')
    [[ -n $GATEWAY ]] || die "no default route, so no gateway to ping"
    running=$(pgrep -af "$STACK_PATTERN")
    [[ -z $running ]] ||
        die "stop these first, or the stages mean nothing:"$'\n'"$running"
    [[ $(vcgencmd get_throttled) == "throttled=0x0" ]] ||
        echo "WARNING: $(vcgencmd get_throttled) already; reboot for a clean start" >&2
}

monitor_rail() {
    local volts throttled
    while true; do
        volts=$(vcgencmd pmic_read_adc EXT5V_V | cut -d= -f2 | tr -d V)
        throttled=$(vcgencmd get_throttled | cut -d= -f2)
        echo "$(stamp) $(<"$STAGE_FILE") $volts $throttled"
        sleep "$RAIL_PERIOD_S"
    done >>"$RUN_DIR/rail.log"
}

monitor_kernel() {
    local line
    journalctl -kf -n 0 --no-pager | grep --line-buffered -iE "voltage|usb" |
        while IFS= read -r line; do
            echo "$(stamp) $(<"$STAGE_FILE") $line" >>"$RUN_DIR/kernel.log"
            echo "  [kernel] $line"
        done
}

monitor_wifi() {
    local rtt_ms
    while true; do
        rtt_ms=$(ping -c 1 -W 1 "$GATEWAY" | sed -n 's/.*time=\([0-9.]*\).*/\1/p')
        echo "$(stamp) $(<"$STAGE_FILE") ${rtt_ms:-lost}"
        sleep 1
    done >>"$RUN_DIR/wifi.log"
}

launch_group() {
    # Job control on: the job gets its own process group and default SIGINT.
    set -m
    "$@" </dev/null &
    LAST_PGID=$!
    set +m
}

run_logged() {
    local log=$1
    shift
    exec "$@" >"$log" 2>&1
}

launch_stage() {
    local stage=$1
    shift
    launch_group run_logged "$RUN_DIR/procs/$stage.log" "$@"
    STAGE_PGIDS+=("$LAST_PGID")
}

start_stage() {
    case $1 in
        idle) ;;
        base) launch_stage "$1" bl dome2 robot.launch.py --options "d b" ;;
        cpu | worst_case) launch_stage "$1" stress-ng --cpu 4 ;;
        oak)
            launch_stage "$1" bl dome_vision_ros dome_vision_ros.launch.py \
                --config "$DOME_VISION_CONFIG" --depth true
            ;;
        subscriber)
            launch_stage "$1" env PYTHONUNBUFFERED=1 ros2 topic hz /oak/detections_3d
            ;;
        semantic)
            launch_stage "$1" bl dome_semantic semantic.launch.py \
                --map_name power_test --static_map_odom true
            ;;
        *) die "no such stage: $1" ;;
    esac
}

stop_group() {
    local pgid=$1 tries
    kill -INT -- "-$pgid" 2>/dev/null || return 0
    for ((tries = 0; tries < STOP_WAIT_S * 2; tries++)); do
        kill -0 -- "-$pgid" 2>/dev/null || return 0
        sleep 0.5
    done
    echo "  process group $pgid ignored SIGINT for ${STOP_WAIT_S}s; killing it" >&2
    kill -TERM -- "-$pgid" 2>/dev/null
    sleep 2
    kill -KILL -- "-$pgid" 2>/dev/null
}

battery_reading() {
    local csv
    # CSV: stamp.sec, stamp.nanosec, frame_id, bus_voltage_v, current_a, power_w, ...
    csv=$(timeout "$TOPIC_WAIT_S" ros2 topic echo --once --csv /telemetry/battery \
        2>/dev/null)
    if [[ -z $csv ]]; then
        echo "pack=no_reading"
        return
    fi
    awk -F, '{printf "pack_v=%.2f power_w=%.1f", $4, $6}' <<<"$csv"
}

oak_usb_reading() {
    local speed
    # The OAK-D is the only device here on the usbfs driver.
    speed=$(lsusb -t | awk '/Driver=usbfs/ {print $NF; exit}')
    echo "oak_usb=${speed:-absent}"
    [[ $speed == 5000M ]] ||
        echo "  WARNING: OAK-D at ${speed:-absent}, not 5000M (USB 3)" >&2
}

detection_rate_reading() {
    local rate
    rate=$(grep -o "average rate: [0-9.]*" "$RUN_DIR/procs/subscriber.log" |
        tail -1 | awk '{print $3}')
    echo "det_hz=${rate:-none}"
}

record_stage_info() {
    local stage=$1 fields=()
    [[ $stage == idle ]] || fields+=("$(battery_reading)")
    case $stage in
        oak | subscriber | semantic | worst_case) fields+=("$(oak_usb_reading)") ;;
    esac
    [[ -f $RUN_DIR/procs/subscriber.log ]] && fields+=("$(detection_rate_reading)")
    ((${#fields[@]})) && echo "$(stamp) $stage ${fields[*]}" >>"$RUN_DIR/stage_info.log"
}

run_stage() {
    local stage=$1
    set_stage "$stage"
    echo
    echo "=== $stage: ${STAGE_DESC[$stage]} ($(stamp)) ==="
    start_stage "$stage"
    sleep "$HOLD_S"
    record_stage_info "$stage"
    [[ $stage == cpu ]] && stop_group "${STAGE_PGIDS[-1]}"
    summarize "$RUN_DIR" "$stage"
}

start_monitors() {
    local monitor
    for monitor in monitor_rail monitor_kernel monitor_wifi; do
        launch_group "$monitor"
        MONITOR_PGIDS+=("$LAST_PGID")
    done
}

cleanup() {
    trap '' INT TERM
    trap - EXIT
    local i left
    set_stage shutdown
    echo
    echo "Stopping stages, newest first..."
    for ((i = ${#STAGE_PGIDS[@]} - 1; i >= 0; i--)); do
        stop_group "${STAGE_PGIDS[i]}"
    done
    for i in "${MONITOR_PGIDS[@]}"; do
        kill -TERM -- "-$i" 2>/dev/null
    done
    left=$(pgrep -af "$STACK_PATTERN")
    [[ -z $left ]] || printf "WARNING: still running after cleanup:\n%s\n" "$left" >&2
    echo
    echo "=== Summary ==="
    summarize "$RUN_DIR" | tee "$RUN_DIR/summary.txt"
    echo "Logs: $RUN_DIR"
}

main() {
    parse_args "$@"
    if [[ -n ${REPORT_DIR:-} ]]; then
        report "$REPORT_DIR"
        exit 0
    fi
    preflight
    RUN_DIR="$HOME/power_tests/$(date +%F_%H%M%S)"
    STAGE_FILE="$RUN_DIR/stage"
    mkdir -p "$RUN_DIR/procs"
    set_stage idle
    trap cleanup EXIT
    trap "exit 130" INT TERM
    start_monitors
    echo "Logging to $RUN_DIR. Each stage holds ${HOLD_S}s. Ctrl-C stops everything."
    local stage
    for stage in "${STAGES[@]}"; do
        run_stage "$stage"
    done
}

main "$@"
