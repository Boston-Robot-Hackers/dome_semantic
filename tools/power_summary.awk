# power_summary.awk — per-stage summary of one power_load_test.sh run.
# Author: Pito Salas and Claude Code
# Open Source Under MIT license
#
# Input: any of rail.log, kernel.log, wifi.log, stage_info.log from one run
# directory. Every line starts "<date> <time> <stage>"; the rest is per file:
#   rail.log        <ext5v_volts> <get_throttled hex>
#   kernel.log      <raw journalctl -k line>
#   wifi.log        <ping ms | lost>
#   stage_info.log  key=value ...
# Variables: only (print one stage; empty = all), undervolt_v (threshold
# for the "below" count). Stages print in the order they first appear.
# Lines cut short by a crash are skipped, never guessed at.

function note_stage(stage) {
    if (!(stage in seen)) {
        seen[stage] = 1
        order[++stage_count] = stage
    }
}

function wanted(stage) {
    return only == "" || stage == only
}

function print_stage(stage) {
    printf "== %s ==\n", stage
    if (samples[stage] > 0) {
        printf "  5V rail:   min %.2f V, mean %.2f V, %d below %.2f V (%d samples)\n", \
            min_v[stage], sum_v[stage] / samples[stage], below[stage], \
            undervolt_v, samples[stage]
        printf "  throttled: %s at end, %d change(s)\n", \
            throttled_end[stage], changes[stage]
    } else {
        print "  5V rail:   no samples"
    }
    printf "  kernel:    %d undervoltage, %d USB disconnect\n", \
        undervolt[stage], usb_disconnect[stage]
    if (pings[stage] > 0)
        printf "  wifi:      worst %.1f ms, %d of %d lost\n", \
            worst_ping[stage], lost[stage], pings[stage]
    if (info[stage] != "")
        printf "  info:      %s\n", info[stage]
}

FILENAME ~ /rail\.log$/ {
    if (NF < 5 || $4 !~ /^[0-9]+\.[0-9]+$/ || $5 !~ /^0x[0-9a-fA-F]+$/) next
    # A change is charged to the stage it happens in, so compare before filtering.
    is_change = (has_prev && $5 != prev_throttled)
    prev_throttled = $5
    has_prev = 1
    if (!wanted($3)) next
    note_stage($3)
    volts = $4 + 0
    samples[$3]++
    sum_v[$3] += volts
    if (samples[$3] == 1 || volts < min_v[$3]) min_v[$3] = volts
    if (volts < undervolt_v) below[$3]++
    if (is_change) changes[$3]++
    throttled_end[$3] = $5
    next
}

FILENAME ~ /kernel\.log$/ {
    if (NF < 4 || !wanted($3)) next
    note_stage($3)
    if ($0 ~ /Undervoltage detected/) undervolt[$3]++
    if ($0 ~ /USB disconnect/) usb_disconnect[$3]++
    next
}

FILENAME ~ /wifi\.log$/ {
    if (NF < 4 || !wanted($3)) next
    if ($4 != "lost" && $4 !~ /^[0-9]+(\.[0-9]+)?$/) next
    note_stage($3)
    pings[$3]++
    if ($4 == "lost") lost[$3]++
    else if ($4 + 0 > worst_ping[$3]) worst_ping[$3] = $4 + 0
    next
}

FILENAME ~ /stage_info\.log$/ {
    if (NF < 4 || !wanted($3)) next
    note_stage($3)
    fields = $4
    for (i = 5; i <= NF; i++) fields = fields " " $i
    info[$3] = (info[$3] == "") ? fields : info[$3] " " fields
    next
}

END {
    for (i = 1; i <= stage_count; i++) print_stage(order[i])
}
