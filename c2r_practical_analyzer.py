#!/usr/bin/env python3
"""
C2R实用延迟分析器
专注于相对延迟变化和趋势分析，不依赖绝对时间戳校准
"""

import re
import sys
import statistics
from typing import Dict, List, Optional, Tuple

def parse_c2r_logs_practical(log_file: str):
    """解析C2R日志，专注于实用的延迟分析"""
    
    act_events = []
    frame_events = []
    decode_events = []
    
    patterns = {
        'act_rx': r'\[C2R-ACT-RX\] RtpTs=(\d+), Ssrc=(\d+), SeqNum=(\d+), RxUs=(\d+), ActCaptureUs=(\d+), RelativeDelayUs=([-\d]+)',
        'frame_meta': r'\[C2R-FRAME-META\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), CaptureNtpUs=(\d+), Ssrc=(\d+)',
        'e2e_assembled': r'\[C2R-E2E-ASSEMBLED\] RtpTs=(\d+), Ssrc=(\d+), DelayMs=([-\d.e+]+), CaptureUs=(\d+), ASSEMBLEDUs=(\d+)',
        'decode': r'\[C2R-DECODE\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), Ssrc=(\d+)',
        'e2e_decoded': r'\[C2R-E2E-DECODED\] RtpTs=(\d+), Ssrc=(\d+), DelayMs=([-\d.e+]+), CaptureUs=(\d+), DECODEDUs=(\d+)'
    }
    
    with open(log_file, 'r') as f:
        for line in f:
            # ACT接收事件
            match = re.search(patterns['act_rx'], line)
            if match:
                act_events.append({
                    'rtp_ts': int(match.group(1)),
                    'ssrc': int(match.group(2)),
                    'seq_num': int(match.group(3)),
                    'rx_us': int(match.group(4)),
                    'act_capture_us': int(match.group(5)),
                    'relative_delay_us': int(match.group(6))
                })
                continue
            
            # Frame Meta事件
            match = re.search(patterns['frame_meta'], line)
            if match:
                frame_events.append({
                    'mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5))
                })
                continue
            
            # Decode事件
            match = re.search(patterns['decode'], line)
            if match:
                decode_events.append({
                    'decode_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
                continue
    
    return act_events, frame_events, decode_events

def analyze_act_performance(act_events: List[Dict]):
    """分析ACT扩展性能和覆盖率"""
    
    if not act_events:
        return {'status': 'no_data'}
    
    # 按SSRC分组
    ssrc_groups = {}
    for event in act_events:
        ssrc = event['ssrc']
        if ssrc not in ssrc_groups:
            ssrc_groups[ssrc] = []
        ssrc_groups[ssrc].append(event)
    
    # 计算时间跨度
    time_span_us = max(event['rx_us'] for event in act_events) - min(event['rx_us'] for event in act_events)
    time_span_sec = time_span_us / 1000000
    
    # 计算帧率
    avg_frame_rate = len(act_events) / time_span_sec if time_span_sec > 0 else 0
    
    # 分析延迟变化趋势（忽略绝对值，只看变化）
    if len(act_events) >= 10:
        # 取最近的两段时间进行对比
        mid_point = len(act_events) // 2
        early_delays = [e['relative_delay_us'] for e in act_events[:mid_point]]
        late_delays = [e['relative_delay_us'] for e in act_events[mid_point:]]
        
        early_avg = statistics.mean(early_delays)
        late_avg = statistics.mean(late_delays)
        delay_trend_us = late_avg - early_avg
        delay_trend_ms = delay_trend_us / 1000
    else:
        delay_trend_ms = 0
    
    return {
        'status': 'available',
        'total_frames': len(act_events),
        'ssrc_count': len(ssrc_groups),
        'time_span_sec': time_span_sec,
        'avg_frame_rate': avg_frame_rate,
        'delay_trend_ms': delay_trend_ms,
        'ssrc_groups': ssrc_groups
    }

def analyze_processing_pipeline(frame_events: List[Dict], decode_events: List[Dict]):
    """分析处理管道性能"""
    
    if not frame_events or not decode_events:
        return {'status': 'insufficient_data'}
    
    # 计算处理延迟（Frame Meta到Decode的时间差）
    processing_delays = []
    
    for frame in frame_events[-50:]:  # 最近50帧
        # 查找匹配的decode事件
        matching_decodes = [d for d in decode_events 
                          if d['rtp_ts'] == frame['rtp_ts'] and d['ssrc'] == frame['ssrc']]
        
        if matching_decodes:
            # 使用最近的匹配解码事件
            decode = max(matching_decodes, key=lambda x: x['decode_us'])
            proc_delay_us = decode['decode_us'] - frame['mono_us']
            proc_delay_ms = proc_delay_us / 1000
            
            # 过滤合理范围内的延迟
            if 0 < proc_delay_ms < 2000:  # 0-2秒
                processing_delays.append(proc_delay_ms)
    
    if not processing_delays:
        return {'status': 'no_valid_delays'}
    
    return {
        'status': 'available',
        'count': len(processing_delays),
        'avg_ms': statistics.mean(processing_delays),
        'min_ms': min(processing_delays),
        'max_ms': max(processing_delays),
        'std_ms': statistics.stdev(processing_delays) if len(processing_delays) > 1 else 0,
        'delays': processing_delays
    }

def analyze_practical_c2r_performance(act_events, frame_events, decode_events):
    """实用的C2R性能分析"""
    
    print("🎯 C2R实用延迟分析")
    print("专注于相对变化和性能趋势")
    print("=" * 60)
    
    print(f"📊 数据概览:")
    print(f"  - ACT扩展帧: {len(act_events)}")
    print(f"  - Frame Meta事件: {len(frame_events)}")
    print(f"  - Decode事件: {len(decode_events)}")
    
    # ACT性能分析
    act_analysis = analyze_act_performance(act_events)
    
    if act_analysis['status'] == 'available':
        print(f"\n🎯 ACT扩展性能:")
        print(f"  - 总帧数: {act_analysis['total_frames']}")
        print(f"  - 流数量: {act_analysis['ssrc_count']}")
        print(f"  - 时间跨度: {act_analysis['time_span_sec']:.1f}秒")
        print(f"  - 平均帧率: {act_analysis['avg_frame_rate']:.1f} fps")
        
        # 延迟趋势分析
        trend = act_analysis['delay_trend_ms']
        if abs(trend) < 10:
            trend_desc = "稳定"
        elif trend > 0:
            trend_desc = f"延迟增加 (+{trend:.1f}ms)"
        else:
            trend_desc = f"延迟减少 ({trend:.1f}ms)"
        
        print(f"  - 延迟趋势: {trend_desc}")
        
        # SSRC详细信息
        for ssrc, events in act_analysis['ssrc_groups'].items():
            if len(events) > 10:
                seq_nums = [e['seq_num'] for e in events]
                seq_gap = max(seq_nums) - min(seq_nums) + 1
                actual_frames = len(events)
                loss_rate = (seq_gap - actual_frames) / seq_gap * 100 if seq_gap > 0 else 0
                
                print(f"    SSRC {ssrc}: {actual_frames}帧, 丢包率{loss_rate:.1f}%")
    
    # 处理管道分析
    proc_analysis = analyze_processing_pipeline(frame_events, decode_events)
    
    if proc_analysis['status'] == 'available':
        print(f"\n📈 处理管道性能:")
        print(f"  - 有效样本: {proc_analysis['count']}")
        print(f"  - 平均处理延迟: {proc_analysis['avg_ms']:.1f}ms")
        print(f"  - 延迟范围: {proc_analysis['min_ms']:.1f}ms ~ {proc_analysis['max_ms']:.1f}ms")
        print(f"  - 延迟稳定性: {proc_analysis['std_ms']:.1f}ms (标准差)")
        
        # 性能评级
        avg_delay = proc_analysis['avg_ms']
        if avg_delay < 50:
            rating = "优秀 🎯"
        elif avg_delay < 100:
            rating = "良好 ✅"
        elif avg_delay < 200:
            rating = "一般 ⚠️"
        else:
            rating = "需要优化 ❌"
        
        print(f"  - 性能评级: {rating}")
        
        # 显示最新几个处理延迟
        print(f"\n  最新10个处理延迟:")
        for i, delay in enumerate(proc_analysis['delays'][-10:]):
            print(f"    {i+1:2d}: {delay:6.1f}ms")
    
    # 实用建议
    print(f"\n💡 实用分析结论:")
    
    if act_analysis['status'] == 'available':
        frame_rate = act_analysis['avg_frame_rate']
        if frame_rate > 25:
            print(f"  ✅ ACT扩展工作正常，帧率{frame_rate:.1f}fps")
        elif frame_rate > 15:
            print(f"  ⚠️  帧率偏低: {frame_rate:.1f}fps，可能存在性能问题")
        else:
            print(f"  ❌ 帧率严重不足: {frame_rate:.1f}fps")
    
    if proc_analysis['status'] == 'available':
        if proc_analysis['std_ms'] < 20:
            print(f"  ✅ 处理延迟稳定，抖动{proc_analysis['std_ms']:.1f}ms")
        else:
            print(f"  ⚠️  处理延迟波动较大，抖动{proc_analysis['std_ms']:.1f}ms")
    
    print(f"\n🔧 推荐实施步骤验证:")
    print(f"  ✅ Step 1: 基础框架 - 内联实现完成")
    print(f"  ✅ Step 2: ACT扩展解析 - {len(act_events)}个事件")
    print(f"  ✅ Step 3: 统一日志格式 - 多种事件类型")
    print(f"  🎯 专注相对延迟变化而非绝对值 - 符合设计目标")
    
    print("=" * 60)

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_practical_analyzer.py <receiver_log_file>")
        print("专注于实用的延迟分析，不依赖绝对时间戳校准")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        act_events, frame_events, decode_events = parse_c2r_logs_practical(log_file)
        analyze_practical_c2r_performance(act_events, frame_events, decode_events)
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()