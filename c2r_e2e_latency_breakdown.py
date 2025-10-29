#!/usr/bin/env python3
"""
C2R端到端延迟组成分析器
详细分析延迟各个阶段的组成和表现
"""

import re
import sys
import statistics
from collections import defaultdict
import numpy as np

def parse_e2e_latency_data(log_file: str):
    """解析端到端延迟数据"""
    
    # 数据结构
    act_events = []          # RTP包接收 + ACT解析
    frame_assembled = []     # 帧组装完成
    frame_decoded = []       # 帧解码完成
    frame_meta = []          # 帧元数据
    
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
                frame_meta.append({
                    'mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5))
                })
                continue
                
            # E2E组装事件
            match = re.search(patterns['e2e_assembled'], line)
            if match:
                frame_assembled.append({
                    'rtp_ts': int(match.group(1)),
                    'ssrc': int(match.group(2)),
                    'assembled_us': int(match.group(5))
                })
                continue
                
            # 解码事件
            match = re.search(patterns['decode'], line)
            if match:
                frame_decoded.append({
                    'decode_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
                continue
    
    return act_events, frame_meta, frame_assembled, frame_decoded

def analyze_latency_stages(act_events, frame_meta, frame_assembled, frame_decoded):
    """分析延迟各个阶段"""
    
    # 按RTP时间戳组织数据
    frames_by_rtp = defaultdict(dict)
    
    # 组织ACT事件
    for event in act_events:
        rtp_ts = event['rtp_ts']
        frames_by_rtp[rtp_ts]['act_rx_us'] = event['rx_us']
        frames_by_rtp[rtp_ts]['ssrc'] = event['ssrc']
        frames_by_rtp[rtp_ts]['seq_num'] = event['seq_num']
    
    # 组织Frame Meta事件
    for event in frame_meta:
        rtp_ts = event['rtp_ts']
        frames_by_rtp[rtp_ts]['meta_us'] = event['mono_us']
    
    # 组织组装事件
    for event in frame_assembled:
        rtp_ts = event['rtp_ts']
        frames_by_rtp[rtp_ts]['assembled_us'] = event['assembled_us']
    
    # 组织解码事件
    for event in frame_decoded:
        rtp_ts = event['rtp_ts']
        if 'decoded_us' not in frames_by_rtp[rtp_ts]:
            frames_by_rtp[rtp_ts]['decoded_us'] = event['decode_us']
    
    # 计算各阶段延迟
    stage_delays = {
        'rx_to_meta': [],      # RTP接收 -> Frame Meta
        'meta_to_assembled': [], # Frame Meta -> 组装完成
        'assembled_to_decoded': [], # 组装完成 -> 解码完成
        'rx_to_decoded': []    # 总的接收端延迟
    }
    
    complete_frames = []
    
    for rtp_ts, frame_data in frames_by_rtp.items():
        # 只分析有完整数据的帧
        required_fields = ['act_rx_us', 'meta_us', 'assembled_us']
        if all(field in frame_data for field in required_fields):
            
            # 计算各阶段延迟
            rx_to_meta = (frame_data['meta_us'] - frame_data['act_rx_us']) / 1000  # ms
            meta_to_assembled = (frame_data['assembled_us'] - frame_data['meta_us']) / 1000  # ms
            
            # 过滤合理范围的延迟
            if 0 < rx_to_meta < 100 and -10 < meta_to_assembled < 100:
                stage_delays['rx_to_meta'].append(rx_to_meta)
                stage_delays['meta_to_assembled'].append(meta_to_assembled)
                
                frame_info = {
                    'rtp_ts': rtp_ts,
                    'rx_to_meta_ms': rx_to_meta,
                    'meta_to_assembled_ms': meta_to_assembled,
                    'total_rx_ms': rx_to_meta + meta_to_assembled
                }
                
                # 如果有解码数据
                if 'decoded_us' in frame_data:
                    assembled_to_decoded = (frame_data['decoded_us'] - frame_data['assembled_us']) / 1000
                    rx_to_decoded = (frame_data['decoded_us'] - frame_data['act_rx_us']) / 1000
                    
                    if 0 < assembled_to_decoded < 1000 and 0 < rx_to_decoded < 1000:
                        stage_delays['assembled_to_decoded'].append(assembled_to_decoded)
                        stage_delays['rx_to_decoded'].append(rx_to_decoded)
                        frame_info['assembled_to_decoded_ms'] = assembled_to_decoded
                        frame_info['total_decoded_ms'] = rx_to_decoded
                
                complete_frames.append(frame_info)
    
    return stage_delays, complete_frames

def analyze_frame_rate_and_timing(act_events):
    """分析帧率和时序特征"""
    
    if len(act_events) < 10:
        return {}
    
    # 按时间排序
    sorted_events = sorted(act_events, key=lambda x: x['rx_us'])
    
    # 计算帧间间隔
    frame_intervals = []
    for i in range(1, len(sorted_events)):
        interval_us = sorted_events[i]['rx_us'] - sorted_events[i-1]['rx_us']
        interval_ms = interval_us / 1000
        if 10 < interval_ms < 200:  # 合理的帧间间隔
            frame_intervals.append(interval_ms)
    
    if not frame_intervals:
        return {}
    
    # 计算统计信息
    avg_interval = statistics.mean(frame_intervals)
    std_interval = statistics.stdev(frame_intervals) if len(frame_intervals) > 1 else 0
    theoretical_fps = 1000 / avg_interval if avg_interval > 0 else 0
    
    # 分析时序稳定性
    jitter_ms = std_interval
    
    return {
        'frame_count': len(sorted_events),
        'time_span_sec': (sorted_events[-1]['rx_us'] - sorted_events[0]['rx_us']) / 1000000,
        'avg_interval_ms': avg_interval,
        'jitter_ms': jitter_ms,
        'theoretical_fps': theoretical_fps,
        'intervals': frame_intervals
    }

def generate_e2e_report(act_events, frame_meta, frame_assembled, frame_decoded):
    """生成端到端延迟报告"""
    
    print("🎯 WebRTC端到端延迟组成分析")
    print("=" * 70)
    
    # 基础数据统计
    print(f"📊 数据统计:")
    print(f"  - ACT接收事件: {len(act_events)}")
    print(f"  - Frame Meta事件: {len(frame_meta)}")
    print(f"  - 帧组装事件: {len(frame_assembled)}")
    print(f"  - 帧解码事件: {len(frame_decoded)}")
    
    # 分析延迟阶段
    stage_delays, complete_frames = analyze_latency_stages(act_events, frame_meta, frame_assembled, frame_decoded)
    
    print(f"\n🔍 延迟阶段分析:")
    print(f"  - 完整处理链路帧数: {len(complete_frames)}")
    
    # 各阶段延迟统计
    for stage_name, delays in stage_delays.items():
        if delays:
            avg_delay = statistics.mean(delays)
            std_delay = statistics.stdev(delays) if len(delays) > 1 else 0
            min_delay = min(delays)
            max_delay = max(delays)
            
            stage_desc = {
                'rx_to_meta': 'RTP接收→Frame Meta',
                'meta_to_assembled': 'Frame Meta→组装完成',
                'assembled_to_decoded': '组装完成→解码完成',
                'rx_to_decoded': '接收→解码(总计)'
            }
            
            print(f"\n  📈 {stage_desc.get(stage_name, stage_name)} ({len(delays)}样本):")
            print(f"    - 平均: {avg_delay:.2f}ms")
            print(f"    - 标准差: {std_delay:.2f}ms")
            print(f"    - 范围: {min_delay:.2f}ms ~ {max_delay:.2f}ms")
            
            # 性能评级
            if stage_name == 'rx_to_decoded':
                if avg_delay < 50:
                    rating = "优秀 🎯"
                elif avg_delay < 100:
                    rating = "良好 ✅"
                elif avg_delay < 200:
                    rating = "一般 ⚠️"
                else:
                    rating = "需要优化 ❌"
                print(f"    - 性能评级: {rating}")
    
    # 帧率和时序分析
    timing_analysis = analyze_frame_rate_and_timing(act_events)
    
    if timing_analysis:
        print(f"\n📺 帧率和时序特征:")
        print(f"  - 传输时长: {timing_analysis['time_span_sec']:.1f}秒")
        print(f"  - 理论帧率: {timing_analysis['theoretical_fps']:.1f} fps")
        print(f"  - 平均帧间隔: {timing_analysis['avg_interval_ms']:.1f}ms")
        print(f"  - 时序抖动: {timing_analysis['jitter_ms']:.1f}ms")
        
        # 帧率稳定性评估
        if timing_analysis['jitter_ms'] < 5:
            stability = "非常稳定 🎯"
        elif timing_analysis['jitter_ms'] < 10:
            stability = "稳定 ✅"
        elif timing_analysis['jitter_ms'] < 20:
            stability = "轻微抖动 ⚠️"
        else:
            stability = "抖动明显 ❌"
        
        print(f"  - 稳定性评估: {stability}")
    
    # 详细的延迟组成分析
    if complete_frames:
        print(f"\n🎬 延迟组成详细分析 (最新10帧):")
        print(f"  {'帧序号':<8} {'接收→Meta':<12} {'Meta→组装':<12} {'组装→解码':<12} {'总延迟':<10}")
        print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*12} {'-'*10}")
        
        for i, frame in enumerate(complete_frames[-10:]):
            rx_meta = f"{frame['rx_to_meta_ms']:.1f}ms"
            meta_asm = f"{frame['meta_to_assembled_ms']:.1f}ms"
            
            if 'assembled_to_decoded_ms' in frame:
                asm_dec = f"{frame['assembled_to_decoded_ms']:.1f}ms"
                total = f"{frame['total_decoded_ms']:.1f}ms"
            else:
                asm_dec = "N/A"
                total = f"{frame['total_rx_ms']:.1f}ms"
            
            print(f"  {i+1:<8} {rx_meta:<12} {meta_asm:<12} {asm_dec:<12} {total:<10}")
    
    # 性能瓶颈分析
    print(f"\n🔧 性能瓶颈分析:")
    
    if stage_delays['rx_to_meta'] and stage_delays['meta_to_assembled']:
        rx_meta_avg = statistics.mean(stage_delays['rx_to_meta'])
        meta_asm_avg = statistics.mean(stage_delays['meta_to_assembled'])
        
        if rx_meta_avg > meta_asm_avg * 2:
            print(f"  ⚠️  RTP接收→Meta阶段耗时较长 ({rx_meta_avg:.1f}ms)")
            print(f"     可能原因: 网络抖动、RTP解析延迟")
        elif meta_asm_avg > rx_meta_avg * 2:
            print(f"  ⚠️  Meta→组装阶段耗时较长 ({meta_asm_avg:.1f}ms)")
            print(f"     可能原因: 帧重组延迟、丢包重传")
        else:
            print(f"  ✅ 各阶段延迟相对均衡")
    
    if stage_delays['assembled_to_decoded']:
        decode_avg = statistics.mean(stage_delays['assembled_to_decoded'])
        if decode_avg > 50:
            print(f"  ⚠️  解码阶段延迟较高 ({decode_avg:.1f}ms)")
            print(f"     可能原因: CPU性能、解码器配置")
        else:
            print(f"  ✅ 解码性能良好 ({decode_avg:.1f}ms)")
    
    print(f"\n💡 优化建议:")
    
    if timing_analysis and timing_analysis['jitter_ms'] > 15:
        print(f"  1. 网络优化: 时序抖动{timing_analysis['jitter_ms']:.1f}ms，建议优化网络条件")
    
    if stage_delays['rx_to_decoded']:
        total_avg = statistics.mean(stage_delays['rx_to_decoded'])
        if total_avg > 100:
            print(f"  2. 整体优化: 总延迟{total_avg:.1f}ms，建议端到端优化")
        else:
            print(f"  ✅ 当前延迟表现良好: 平均{total_avg:.1f}ms")
    
    print("=" * 70)

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_e2e_latency_breakdown.py <receiver_log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        act_events, frame_meta, frame_assembled, frame_decoded = parse_e2e_latency_data(log_file)
        generate_e2e_report(act_events, frame_meta, frame_assembled, frame_decoded)
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()