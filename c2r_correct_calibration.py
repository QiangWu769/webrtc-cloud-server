#!/usr/bin/env python3
"""
正确实现方法2：基于ACT的相对时钟校准
核心思想：利用RTCP SR建立两个时钟域的相对映射，而不是绝对时间对比
"""

import re
import sys
import statistics

def parse_logs_for_relative_calibration(log_file: str):
    """解析日志，提取相对时钟校准所需数据"""
    sr_events = []
    frame_data = []
    
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
                frame_data.append({
                    'type': 'meta',
                    'mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5))
                })
            
            # Decode事件
            match = re.search(patterns['decode'], line)
            if match:
                frame_data.append({
                    'type': 'decode',
                    'mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
    
    return sr_events, frame_data

def estimate_frame_send_time_from_sr(sr_events, frame_rtp_ts):
    """
    使用SR锚点估算帧的发送时间(发送端NTP域)
    方法：基于RTP时间戳的线性插值
    """
    if len(sr_events) < 2:
        return None
    
    # 找到最接近的前后两个SR锚点
    sorted_srs = sorted(sr_events, key=lambda x: x['send_rtp_ts'])
    
    before_sr = None
    after_sr = None
    
    for sr in sorted_srs:
        if sr['send_rtp_ts'] <= frame_rtp_ts:
            before_sr = sr
        elif sr['send_rtp_ts'] > frame_rtp_ts and not after_sr:
            after_sr = sr
            break
    
    if not before_sr or not after_sr:
        # 如果没有前后锚点，使用最近的一个
        closest_sr = min(sorted_srs, key=lambda sr: abs(sr['send_rtp_ts'] - frame_rtp_ts))
        return closest_sr['send_ntp_us']
    
    # 线性插值估算发送时间
    rtp_diff = after_sr['send_rtp_ts'] - before_sr['send_rtp_ts']
    ntp_diff = after_sr['send_ntp_us'] - before_sr['send_ntp_us']
    
    if rtp_diff > 0:
        frame_rtp_offset = frame_rtp_ts - before_sr['send_rtp_ts']
        estimated_send_ntp_us = before_sr['send_ntp_us'] + (ntp_diff * frame_rtp_offset) // rtp_diff
        return estimated_send_ntp_us
    
    return before_sr['send_ntp_us']

def build_ntp_to_mono_mapping(sr_events):
    """
    建立发送端NTP时间到接收端单调时钟的映射
    返回线性映射参数: mono_us = slope * ntp_us + intercept
    """
    if len(sr_events) < 5:
        return None
    
    # 使用最近30个SR事件
    recent_srs = sorted(sr_events, key=lambda x: x['rx_mono_us'])[-30:]
    
    # 简单线性回归
    n = len(recent_srs)
    sum_x = sum(sr['send_ntp_us'] for sr in recent_srs)
    sum_y = sum(sr['rx_mono_us'] for sr in recent_srs)
    sum_xy = sum(sr['send_ntp_us'] * sr['rx_mono_us'] for sr in recent_srs)
    sum_x2 = sum(sr['send_ntp_us'] ** 2 for sr in recent_srs)
    
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
    intercept = (sum_y - slope * sum_x) / n
    
    # 计算R²
    mean_y = sum_y / n
    ss_tot = sum((sr['rx_mono_us'] - mean_y) ** 2 for sr in recent_srs)
    ss_res = sum((sr['rx_mono_us'] - (slope * sr['send_ntp_us'] + intercept)) ** 2 for sr in recent_srs)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    return {
        'slope': slope,
        'intercept': intercept,
        'r_squared': r_squared,
        'sample_count': n
    }

def analyze_relative_latency(sr_events, frame_data):
    """基于相对时钟校准分析延迟"""
    print("🎯 方法2：基于ACT的相对时钟校准分析")
    print("=" * 60)
    
    print(f"📊 数据统计:")
    print(f"  - SR锚点: {len(sr_events)}")
    print(f"  - 帧事件: {len(frame_data)}")
    
    # 建立时钟映射
    mapping = build_ntp_to_mono_mapping(sr_events)
    if not mapping:
        print(f"  ❌ SR锚点不足，无法建立时钟映射")
        return
    
    print(f"\n🔧 时钟域映射:")
    print(f"  - 样本数: {mapping['sample_count']}")
    print(f"  - R²: {mapping['r_squared']:.6f}")
    print(f"  - 映射质量: {'优秀' if mapping['r_squared'] >= 0.98 else '良好' if mapping['r_squared'] >= 0.95 else '一般'}")
    
    # 分析帧数据
    meta_frames = [f for f in frame_data if f['type'] == 'meta']
    decode_frames = [f for f in frame_data if f['type'] == 'decode']
    
    print(f"\n📈 延迟分析:")
    print(f"  - ACT扩展帧: {len(meta_frames)}")
    print(f"  - 解码事件: {len(decode_frames)}")
    
    if not meta_frames:
        print(f"  ❌ 没有ACT扩展数据")
        return
    
    # 方法A：使用ACT直接时间差分析
    print(f"\n🎯 方法A：ACT时间差分析")
    act_relative_delays = []
    
    for i in range(1, min(len(meta_frames), 20)):
        curr_frame = meta_frames[i]
        prev_frame = meta_frames[i-1]
        
        # 计算帧间的相对延迟变化
        capture_time_diff = curr_frame['capture_ntp_us'] - prev_frame['capture_ntp_us']
        receive_time_diff = curr_frame['mono_us'] - prev_frame['mono_us']
        
        # 相对延迟变化 = 接收时间差 - 采集时间差
        relative_delay_change = receive_time_diff - capture_time_diff
        relative_delay_change_ms = relative_delay_change / 1000
        
        if abs(relative_delay_change_ms) < 1000:  # 合理范围
            act_relative_delays.append(relative_delay_change_ms)
    
    if act_relative_delays:
        print(f"    - 相对延迟变化 ({len(act_relative_delays)}个样本):")
        print(f"      平均: {statistics.mean(act_relative_delays):.1f}ms")
        print(f"      标准差: {statistics.stdev(act_relative_delays) if len(act_relative_delays) > 1 else 0:.1f}ms")
        print(f"      范围: {min(act_relative_delays):.1f}ms ~ {max(act_relative_delays):.1f}ms")
    
    # 方法B：使用SR锚点估算发送时间
    print(f"\n🎯 方法B：SR锚点估算延迟")
    sr_estimated_delays = []
    
    for frame in meta_frames[-10:]:  # 最近10帧
        # 使用SR锚点估算帧的发送时间
        estimated_send_ntp = estimate_frame_send_time_from_sr(sr_events, frame['rtp_ts'])
        
        if estimated_send_ntp:
            # 将估算的发送时间转换到接收端时钟域
            estimated_send_mono = mapping['slope'] * estimated_send_ntp + mapping['intercept']
            
            # 计算延迟
            estimated_latency_us = frame['mono_us'] - estimated_send_mono
            estimated_latency_ms = estimated_latency_us / 1000
            
            if -1000 < estimated_latency_ms < 5000:  # 合理范围
                sr_estimated_delays.append(estimated_latency_ms)
                print(f"    Frame {frame['frame_id']:4d}: {estimated_latency_ms:6.1f}ms (SR估算)")
    
    if sr_estimated_delays:
        print(f"    - SR估算延迟统计:")
        print(f"      平均: {statistics.mean(sr_estimated_delays):.1f}ms")
        print(f"      范围: {min(sr_estimated_delays):.1f}ms ~ {max(sr_estimated_delays):.1f}ms")
    
    # 处理延迟分析
    print(f"\n🎯 接收端处理延迟:")
    processing_delays = []
    
    for meta in meta_frames[-20:]:
        # 找到匹配的decode事件
        best_decode = None
        min_rtp_diff = float('inf')
        
        for decode in decode_frames:
            rtp_diff = abs(decode['rtp_ts'] - meta['rtp_ts'])
            if rtp_diff < min_rtp_diff and decode['ssrc'] == meta['ssrc']:
                min_rtp_diff = rtp_diff
                best_decode = decode
        
        if best_decode and min_rtp_diff < 90000:  # RTP差值<1秒
            proc_delay_us = best_decode['mono_us'] - meta['mono_us']
            proc_delay_ms = proc_delay_us / 1000
            
            if 0 < proc_delay_ms < 2000:  # 合理范围
                processing_delays.append(proc_delay_ms)
    
    if processing_delays:
        print(f"    - 处理延迟统计 ({len(processing_delays)}个样本):")
        print(f"      平均: {statistics.mean(processing_delays):.1f}ms")
        print(f"      范围: {min(processing_delays):.1f}ms ~ {max(processing_delays):.1f}ms")
    
    print(f"\n💡 方法2总结:")
    print(f"  ✅ 成功建立时钟域映射 (R²={mapping['r_squared']:.3f})")
    if act_relative_delays:
        print(f"  ✅ ACT相对延迟分析: 平均变化{statistics.mean(act_relative_delays):.1f}ms")
    if sr_estimated_delays:
        print(f"  ✅ SR估算绝对延迟: 平均{statistics.mean(sr_estimated_delays):.1f}ms")
    if processing_delays:
        print(f"  ✅ 处理延迟: 平均{statistics.mean(processing_delays):.1f}ms")

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_correct_calibration.py <receiver_log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        sr_events, frame_data = parse_logs_for_relative_calibration(log_file)
        analyze_relative_latency(sr_events, frame_data)
        
        print(f"\n🔬 方法2核心原理:")
        print(f"  1. 利用RTCP SR建立两时钟域的相对映射关系")
        print(f"  2. ACT提供精确的帧间相对时序信息")
        print(f"  3. 不依赖绝对时钟同步，基于相对时间差分析")
        print(f"  4. 可检测延迟变化趋势和处理性能")
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()