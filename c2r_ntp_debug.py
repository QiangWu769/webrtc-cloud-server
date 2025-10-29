#!/usr/bin/env python3
"""
调试NTP时间转换问题
"""

def analyze_ntp_conversion():
    """分析NTP时间转换"""
    
    # 原始ACT时间戳
    act_timestamp = 17053907328044306432
    
    # 转换后的CaptureNtpUs
    capture_ntp_us = 3970672338067000
    
    # 接收端单调时钟
    mono_us = 3999732666974
    
    print("🔍 NTP时间转换调试")
    print("=" * 50)
    
    print(f"📊 原始数据:")
    print(f"  ACT原始时间戳: {act_timestamp:,}")
    print(f"  转换后NTP(us): {capture_ntp_us:,}")
    print(f"  接收端Mono(us): {mono_us:,}")
    
    # 分析转换比率
    conversion_ratio = capture_ntp_us / act_timestamp
    print(f"\n🔄 转换分析:")
    print(f"  转换比率: {conversion_ratio:.10f}")
    
    # NTP时间格式分析
    # 标准NTP时间戳是64位：32位秒 + 32位小数
    ntp_seconds = act_timestamp >> 32
    ntp_fraction = act_timestamp & 0xFFFFFFFF
    
    print(f"\n📅 NTP格式解析:")
    print(f"  NTP秒部分: {ntp_seconds:,}")
    print(f"  NTP小数部分: {ntp_fraction:,}")
    
    # 转换为标准时间
    ntp_time_seconds = ntp_seconds + (ntp_fraction / (2**32))
    ntp_time_us = int(ntp_time_seconds * 1000000)
    
    print(f"  标准NTP时间: {ntp_time_seconds:.3f} 秒")
    print(f"  转换为微秒: {ntp_time_us:,} us")
    
    # 与Unix时间对比
    # NTP epoch: 1900-01-01
    # Unix epoch: 1970-01-01
    # 差值: 70年 = 2208988800秒
    UNIX_OFFSET = 2208988800
    unix_seconds = ntp_seconds - UNIX_OFFSET
    
    print(f"\n🕐 时间验证:")
    print(f"  Unix时间戳: {unix_seconds:,} 秒")
    
    if unix_seconds > 0:
        import datetime
        try:
            dt = datetime.datetime.fromtimestamp(unix_seconds)
            print(f"  对应日期: {dt}")
        except:
            print(f"  日期转换失败")
    
    # 正确的延迟计算
    correct_e2e_latency_us = mono_us - ntp_time_us
    correct_e2e_latency_ms = correct_e2e_latency_us / 1000
    
    print(f"\n📈 正确的延迟计算:")
    print(f"  端到端延迟: {correct_e2e_latency_us:,} us")
    print(f"  端到端延迟: {correct_e2e_latency_ms:.1f} ms")
    
    if -1000 < correct_e2e_latency_ms < 10000:
        print(f"  ✅ 延迟在合理范围内！")
        print(f"  🎯 实际延迟: {correct_e2e_latency_ms:.1f}ms")
    else:
        print(f"  ❌ 延迟仍然不合理")
    
    # 分析WebRTC中的NTP转换问题
    print(f"\n🔧 WebRTC NTP转换问题:")
    print(f"  可能的问题:")
    print(f"  1. NtpTime.ToMs()转换有误")
    print(f"  2. ACT扩展的时间戳格式不标准")
    print(f"  3. 需要特殊的单位转换")
    
    # 建议的修正方法
    print(f"\n💡 修正建议:")
    print(f"  方法1: 直接使用ACT原始时间戳计算")
    print(f"  方法2: 修正NtpTime转换逻辑")
    print(f"  方法3: 使用相对时间差而非绝对时间")

if __name__ == "__main__":
    analyze_ntp_conversion()