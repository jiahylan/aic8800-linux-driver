/**
 ******************************************************************************
 *
 * @file rwnx_main.h
 *
 * Copyright (C) RivieraWaves 2012-2019
 *
 ******************************************************************************
 */

#ifndef _RWNX_MAIN_H_
#define _RWNX_MAIN_H_

#include "rwnx_defs.h"

int rwnx_cfg80211_init(struct rwnx_plat *rwnx_plat, void **platform_data);
void rwnx_cfg80211_deinit(struct rwnx_hw *rwnx_hw);
extern int testmode;
extern u8 chip_id;
extern u8 chip_sub_id;
extern u8 chip_mcu_id;

void rwnx_skb_align_8bytes(struct sk_buff *skb);
void rwnx_frame_parser(char* tag, char* data, unsigned long len);
int rwnx_cfg80211_set_monitor_channel_(struct wiphy *wiphy,
                                       struct cfg80211_chan_def *chandef);
int aicwf_vendor_init(struct wiphy *wiphy);

#define CHIP_ID_H_MASK  0xC0
#define IS_CHIP_ID_H()  ((chip_id & CHIP_ID_H_MASK) == CHIP_ID_H_MASK)

#endif /* _RWNX_MAIN_H_ */
