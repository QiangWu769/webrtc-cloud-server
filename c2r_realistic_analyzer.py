#!/usr/bin/env python3
"""
C2R实际可用延迟分析 - 基于单调时钟的相对延迟分析
不需要时钟同步，分析接收端内部的处理延迟和性能指标
"""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import statistics

def parse_c2r_logs(log_file: str):
    """解析C2R日志文件"""
    frame_metas = []
    decodes = []
    sr_anchors = []
    
    patterns = {
        'frame_meta': r'\[C2R-FRAME-META\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), CaptureNtpUs=(\d+), Ssrc=(\d+)',
        'decode': r'\[C2R-DECODE\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), Ssrc=(\d+)',
        'sr_rx': r'\[C2R-SR-RX\] MonoUs=(\d+), SrNtpUs=(\d+), RtpTs=(\d+), Ssrc=(\d+)'
    }
    
    with open(log_file, 'r') as f:
        for line in f:
            # Frame Meta 日志 (ACT扩展帧组装完成)
            match = re.search(patterns['frame_meta'], line)
            if match:
                frame_metas.append({
                    'mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5))
                })
            
            # Decode 日志 (解码完成)
            match = re.search(patterns['decode'], line)
            if match:
                decodes.append({
                    'mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
            
            # SR 锚点
            match = re.search(patterns['sr_rx'], line)
            if match:
                sr_anchors.append({
                    'mono_us': int(match.group(1)),
                    'sr_ntp_us': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
    
    return frame_metas, decodes, sr_anchors

def analyze_processing_delays(frame_metas: List, decodes: List) -> Dict:
    """分析接收端处理延迟 - 这是真正可测量的！"""
    print("🎯 接收端处理延迟分析")
    print("   (帧组装完成 → 解码完成的时间)")
    
    processing_delays = []
    matched_pairs = []
    
    # 为每个解码事件找到对应的帧组装事件
    for decode in decodes:
        # 找到最接近的frame_meta（相同RTP时间戳或时间最近）
        best_meta = None
        min_time_diff = float('inf')
        
        for meta in frame_metas:
            if meta['ssrc'] == decode['ssrc']:
                # 优先匹配RTP时间戳相近的
                rtp_diff = abs(meta['rtp_ts'] - decode['rtp_ts'])
                time_diff = abs(meta['mono_us'] - decode['mono_us'])
                
                if rtp_diff < 9000:  # RTP差值小于100ms@90kHz
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        best_meta = meta
        
        if best_meta and decode['mono_us'] > best_meta['mono_us']:
            # 确保解码时间在组装时间之后
            delay_us = decode['mono_us'] - best_meta['mono_us']
            if 0 < delay_us < 1000000:  # 合理范围：0-1秒
                processing_delays.append(delay_us)
                matched_pairs.append({
                    'meta': best_meta,
                    'decode': decode,
                    'delay_us': delay_us,
                    'delay_ms': delay_us / 1000
                })
    
    if processing_delays:
        print(f"   📊 处理延迟统计 ({len(processing_delays)}个样本):")
        print(f"     - 平均处理延迟: {statistics.mean(processing_delays)/1000:.1f}ms")
        print(f"     - 最小处理延迟: {min(processing_delays)/1000:.1f}ms")
        print(f"     - 最大处理延迟: {max(processing_delays)/1000:.1f}ms")
        print(f"     - 中位数延迟: {statistics.median(processing_delays)/1000:.1f}ms")
        if len(processing_delays) > 1:
            print(f"     - 标准差: {statistics.stdev(processing_delays)/1000:.1f}ms")
        
        print(f"\n   🔍 最近10帧的处理延迟:")
        for pair in matched_pairs[-10:]:
            print(f"     Frame {pair['decode']['frame_id']:4d}: {pair['delay_ms']:5.1f}ms")
        
        return {
            'delays': processing_delays,
            'pairs': matched_pairs,
            'avg_ms': statistics.mean(processing_delays) / 1000
        }
    else:
        print("   ❌ 没有找到匹配的帧组装-解码对")
        return {'delays': [], 'pairs': [], 'avg_ms': 0}

def analyze_frame_rate_consistency(decodes: List) -> Dict:
    """分析帧率一致性和时序抖动"""
    print("\n🎯 帧率一致性分析")
    print("   (基于解码事件的时间间隔)")
    
    if len(decodes) < 2:
        print("   ❌ 解码事件不足")
        return {}
    
    # 按时间排序
    sorted_decodes = sorted(decodes, key=lambda x: x['mono_us'])
    
    # 计算帧间时间间隔
    intervals_ms = []
    for i in range(1, len(sorted_decodes)):
        interval_us = sorted_decodes[i]['mono_us'] - sorted_decodes[i-1]['mono_us']
        interval_ms = interval_us / 1000
        if 10 <= interval_ms <= 200:  # 合理范围：5-100fps
            intervals_ms.append(interval_ms)
    
    if intervals_ms:
        avg_interval = statistics.mean(intervals_ms)
        fps = 1000 / avg_interval
        
        print(f"   📊 解码帧率统计:")
        print(f"     - 平均帧间隔: {avg_interval:.1f}ms")
        print(f"     - 实际帧率: {fps:.1f} fps")
        print(f"     - 最小间隔: {min(intervals_ms):.1f}ms")
        print(f"     - 最大间隔: {max(intervals_ms):.1f}ms")
        if len(intervals_ms) > 1:
            jitter = statistics.stdev(intervals_ms)
            print(f"     - 时序抖动: {jitter:.1f}ms (标准差)")
            print(f"     - 抖动率: {jitter/avg_interval*100:.1f}%")
        
        return {
            'avg_interval_ms': avg_interval,
            'fps': fps,
            'jitter_ms': statistics.stdev(intervals_ms) if len(intervals_ms) > 1 else 0
        }
    
    return {}

def analyze_rtp_consistency(frame_metas: List, decodes: List) -> Dict:
    """分析RTP时间戳一致性"""
    print("\n🎯 RTP时间戳一致性分析")
    print("   (检查丢帧和重复帧)")
    
    all_events = []
    
    # 合并所有事件
    for meta in frame_metas:
        all_events.append({
            'rtp_ts': meta['rtp_ts'],
            'mono_us': meta['mono_us'],
            'type': 'META',
            'ssrc': meta['ssrc']
        })
    
    for decode in decodes:
        all_events.append({
            'rtp_ts': decode['rtp_ts'],
            'mono_us': decode['mono_us'],
            'type': 'DECODE',
            'ssrc': decode['ssrc']
        })
    
    # 按SSRC分组
    ssrc_groups = {}
    for event in all_events:
        ssrc = event['ssrc']
        if ssrc not in ssrc_groups:
            ssrc_groups[ssrc] = []
        ssrc_groups[ssrc].append(event)
    
    for ssrc, events in ssrc_groups.items():
        print(f"\n   📡 SSRC {ssrc}:")
        
        # 按RTP时间戳排序
        sorted_events = sorted(events, key=lambda x: x['rtp_ts'])
        
        # 分析RTP间隔
        rtp_intervals = []
        for i in range(1, len(sorted_events)):
            rtp_diff = sorted_events[i]['rtp_ts'] - sorted_events[i-1]['rtp_ts']
            if rtp_diff > 0:  # 避免重复时间戳
                rtp_intervals.append(rtp_diff)
        
        if rtp_intervals:
            avg_rtp_interval = statistics.mean(rtp_intervals)
            expected_ms = avg_rtp_interval / 90  # 90kHz时钟
            print(f"     - 平均RTP间隔: {avg_rtp_interval:.0f} ({expected_ms:.1f}ms)")
            print(f"     - 期望帧率: {90000/avg_rtp_interval:.1f} fps")
            
            # 检查异常间隔
            large_gaps = [interval for interval in rtp_intervals if interval > avg_rtp_interval * 2]
            if large_gaps:
                print(f"     - 检测到 {len(large_gaps)} 个可能的丢帧")

def analyze_buffering_behavior(frame_metas: List, decodes: List) -> Dict:
    """分析缓冲行为"""
    print("\n🎯 缓冲行为分析")
    print("   (解码器输入vs输出的时序关系)")
    
    if not frame_metas or not decodes:
        print("   ❌ 数据不足")
        return {}
    
    # 按时间窗口分析
    window_size_ms = 1000  # 1秒窗口
    
    # 取最近的数据
    recent_metas = sorted(frame_metas, key=lambda x: x['mono_us'])[-100:]
    recent_decodes = sorted(decodes, key=lambda x: x['mono_us'])[-100:]
    
    if recent_metas and recent_decodes:
        start_time = min(recent_metas[0]['mono_us'], recent_decodes[0]['mono_us'])
        end_time = max(recent_metas[-1]['mono_us'], recent_decodes[-1]['mono_us'])
        
        duration_s = (end_time - start_time) / 1000000
        meta_rate = len(recent_metas) / duration_s
        decode_rate = len(recent_decodes) / duration_s
        
        print(f"   📊 缓冲统计 (最近{duration_s:.1f}秒):")
        print(f"     - 帧输入率: {meta_rate:.1f} fps")
        print(f"     - 帧输出率: {decode_rate:.1f} fps")
        print(f"     - 处理效率: {decode_rate/meta_rate*100:.1f}%")
        
        if decode_rate < meta_rate * 0.9:
            print(f"     ⚠️  解码器可能过载 (输出率低于输入率)")
        elif decode_rate > meta_rate * 1.1:
            print(f"     📈 解码器正在清空缓冲区")
        else:
            print(f"     ✅ 解码器运行稳定")

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_realistic_analyzer.py <receiver_log_file>")
        print("示例: python3 c2r_realistic_analyzer.py webrtc_config_results/receiver_cloud.log")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        frame_metas, decodes, sr_anchors = parse_c2r_logs(log_file)
        
        print("=" * 80)
        print("🎯 C2R实际可用延迟分析 (无需时钟同步)")
        print("=" * 80)
        
        print(f"\n📊 数据概览:")
        print(f"  - ACT扩展帧 (帧组装完成): {len(frame_metas)}")
        print(f"  - 解码事件 (解码完成): {len(decodes)}")
        print(f"  - SR锚点: {len(sr_anchors)}")
        
        # 执行实际可用的分析
        processing_result = analyze_processing_delays(frame_metas, decodes)
        framerate_result = analyze_frame_rate_consistency(decodes)
        analyze_rtp_consistency(frame_metas, decodes)
        analyze_buffering_behavior(frame_metas, decodes)
        
        print(f"\n💡 关键发现:")
        if processing_result['delays']:
            avg_processing = processing_result['avg_ms']
            print(f"  ✅ 平均处理延迟: {avg_processing:.1f}ms (帧组装→解码)")
        
        if framerate_result:
            fps = framerate_result['fps']
            jitter = framerate_result.get('jitter_ms', 0)
            print(f"  ✅ 实际解码帧率: {fps:.1f} fps")
            if jitter > 0:
                print(f"  📊 时序抖动: {jitter:.1f}ms")
        
        print(f"\n⚠️  重要说明:")
        print(f"  - 当前分析基于接收端单调时钟，不需要时钟同步")
        print(f"  - 无法计算绝对端到端延迟（需要发送端-接收端时钟同步）")
        print(f"  - 可以准确分析接收端内部的处理性能和稳定性")
        print(f"  - ACT扩展数据可用于未来的时钟同步实现")
        
        print("=" * 80)
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()