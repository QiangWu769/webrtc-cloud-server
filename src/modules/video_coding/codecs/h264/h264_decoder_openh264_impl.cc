/*
 *  Copyright (c) 2025 WebRTC project authors. All Rights Reserved.
 */

#ifdef WEBRTC_USE_H264

#include "modules/video_coding/codecs/h264/h264_decoder_openh264_impl.h"

#include <algorithm>
#include <cstring>
#include <memory>

#include "api/scoped_refptr.h"
#include "api/video/i420_buffer.h"
#include "api/video/video_frame.h"
#include "api/video/video_frame_buffer.h"
#include "api/video/video_rotation.h"
#include "common_video/include/video_frame_buffer.h"
#include "modules/video_coding/codecs/h264/include/h264_globals.h"
#include "modules/video_coding/include/video_error_codes.h"
#include "rtc_base/checks.h"
#include "rtc_base/logging.h"
#include "system_wrappers/include/metrics.h"
#include "third_party/openh264/src/codec/api/wels/codec_api.h"
#include "third_party/openh264/src/codec/api/wels/codec_app_def.h"
#include "third_party/openh264/src/codec/api/wels/codec_def.h"
#include "third_party/openh264/src/codec/api/wels/codec_ver.h"

namespace webrtc {

namespace {

enum H264DecoderOpenH264Event {
  kH264DecoderOpenH264EventInit = 0,
  kH264DecoderOpenH264EventError = 1,
  kH264DecoderOpenH264EventMax = 16,
};

}  // namespace

H264DecoderOpenH264Impl::H264DecoderOpenH264Impl()
    : decoder_(nullptr),
      decode_complete_callback_(nullptr),
      buffer_pool_(false, 300),
      has_reported_init_(false),
      has_reported_error_(false),
      initialized_(false) {
  RTC_LOG(LS_INFO) << "Creating H264DecoderOpenH264Impl.";
}

H264DecoderOpenH264Impl::~H264DecoderOpenH264Impl() {
  Release();
}

bool H264DecoderOpenH264Impl::Configure(const Settings& settings) {
  ReportInit();

  if (settings.codec_type() != kVideoCodecH264) {
    ReportError();
    return false;
  }

  if (decoder_) {
    Release();
  }

  if (WelsCreateDecoder(&decoder_) != 0 || decoder_ == nullptr) {
    RTC_LOG(LS_ERROR) << "Failed to create OpenH264 decoder";
    ReportError();
    return false;
  }

  SDecodingParam dec_param;
  memset(&dec_param, 0, sizeof(SDecodingParam));
  dec_param.sVideoProperty.eVideoBsType = VIDEO_BITSTREAM_DEFAULT;
  dec_param.bParseOnly = false;
  dec_param.uiTargetDqLayer = UCHAR_MAX;
  dec_param.eEcActiveIdc = ERROR_CON_SLICE_COPY;

  long ret = decoder_->Initialize(&dec_param);
  if (ret != cmResultSuccess) {
    RTC_LOG(LS_ERROR) << "Failed to initialize OpenH264 decoder, ret=" << ret;
    WelsDestroyDecoder(decoder_);
    decoder_ = nullptr;
    ReportError();
    return false;
  }

  int log_level = WELS_LOG_WARNING;
  decoder_->SetOption(DECODER_OPTION_TRACE_LEVEL, &log_level);

  RTC_LOG(LS_INFO) << "OpenH264 decoder initialized successfully. Version: "
                   << OPENH264_MAJOR << "." << OPENH264_MINOR << "."
                   << OPENH264_REVISION;

  initialized_ = true;
  return true;
}

int32_t H264DecoderOpenH264Impl::Release() {
  if (decoder_) {
    decoder_->Uninitialize();
    WelsDestroyDecoder(decoder_);
    decoder_ = nullptr;
  }
  initialized_ = false;
  return WEBRTC_VIDEO_CODEC_OK;
}

int32_t H264DecoderOpenH264Impl::RegisterDecodeCompleteCallback(
    DecodedImageCallback* callback) {
  decode_complete_callback_ = callback;
  return WEBRTC_VIDEO_CODEC_OK;
}

int32_t H264DecoderOpenH264Impl::Decode(const EncodedImage& input_image,
                                         bool missing_frames,
                                         int64_t render_time_ms) {
  if (!IsInitialized()) {
    RTC_LOG(LS_ERROR) << "Decoder not initialized";
    ReportError();
    return WEBRTC_VIDEO_CODEC_UNINITIALIZED;
  }

  if (!decode_complete_callback_) {
    RTC_LOG(LS_WARNING) << "Decode callback not set";
    ReportError();
    return WEBRTC_VIDEO_CODEC_UNINITIALIZED;
  }

  if (!input_image.data() || input_image.size() == 0) {
    RTC_LOG(LS_ERROR) << "Invalid input image";
    ReportError();
    return WEBRTC_VIDEO_CODEC_ERR_PARAMETER;
  }

  uint8_t* pData[3] = {nullptr};
  SBufferInfo sDstBufInfo;
  memset(&sDstBufInfo, 0, sizeof(SBufferInfo));

  DECODING_STATE ret = decoder_->DecodeFrame2(
      input_image.data(),
      static_cast<int>(input_image.size()),
      pData,
      &sDstBufInfo);

  if (ret != dsErrorFree) {
    RTC_LOG(LS_ERROR) << "OpenH264 DecodeFrame2 failed, ret=" << ret;
    ReportError();
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  if (sDstBufInfo.iBufferStatus != 1) {
    return WEBRTC_VIDEO_CODEC_OK;
  }

  int width = sDstBufInfo.UsrData.sSystemBuffer.iWidth;
  int height = sDstBufInfo.UsrData.sSystemBuffer.iHeight;

  if (width <= 0 || height <= 0) {
    RTC_LOG(LS_ERROR) << "Invalid decoded frame dimensions: "
                      << width << "x" << height;
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  scoped_refptr<I420Buffer> buffer =
      buffer_pool_.CreateI420Buffer(width, height);
  if (!buffer) {
    RTC_LOG(LS_ERROR) << "Failed to allocate I420 buffer";
    return WEBRTC_VIDEO_CODEC_ERROR;
  }

  int stride_y = sDstBufInfo.UsrData.sSystemBuffer.iStride[0];
  int stride_u = sDstBufInfo.UsrData.sSystemBuffer.iStride[1];
  int stride_v = stride_u;

  const uint8_t* src_y = pData[0];
  uint8_t* dst_y = buffer->MutableDataY();
  for (int row = 0; row < height; ++row) {
    memcpy(dst_y, src_y, width);
    src_y += stride_y;
    dst_y += buffer->StrideY();
  }

  const uint8_t* src_u = pData[1];
  uint8_t* dst_u = buffer->MutableDataU();
  int chroma_width = (width + 1) / 2;
  int chroma_height = (height + 1) / 2;
  for (int row = 0; row < chroma_height; ++row) {
    memcpy(dst_u, src_u, chroma_width);
    src_u += stride_u;
    dst_u += buffer->StrideU();
  }

  const uint8_t* src_v = pData[2];
  uint8_t* dst_v = buffer->MutableDataV();
  for (int row = 0; row < chroma_height; ++row) {
    memcpy(dst_v, src_v, chroma_width);
    src_v += stride_v;
    dst_v += buffer->StrideV();
  }

  h264_bitstream_parser_.ParseBitstream(input_image);
  std::optional<int> qp = h264_bitstream_parser_.GetLastSliceQp();

  VideoFrame decoded_frame =
      VideoFrame::Builder()
          .set_video_frame_buffer(buffer)
          .set_timestamp_rtp(input_image.RtpTimestamp())
          .set_rotation(kVideoRotation_0)
          .build();

  decode_complete_callback_->Decoded(decoded_frame, std::nullopt, qp);

  return WEBRTC_VIDEO_CODEC_OK;
}

const char* H264DecoderOpenH264Impl::ImplementationName() const {
  return "OpenH264";
}

bool H264DecoderOpenH264Impl::IsInitialized() const {
  return initialized_ && decoder_ != nullptr;
}

void H264DecoderOpenH264Impl::ReportInit() {
  if (has_reported_init_)
    return;
  RTC_HISTOGRAM_ENUMERATION("WebRTC.Video.H264DecoderOpenH264.Event",
                            kH264DecoderOpenH264EventInit,
                            kH264DecoderOpenH264EventMax);
  has_reported_init_ = true;
}

void H264DecoderOpenH264Impl::ReportError() {
  if (has_reported_error_)
    return;
  RTC_HISTOGRAM_ENUMERATION("WebRTC.Video.H264DecoderOpenH264.Event",
                            kH264DecoderOpenH264EventError,
                            kH264DecoderOpenH264EventMax);
  has_reported_error_ = true;
}

}  // namespace webrtc

#endif  // WEBRTC_USE_H264
