#!/usr/bin/env python3
"""
手动测试时钟校准和延迟计算
"""

# 示例数据（从实际日志中提取）
frame_meta = {
    'assembly_mono_us': 3999732666974,
    'capture_ntp_us': 3970672338067000,
    'rtp_ts': 1252272753
}

decode = {
    'decode_mono_us': 3999734619747,
    'rtp_ts': 1252116783  # 不匹配的RTP时间戳
}

# 时钟校准参数（从前面的分析结果）
calibration = {
    'slope': 0.787287,
    'intercept': -3122057655817626
}

def convert_ntp_to_mono(send_ntp_us):
    """将发送端NTP时间转换为接收端单调时钟时间"""
    return calibration['slope'] * send_ntp_us + calibration['intercept']

def main():
    print("🎯 手动延迟计算测试")
    print("=" * 50)
    
    print(f"📊 输入数据:")
    print(f"  Frame Meta:")
    print(f"    - 组装时间: {frame_meta['assembly_mono_us']:,} us")
    print(f"    - 采集时间: {frame_meta['capture_ntp_us']:,} us (NTP)")
    print(f"    - RTP时间戳: {frame_meta['rtp_ts']}")
    
    print(f"\n🔧 时钟校准:")
    print(f"  rx_mono = {calibration['slope']:.6f} * send_ntp + {calibration['intercept']:,.0f}")
    
    # 转换采集时间到接收端时钟域
    estimated_capture_mono = convert_ntp_to_mono(frame_meta['capture_ntp_us'])
    print(f"\n🔄 时钟域转换:")
    print(f"  采集时间 (NTP域): {frame_meta['capture_ntp_us']:,} us")
    print(f"  采集时间 (Mono域): {estimated_capture_mono:,.0f} us")
    
    # 计算端到端延迟
    e2e_latency_us = frame_meta['assembly_mono_us'] - estimated_capture_mono
    e2e_latency_ms = e2e_latency_us / 1000
    
    print(f"\n📈 延迟计算:")
    print(f"  端到端延迟: {e2e_latency_us:,} us = {e2e_latency_ms:.1f} ms")
    
    # 验证合理性
    if -1000 < e2e_latency_ms < 10000:
        print(f"  ✅ 延迟在合理范围内")
    else:
        print(f"  ❌ 延迟超出合理范围 (-1s ~ 10s)")
        
        # 分析可能的问题
        print(f"\n🔍 问题分析:")
        
        # 时钟域差异
        ntp_vs_mono_ratio = frame_meta['assembly_mono_us'] / frame_meta['capture_ntp_us']
        print(f"  时钟域比率: {ntp_vs_mono_ratio:.6f}")
        
        # 时间尺度
        print(f"  NTP时间: {frame_meta['capture_ntp_us'] / 1e9:.1f} 千秒")
        print(f"  Mono时间: {frame_meta['assembly_mono_us'] / 1e9:.1f} 千秒")
        
        if abs(ntp_vs_mono_ratio - 1.0) > 0.1:
            print(f"  ⚠️  时钟域存在显著差异")
    
    print(f"\n💡 结论:")
    if -100 < e2e_latency_ms < 1000:
        print(f"  🎯 成功计算出端到端延迟: {e2e_latency_ms:.1f}ms")
        print(f"  📊 方法2 (基于ACT的相对时钟校准) 工作正常！")
    else:
        print(f"  🔧 需要进一步调试时钟校准参数")
        print(f"  💭 可能需要更多的SR锚点或更长的时间窗口")

if __name__ == "__main__":
    main()