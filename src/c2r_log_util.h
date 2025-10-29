/*
 *  Copyright (c) 2024 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#ifndef C2R_LOG_UTIL_H_
#define C2R_LOG_UTIL_H_

#include <cstdlib>
#include "rtc_base/logging.h"

namespace webrtc {

// C2R logging utility class for Capture-to-Render latency measurement
class C2RLogUtil {
public:
  // C2R logging is always enabled for latency measurement
  static bool IsC2RLogEnabled() {
    return true;  // Always enabled
  }

  // Unified C2R logging macro
  #define C2R_LOG(tag, ...) \
    do { \
      if (webrtc::C2RLogUtil::IsC2RLogEnabled()) { \
        RTC_LOG(LS_INFO) << "[C2R-" << tag << "] " << __VA_ARGS__; \
      } \
    } while(0)
};

} // namespace webrtc

#endif  // C2R_LOG_UTIL_H_