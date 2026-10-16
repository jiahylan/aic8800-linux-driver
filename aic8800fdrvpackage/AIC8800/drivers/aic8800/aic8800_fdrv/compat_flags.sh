#!/bin/sh
# Distribution kernels backport cfg80211 APIs independently of LINUX_VERSION_CODE.
# Inspect declarations in the target headers instead of guessing from a version.
set -eu
header=$1
[ -r "$header" ] || exit 0
has_parameter() {
    awk -v function_name="$1" '
        $0 ~ "^[a-z_].*" function_name "\\(" { active = 1 }
        active { print; if ($0 ~ /;/) exit }
    ' "$header" | grep -qw "$2"
}
if has_parameter cfg80211_rx_spurious_frame link_id; then
    printf '%s ' -DAIC_CFG80211_SPURIOUS_LINK_ID
fi
if has_parameter cfg80211_rx_unexpected_4addr_frame link_id; then
    printf '%s ' -DAIC_CFG80211_4ADDR_LINK_ID
fi
if has_parameter cfg80211_ch_switch_notify link_id; then
    printf '%s ' -DAIC_CFG80211_CH_SWITCH_LINK_ID
fi
if has_parameter cfg80211_ch_switch_notify punct_bitmap; then
    printf '%s ' -DAIC_CFG80211_CH_SWITCH_PUNCT
fi
if has_parameter cfg80211_ch_switch_started_notify link_id; then
    printf '%s ' -DAIC_CFG80211_CH_SWITCH_STARTED_LINK_ID
fi
if has_parameter cfg80211_ch_switch_started_notify punct_bitmap; then
    printf '%s ' -DAIC_CFG80211_CH_SWITCH_STARTED_PUNCT
fi
if has_parameter cfg80211_cac_event link_id; then
    printf '%s ' -DAIC_CFG80211_CAC_LINK_ID
fi
