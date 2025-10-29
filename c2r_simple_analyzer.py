#!/usr/bin/env python3
"""
简化的C2R延迟分析工具 - 专注于实际可用的分析方法
"""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Dict
import statistics

@dataclass
class C2REvent:
    timestamp_us: int
    event_type: str
    frame_id: Optional[int] = None
    rtp_ts: Optional[int] = None
    capture_ntp_us: Optional[int] = None
    sr_ntp_us: Optional[int] = None
    ssrc: Optional[int] = None

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
            # Frame Meta 日志 (ACT扩展)
            match = re.search(patterns['frame_meta'], line)
            if match:
                frame_metas.append({
                    'mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5))
                })
            
            # Decode 日志
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

def analyze_frame_intervals(frame_metas, decodes):
    """分析帧间间隔和处理延迟"""
    print("🎯 帧间隔分析 (基于RTP时间戳)")
    
    if not frame_metas and not decodes:
        print("  ❌ 没有帧数据")
        return
    
    # 使用decode数据分析帧间隔（更常见）
    events = decodes if decodes else frame_metas
    events = sorted(events, key=lambda x: x['rtp_ts'])
    
    intervals_ms = []
    for i in range(1, len(events)):
        rtp_diff = events[i]['rtp_ts'] - events[i-1]['rtp_ts']
        interval_ms = rtp_diff / 90  # RTP时钟90kHz转换为毫秒
        if 10 <= interval_ms <= 100:  # 合理的帧间隔范围
            intervals_ms.append(interval_ms)
    
    if intervals_ms:
        print(f"  📊 帧间隔统计 (最近{len(intervals_ms)}帧):")
        print(f"    - 平均帧间隔: {statistics.mean(intervals_ms):.1f}ms")
        print(f"    - 帧率估算: {1000/statistics.mean(intervals_ms):.1f} fps")
        print(f"    - 最小间隔: {min(intervals_ms):.1f}ms")
        print(f"    - 最大间隔: {max(intervals_ms):.1f}ms")

def analyze_processing_pipeline(frame_metas, decodes):
    """分析处理管道延迟"""
    print("\n🎯 处理管道分析")
    
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
    
    for ssrc, data in ssrc_groups.items():
        print(f"\n  📡 SSRC {ssrc}:")
        print(f"    - ACT扩展帧: {len(data['metas'])}")
        print(f"    - 解码事件: {len(data['decodes'])}")
        
        if data['metas']:
            # 分析ACT扩展的内部延迟
            recent_metas = sorted(data['metas'], key=lambda x: x['mono_us'])[-10:]
            internal_delays = []
            
            for meta in recent_metas:
                # 帧组装完成时间 vs 采集时间的"表观"差异
                # 注意：这包含了时钟域差异，不是真实延迟
                apparent_delay = meta['mono_us'] - meta['capture_ntp_us']
                internal_delays.append(apparent_delay / 1000)  # 转换为毫秒
            
            print(f"    - 表观延迟范围: {min(internal_delays):.0f}ms ~ {max(internal_delays):.0f}ms")
            print(f"      (包含时钟域差异，非真实延迟)")

def analyze_timing_consistency(frame_metas, decodes, sr_anchors):
    """分析时序一致性"""
    print("\n🎯 时序一致性分析")
    
    # SR发送频率
    if len(sr_anchors) >= 2:
        sr_sorted = sorted(sr_anchors, key=lambda x: x['mono_us'])
        sr_intervals = []
        for i in range(1, min(len(sr_sorted), 20)):
            interval = (sr_sorted[i]['mono_us'] - sr_sorted[i-1]['mono_us']) / 1000
            sr_intervals.append(interval)
        
        if sr_intervals:
            print(f"  📡 RTCP SR发送间隔:")
            print(f"    - 平均间隔: {statistics.mean(sr_intervals):.0f}ms")
            print(f"    - 发送频率: {1000/statistics.mean(sr_intervals):.1f} Hz")
    
    # 解码事件频率
    if len(decodes) >= 2:
        decode_sorted = sorted(decodes, key=lambda x: x['mono_us'])[-20:]
        decode_intervals = []
        for i in range(1, len(decode_sorted)):
            interval = (decode_sorted[i]['mono_us'] - decode_sorted[i-1]['mono_us']) / 1000
            if 10 <= interval <= 100:  # 合理范围
                decode_intervals.append(interval)
        
        if decode_intervals:
            print(f"  🎬 解码事件间隔:")
            print(f"    - 平均间隔: {statistics.mean(decode_intervals):.1f}ms")
            print(f"    - 解码频率: {1000/statistics.mean(decode_intervals):.1f} fps")

def show_recent_events(frame_metas, decodes, sr_anchors):
    """显示最近的事件"""
    print("\n🎯 最近事件 (最新5个)")
    
    all_events = []
    
    for meta in frame_metas[-5:]:
        all_events.append({
            'time': meta['mono_us'],
            'type': 'FRAME-META',
            'info': f"Frame {meta['frame_id']}, RTP {meta['rtp_ts']}"
        })
    
    for decode in decodes[-5:]:
        all_events.append({
            'time': decode['mono_us'],
            'type': 'DECODE',
            'info': f"Frame {decode['frame_id']}, RTP {decode['rtp_ts']}"
        })
    
    for sr in sr_anchors[-3:]:
        all_events.append({
            'time': sr['mono_us'],
            'type': 'SR-RX',
            'info': f"RTP {sr['rtp_ts']}"
        })
    
    # 按时间排序
    all_events.sort(key=lambda x: x['time'])
    
    for event in all_events[-10:]:
        time_str = f"{event['time']:,}"
        print(f"  {event['type']:12} @ {time_str}us: {event['info']}")

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_simple_analyzer.py <receiver_log_file>")
        print("示例: python3 c2r_simple_analyzer.py webrtc_config_results/receiver_cloud.log")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        frame_metas, decodes, sr_anchors = parse_c2r_logs(log_file)
        
        print("=" * 70)
        print("🎯 C2R延迟分析报告 - 实用版")
        print("=" * 70)
        
        print(f"\n📊 数据统计:")
        print(f"  - ACT扩展帧 (FRAME-META): {len(frame_metas)}")
        print(f"  - 解码事件 (DECODE): {len(decodes)}")
        print(f"  - SR锚点 (SR-RX): {len(sr_anchors)}")
        
        if frame_metas:
            print(f"  ✅ 支持高精度分析 (ACT扩展可用)")
        else:
            print(f"  ⚠️  仅支持相对分析 (无ACT扩展)")
        
        # 执行各种分析
        analyze_frame_intervals(frame_metas, decodes)
        analyze_processing_pipeline(frame_metas, decodes)
        analyze_timing_consistency(frame_metas, decodes, sr_anchors)
        show_recent_events(frame_metas, decodes, sr_anchors)
        
        print(f"\n💡 分析建议:")
        if frame_metas:
            print(f"  - ACT扩展工作正常，可进行精确延迟测量")
            print(f"  - 需要发送端和接收端时钟同步来计算绝对延迟")
            print(f"  - 可以分析延迟的相对变化和趋势")
        else:
            print(f"  - 建议启用ACT扩展以获得精确测量")
            print(f"  - 当前可分析处理性能和时序稳定性")
        
        print("=" * 70)
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()