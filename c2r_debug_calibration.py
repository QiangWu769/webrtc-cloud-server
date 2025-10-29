#!/usr/bin/env python3
"""
简化版时钟校准分析器 - 调试版本
专注于展示核心概念，增加详细的调试信息
"""

import re
import sys
import statistics

def parse_logs_simple(log_file: str):
    """简化的日志解析"""
    sr_events = []
    frame_metas = []
    decodes = []
    
    patterns = {
        'sr_rx': r'\[C2R-SR-RX\] MonoUs=(\d+), SrNtpUs=(\d+), RtpTs=(\d+), Ssrc=(\d+)',
        'frame_meta': r'\[C2R-FRAME-META\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), CaptureNtpUs=(\d+), Ssrc=(\d+)',
        'decode': r'\[C2R-DECODE\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), Ssrc=(\d+)'
    }
    
    with open(log_file, 'r') as f:
        for line in f:
            # SR事件
            match = re.search(patterns['sr_rx'], line)
            if match:
                sr_events.append({
                    'rx_mono_us': int(match.group(1)),
                    'send_ntp_us': int(match.group(2)),
                    'send_rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
            
            # Frame Meta事件
            match = re.search(patterns['frame_meta'], line)
            if match:
                frame_metas.append({
                    'assembly_mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5))
                })
            
            # Decode事件
            match = re.search(patterns['decode'], line)
            if match:
                decodes.append({
                    'decode_mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
    
    return sr_events, frame_metas, decodes

def simple_clock_calibration(sr_events):
    """简化的时钟校准"""
    if len(sr_events) < 5:
        return None
    
    # 使用最近30个SR事件
    recent_srs = sorted(sr_events, key=lambda x: x['rx_mono_us'])[-30:]
    
    # 简单的线性回归计算
    n = len(recent_srs)
    sum_x = sum(sr['send_ntp_us'] for sr in recent_srs)
    sum_y = sum(sr['rx_mono_us'] for sr in recent_srs)
    sum_xy = sum(sr['send_ntp_us'] * sr['rx_mono_us'] for sr in recent_srs)
    sum_x2 = sum(sr['send_ntp_us'] ** 2 for sr in recent_srs)
    
    # 计算斜率和截距
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
    intercept = (sum_y - slope * sum_x) / n
    
    # 计算相关系数
    mean_x = sum_x / n
    mean_y = sum_y / n
    
    numerator = sum((sr['send_ntp_us'] - mean_x) * (sr['rx_mono_us'] - mean_y) for sr in recent_srs)
    denom_x = sum((sr['send_ntp_us'] - mean_x) ** 2 for sr in recent_srs)
    denom_y = sum((sr['rx_mono_us'] - mean_y) ** 2 for sr in recent_srs)
    
    if denom_x * denom_y > 0:
        correlation = numerator / (denom_x * denom_y) ** 0.5
        r_squared = correlation ** 2
    else:
        r_squared = 0
    
    return {
        'slope': slope,
        'intercept': intercept,
        'r_squared': r_squared,
        'sample_count': n
    }

def analyze_with_debug(sr_events, frame_metas, decodes):
    """带调试信息的分析"""
    print("🔧 时钟校准分析 (调试版)")
    
    # 执行校准
    calib = simple_clock_calibration(sr_events)
    if not calib:
        print("   ❌ 校准失败: SR事件不足")
        return
    
    print(f"   📊 校准结果:")
    print(f"     - 样本数: {calib['sample_count']}")
    print(f"     - R²: {calib['r_squared']:.6f}")
    print(f"     - 斜率: {calib['slope']:.6f}")
    print(f"     - 截距: {calib['intercept']:.0f}")
    
    # 尝试匹配帧和解码事件
    print(f"\n🎯 帧匹配分析")
    print(f"   - Frame Meta事件: {len(frame_metas)}")
    print(f"   - Decode事件: {len(decodes)}")
    
    matched_pairs = []
    
    # 按SSRC分组
    ssrc_groups = {}
    for meta in frame_metas:
        ssrc = meta['ssrc']
        if ssrc not in ssrc_groups:
            ssrc_groups[ssrc] = {'metas': [], 'decodes': []}
        ssrc_groups[ssrc]['metas'].append(meta)
    
    for decode in decodes:
        ssrc = decode['ssrc']
        if ssrc not in ssrc_groups:
            ssrc_groups[ssrc] = {'metas': [], 'decodes': []}
        ssrc_groups[ssrc]['decodes'].append(decode)
    
    print(f"   - SSRC组数: {len(ssrc_groups)}")
    
    for ssrc, data in ssrc_groups.items():
        print(f"\n   📡 SSRC {ssrc}:")
        print(f"     - Meta事件: {len(data['metas'])}")
        print(f"     - Decode事件: {len(data['decodes'])}")
        
        # 尝试匹配
        for meta in data['metas'][-10:]:  # 最近10个
            # 寻找最匹配的decode事件
            best_decode = None
            min_rtp_diff = float('inf')
            
            for decode in data['decodes']:
                rtp_diff = abs(decode['rtp_ts'] - meta['rtp_ts'])
                if rtp_diff < min_rtp_diff:
                    min_rtp_diff = rtp_diff
                    best_decode = decode
            
            if best_decode and min_rtp_diff < 90000:  # RTP差值小于1秒
                # 计算延迟
                def convert_ntp_to_mono(send_ntp_us):
                    return int(calib['slope'] * send_ntp_us + calib['intercept'])
                
                estimated_capture_mono = convert_ntp_to_mono(meta['capture_ntp_us'])
                
                # 端到端延迟
                e2e_latency_us = meta['assembly_mono_us'] - estimated_capture_mono
                
                # 处理延迟
                processing_latency_us = best_decode['decode_mono_us'] - meta['assembly_mono_us']
                
                print(f"     Frame {meta['frame_id']:4d}: "
                      f"E2E={e2e_latency_us/1000:8.1f}ms, "
                      f"Proc={processing_latency_us/1000:6.1f}ms, "
                      f"RTP_diff={min_rtp_diff}")
                
                # 记录有效的延迟数据
                if -1000000 < e2e_latency_us < 10000000:  # 合理范围
                    matched_pairs.append({
                        'e2e_latency_ms': e2e_latency_us / 1000,
                        'processing_latency_ms': processing_latency_us / 1000
                    })
    
    # 延迟统计
    if matched_pairs:
        print(f"\n📊 延迟统计 ({len(matched_pairs)}个有效样本):")
        
        e2e_delays = [p['e2e_latency_ms'] for p in matched_pairs]
        proc_delays = [p['processing_latency_ms'] for p in matched_pairs]
        
        print(f"   端到端延迟:")
        print(f"     - 平均: {statistics.mean(e2e_delays):.1f}ms")
        print(f"     - 范围: {min(e2e_delays):.1f}ms ~ {max(e2e_delays):.1f}ms")
        if len(e2e_delays) > 1:
            print(f"     - 标准差: {statistics.stdev(e2e_delays):.1f}ms")
        
        print(f"   处理延迟:")
        print(f"     - 平均: {statistics.mean(proc_delays):.1f}ms")
        print(f"     - 范围: {min(proc_delays):.1f}ms ~ {max(proc_delays):.1f}ms")
        
        net_delays = [e2e - proc for e2e, proc in zip(e2e_delays, proc_delays)]
        print(f"   网络延迟 (估算):")
        print(f"     - 平均: {statistics.mean(net_delays):.1f}ms")
        
    else:
        print(f"\n❌ 没有找到有效的延迟数据")
        print(f"   可能原因:")
        print(f"   - 时钟校准质量不佳 (R²={calib['r_squared']:.3f})")
        print(f"   - RTP时间戳不匹配")
        print(f"   - 延迟超出合理范围")

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_debug_calibration.py <receiver_log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        sr_events, frame_metas, decodes = parse_logs_simple(log_file)
        
        print("=" * 70)
        print("🎯 C2R时钟校准调试分析")
        print("=" * 70)
        
        print(f"\n📊 原始数据:")
        print(f"  - SR锚点: {len(sr_events)}")
        print(f"  - Frame Meta: {len(frame_metas)}")
        print(f"  - Decode事件: {len(decodes)}")
        
        analyze_with_debug(sr_events, frame_metas, decodes)
        
        print("\n💡 时钟校准原理:")
        print("  1. RTCP SR提供: 发送端NTP时间 → 接收端时间的映射点")
        print("  2. 线性回归建立: rx_mono = α * send_ntp + β")
        print("  3. ACT扩展提供: 帧的精确采集时间(发送端NTP)")
        print("  4. 计算延迟: 接收时间 - 校准后的采集时间")
        
        print("=" * 70)
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()