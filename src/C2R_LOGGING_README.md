# C2R (Capture-to-Render) 延迟测量日志系统

## 概述

C2R日志系统用于测量端到端延迟，从视频采集到渲染/解码的完整链路时间分析。

## 自动启用

C2R日志系统**默认启用**，无需设置任何环境变量：

```bash
# C2R日志自动启用
./peerconnection_client
```

### 日志输出格式

所有C2R日志统一使用以下格式：
- **时间单位**: 微秒 (Us)
- **标签前缀**: [C2R-*]
- **字段分隔**: 逗号+空格

## 日志类型

### 1. RTCP SR锚点日志 - `[C2R-SR-RX]`

**位置**: `rtcp_receiver.cc::HandleSenderReport`  
**触发**: 每次接收到RTCP Sender Report  
**用途**: 建立发送端NTP时间与接收端单调时钟的映射关系

**格式**:
```
[C2R-SR-RX] MonoUs=<接收端单调时钟微秒>, SrNtpUs=<发送端NTP时间微秒>, RtpTs=<RTP时间戳>, Ssrc=<发送端SSRC>
```

**示例**:
```
[C2R-SR-RX] MonoUs=3981755395862, SrNtpUs=3970654360766809, RtpTs=68987133, Ssrc=3354634246
```

### 2. 解码完成日志 - `[C2R-DECODE]`

**位置**: `video_stream_decoder2.cc::OnFrameToRender`  
**触发**: 每帧解码完成（云端headless模式）  
**用途**: 记录帧解码完成的接收端时间

**格式**:
```
[C2R-DECODE] MonoUs=<解码完成时间微秒>, FrameId=<帧ID>, RtpTs=<RTP时间戳>, Ssrc=<发送端SSRC>
```

**示例**:
```
[C2R-DECODE] MonoUs=3981755518044, FrameId=0, RtpTs=68987403, Ssrc=3354634246
```

### 3. ACT帧元数据日志 - `[C2R-FRAME-META]` (强化版)

**位置**: `rtp_video_stream_receiver2.cc::OnAssembledFrame`  
**触发**: 完整帧组装完成且包含Absolute Capture Time扩展时  
**用途**: 稳健获取发送端采集时间戳（完整帧组装后读取）

**格式**:
```
[C2R-FRAME-META] MonoUs=<帧组装完成时间微秒>, FrameId=<帧ID>, RtpTs=<RTP时间戳>, CaptureNtpUs=<采集NTP时间微秒>, Ssrc=<发送端SSRC>
```

**示例**:
```
[C2R-FRAME-META] MonoUs=3981755518000, FrameId=12345, RtpTs=68987403, CaptureNtpUs=3970654360000000, Ssrc=3354634246
```

**强化改进**:
- ✅ 在完整帧组装后记录，避免包级别的不稳定性
- ✅ 时间戳为帧组装完成时间，更接近解码时间点
- ✅ 通过`frame->NtpTimeMs()`获取ACT信息，更可靠
- ✅ 多流兼容性预留（Layer字段可选）

## 延迟计算方法

### 方法1: 使用ACT扩展（推荐，精度<10ms）
```
C2R延迟 = DECODE_MonoUs - FRAME_META_CaptureNtpUs（需要时钟同步）
```

### 方法2: 使用RTCP SR映射（备选，精度±500ms）
```
1. 建立线性映射: RTP_timestamp → NTP_time (基于多个SR样本)
2. 推算帧发送时间: Send_NTP = f(DECODE_RtpTs)  
3. 计算延迟: C2R延迟 = DECODE_MonoUs - Send_NTP（需要时钟基准）
```

## 性能影响

- **开销**: 仅在启用时进行时间戳获取和字符串格式化
- **频率**: 
  - SR日志: ~1次/秒
  - DECODE日志: ~30次/秒 (视频帧率)
  - FRAME-META日志: ~30次/秒 (仅当ACT可用时)

## 使用建议

1. **自动记录**: C2R日志自动记录，无需配置
2. **日志分析**: 配合离线分析工具处理日志数据  
3. **ACT扩展**: 建议发送端启用以获得最佳精度
4. **性能友好**: 日志开销极小，适合持续监控

## 注意事项

- 所有时间戳为微秒精度
- SSRC用于多流场景的流隔离
- 需要发送端配合才能实现完整的端到端测量
- 时钟同步是计算绝对延迟的关键