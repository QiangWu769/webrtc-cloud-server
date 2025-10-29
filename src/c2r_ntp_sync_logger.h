/*
 * C2R NTP同步日志记录器
 * 提供NTP同步时间戳和单调时钟的混合日志记录
 */

#ifndef C2R_NTP_SYNC_LOGGER_H_
#define C2R_NTP_SYNC_LOGGER_H_

#include <cstdint>
#include <string>
#include "system_wrappers/include/clock.h"
#include "system_wrappers/include/ntp_time.h"
#include "rtc_base/time_utils.h"

namespace webrtc {

class C2RNtpSyncLogger {
 public:
  // 时间戳记录结构
  struct TimestampPair {
    int64_t mono_us;      // 单调时钟 (微秒)
    int64_t ntp_us;       // NTP时间 (微秒，自1900年)
    int64_t utc_us;       // UTC时间 (微秒，自1970年)
    bool ntp_valid;       // NTP时间是否有效
  };

  static C2RNtpSyncLogger& GetInstance();

  // 获取当前时间戳对
  TimestampPair GetCurrentTimestamps();

  // 格式化时间戳字符串用于日志
  std::string FormatTimestamps(const TimestampPair& ts);

  // 检查NTP同步质量
  bool IsNtpSyncGood() const;

  // 获取时钟偏移信息
  int64_t GetClockOffsetUs() const;

 private:
  C2RNtpSyncLogger();
  ~C2RNtpSyncLogger() = default;
  
  // 禁止拷贝
  C2RNtpSyncLogger(const C2RNtpSyncLogger&) = delete;
  C2RNtpSyncLogger& operator=(const C2RNtpSyncLogger&) = delete;

  Clock* real_time_clock_;
  mutable int64_t last_clock_offset_us_;
  mutable bool ntp_sync_verified_;
};

// 便利宏定义
#define C2R_LOG_WITH_NTP_SYNC(level, message) \
  do { \
    auto ts = C2RNtpSyncLogger::GetInstance().GetCurrentTimestamps(); \
    RTC_LOG(level) << "[C2R-NTP-SYNC] " << message \
                   << " " << C2RNtpSyncLogger::GetInstance().FormatTimestamps(ts); \
  } while (0)

}  // namespace webrtc

#endif  // C2R_NTP_SYNC_LOGGER_H_