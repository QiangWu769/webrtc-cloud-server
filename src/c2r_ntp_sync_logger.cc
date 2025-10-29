/*
 * C2R NTP同步日志记录器实现
 */

#include "c2r_ntp_sync_logger.h"
#include "rtc_base/logging.h"
#include <cmath>
#include <sstream>
#include <iomanip>

namespace webrtc {

C2RNtpSyncLogger& C2RNtpSyncLogger::GetInstance() {
  static C2RNtpSyncLogger instance;
  return instance;
}

C2RNtpSyncLogger::C2RNtpSyncLogger() 
    : real_time_clock_(Clock::GetRealTimeClock()),
      last_clock_offset_us_(0),
      ntp_sync_verified_(false) {
}

C2RNtpSyncLogger::TimestampPair C2RNtpSyncLogger::GetCurrentTimestamps() {
  TimestampPair ts;
  
  // 获取单调时钟时间
  ts.mono_us = webrtc::TimeMicros();
  
  // 获取NTP时间
  try {
    NtpTime ntp_time = real_time_clock_->CurrentNtpTime();
    if (ntp_time.Valid()) {
      // 转换NTP时间为微秒 (自1900年1月1日)
      ts.ntp_us = static_cast<int64_t>(ntp_time.seconds()) * 1000000LL +
                  static_cast<int64_t>((static_cast<double>(ntp_time.fractions()) * 1000000.0) / 
                                      NtpTime::kFractionsPerSecond);
      
      // 转换为UTC时间 (自1970年1月1日)
      Timestamp utc_timestamp = Clock::NtpToUtc(ntp_time);
      if (utc_timestamp.IsFinite()) {
        ts.utc_us = utc_timestamp.us();
        ts.ntp_valid = true;
      } else {
        ts.utc_us = 0;
        ts.ntp_valid = false;
      }
    } else {
      ts.ntp_us = 0;
      ts.utc_us = 0;
      ts.ntp_valid = false;
    }
  } catch (...) {
    ts.ntp_us = 0;
    ts.utc_us = 0;
    ts.ntp_valid = false;
  }
  
  return ts;
}

std::string C2RNtpSyncLogger::FormatTimestamps(const TimestampPair& ts) {
  std::ostringstream oss;
  oss << "MonoUs=" << ts.mono_us;
  
  if (ts.ntp_valid) {
    oss << ", NtpUs=" << ts.ntp_us
        << ", UtcUs=" << ts.utc_us;
    
    // 计算时钟域差异
    int64_t ntp_to_mono_offset = ts.mono_us - (ts.ntp_us % 1000000000000LL); // 取NTP的低位部分
    oss << ", ClockOffsetUs=" << ntp_to_mono_offset;
  } else {
    oss << ", NtpUs=INVALID, UtcUs=INVALID";
  }
  
  return oss.str();
}

bool C2RNtpSyncLogger::IsNtpSyncGood() const {
  TimestampPair ts = const_cast<C2RNtpSyncLogger*>(this)->GetCurrentTimestamps();
  
  if (!ts.ntp_valid) {
    return false;
  }
  
  // 检查时钟是否合理 (NTP应该比单调时钟大很多)
  int64_t expected_ntp_magnitude = 3900000000LL * 1000000LL; // 约2025年的NTP时间
  if (ts.ntp_us < expected_ntp_magnitude) {
    return false;
  }
  
  return true;
}

int64_t C2RNtpSyncLogger::GetClockOffsetUs() const {
  TimestampPair ts = const_cast<C2RNtpSyncLogger*>(this)->GetCurrentTimestamps();
  
  if (!ts.ntp_valid) {
    return 0;
  }
  
  // 计算时钟域偏移 (这里需要考虑epoch差异)
  // NTP epoch (1900) vs Unix epoch (1970) = 70年 = 2208988800秒
  constexpr int64_t EPOCH_DIFF_US = 2208988800LL * 1000000LL;
  int64_t ntp_as_unix_us = ts.ntp_us - EPOCH_DIFF_US;
  
  last_clock_offset_us_ = ts.mono_us - ntp_as_unix_us;
  return last_clock_offset_us_;
}

}  // namespace webrtc