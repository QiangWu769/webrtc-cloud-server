/*
 *  Copyright (c) 2025 WebRTC project authors. All Rights Reserved.
 *
 *  OpenH264 Decoder Implementation for WebRTC
 */

#ifndef MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_
#define MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_

#ifdef WEBRTC_USE_H264

#include <memory>
#include <vector>

#include "api/video/encoded_image.h"
#include "api/video_codecs/video_decoder.h"
#include "common_video/h264/h264_bitstream_parser.h"
#include "common_video/include/video_frame_buffer_pool.h"
#include "modules/video_coding/codecs/h264/include/h264.h"

class ISVCDecoder;

namespace webrtc {

class H264DecoderOpenH264Impl : public H264Decoder {
 public:
  H264DecoderOpenH264Impl();
  ~H264DecoderOpenH264Impl() override;

  bool Configure(const Settings& settings) override;
  int32_t Release() override;

  int32_t RegisterDecodeCompleteCallback(
      DecodedImageCallback* callback) override;

  int32_t Decode(const EncodedImage& input_image,
                 bool missing_frames,
                 int64_t render_time_ms = -1) override;

  const char* ImplementationName() const override;

 private:
  ISVCDecoder* decoder_;
  DecodedImageCallback* decode_complete_callback_;
  VideoFrameBufferPool buffer_pool_;
  H264BitstreamParser h264_bitstream_parser_;
  bool has_reported_init_;
  bool has_reported_error_;
  bool initialized_;

  void ReportInit();
  void ReportError();
  bool IsInitialized() const;
};

}  // namespace webrtc

#endif  // WEBRTC_USE_H264

#endif  // MODULES_VIDEO_CODING_CODECS_H264_H264_DECODER_OPENH264_IMPL_H_
