/*
 *  Copyright (c) 2012 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree. An additional intellectual property rights grant can be found
 *  in the file PATENTS.  All contributing project authors may
 *  be found in the AUTHORS file in the root of the source tree.
 */

#include "video/video_stream_decoder2.h"

#include <cstdint>
#include <optional>

#include "api/units/time_delta.h"
#include "api/video/video_frame.h"
#include "api/video/video_sink_interface.h"
#include "api/video_codecs/video_decoder.h"
#include "modules/video_coding/video_receiver2.h"
#include "rtc_base/checks.h"
#include "rtc_base/logging.h"
#include "rtc_base/time_utils.h"
#include "video/receive_statistics_proxy.h"
#include "video/ntp_time_converter.h"
#include "../c2r_log_util.h"

namespace webrtc {
namespace internal {

VideoStreamDecoder::VideoStreamDecoder(
    VideoReceiver2* video_receiver,
    ReceiveStatisticsProxy* receive_statistics_proxy,
    VideoSinkInterface<VideoFrame>* incoming_video_stream)
    : video_receiver_(video_receiver),
      receive_stats_callback_(receive_statistics_proxy),
      incoming_video_stream_(incoming_video_stream) {
  RTC_DCHECK(video_receiver_);

  ntp_converter_.Initialize();
  video_receiver_->RegisterReceiveCallback(this);
}

VideoStreamDecoder::~VideoStreamDecoder() {
  // Note: There's an assumption at this point that the decoder thread is
  // *not* running. If it was, then there could be a race for each of these
  // callbacks.

  // Unset all the callback pointers that we set in the ctor.
  video_receiver_->RegisterReceiveCallback(nullptr);
}

// Do not acquire the lock of `video_receiver_` in this function. Decode
// callback won't necessarily be called from the decoding thread. The decoding
// thread may have held the lock when calling VideoDecoder::Decode, Reset, or
// Release. Acquiring the same lock in the path of decode callback can deadlock.
int32_t VideoStreamDecoder::OnFrameToRender(const FrameToRender& arguments) {
  // C2R解码完成日志 (云端headless模式) - 运行时控制
  if (C2RLogUtil::IsC2RLogEnabled()) {
    int64_t decode_mono_us = webrtc::TimeMicros();
    int64_t decode_ntp_us = ntp_converter_.MonotonicToNtpMicros(decode_mono_us);
    uint16_t frame_id = arguments.video_frame.id();
    uint32_t rtp_ts = arguments.video_frame.rtp_timestamp();
    uint32_t ssrc = receive_stats_callback_->GetRemoteSsrc();
    
    // C2R统一日志格式：解码完成和E2E延迟
    RTC_LOG(LS_INFO) << "[C2R-DECODE] MonoUs=" << decode_mono_us 
                     << ", NtpUs=" << decode_ntp_us
                     << ", FrameId=" << frame_id
                     << ", RtpTs=" << rtp_ts
                     << ", Ssrc=" << ssrc;
    
    // 尝试计算E2E延迟（如果帧包含NTP时间戳）
    if (arguments.video_frame.ntp_time_ms() > 0) {
      uint64_t capture_us = static_cast<uint64_t>(arguments.video_frame.ntp_time_ms() * 1000);
      int64_t e2e_delay_us = decode_ntp_us - static_cast<int64_t>(capture_us);
      double e2e_delay_ms = e2e_delay_us / 1000.0;
      
      RTC_LOG(LS_INFO) << "[C2R-E2E-DECODED] RtpTs=" << rtp_ts
                       << ", Ssrc=" << ssrc
                       << ", DelayMs=" << e2e_delay_ms
                       << ", CaptureUs=" << capture_us
                       << ", DECODEDNtpUs=" << decode_ntp_us;
    }
  }
  
  receive_stats_callback_->OnDecodedFrame(
      arguments.video_frame, arguments.qp, arguments.decode_time,
      arguments.content_type, arguments.frame_type);
  incoming_video_stream_->OnFrame(arguments.video_frame);
  return 0;
}

void VideoStreamDecoder::OnDroppedFrames(uint32_t frames_dropped) {
  receive_stats_callback_->OnDroppedFrames(frames_dropped);
}

void VideoStreamDecoder::OnIncomingPayloadType(int payload_type) {
  receive_stats_callback_->OnIncomingPayloadType(payload_type);
}

void VideoStreamDecoder::OnDecoderInfoChanged(
    const VideoDecoder::DecoderInfo& decoder_info) {
  receive_stats_callback_->OnDecoderInfo(decoder_info);
}

}  // namespace internal
}  // namespace webrtc
