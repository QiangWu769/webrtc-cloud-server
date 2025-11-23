#!/usr/bin/env python3
"""
综合计算 WebRTC QoE (Quality of Experience) 指标

整合计算以下指标:
1. Switching Rate (分辨率切换率)
2. Rebuffering Ratio (重缓冲率)
3. 解码延迟 (Decode Latency)
4. 丢帧率 (Frame Drop Rate)

用法:
    python3 calculate_qoe_metrics.py <log_file>
"""

import re
import sys
from collections import defaultdict, Counter
import json


def calculate_all_metrics(log_file):
    """
    从 WebRTC 日志计算所有 QoE 指标

    Args:
        log_file: WebRTC 日志文件路径

    Returns:
        dict: 包含所有 QoE 指标的字典
    """
    with open(log_file, 'r') as f:
        log_content = f.read()

    metrics = {}

    # 1. 计算 Switching Rate
    metrics['switching_rate'] = calculate_switching_rate_internal(log_content)

    # 2. 计算 Rebuffering Ratio
    metrics['rebuffering'] = calculate_rebuffering_internal(log_content)

    # 3. 计算解码延迟
    metrics['decode_latency'] = calculate_decode_latency_internal(log_content)

    # 4. 计算丢帧率
    metrics['frame_drops'] = calculate_frame_drops_internal(log_content)

    return metrics


def calculate_switching_rate_internal(log_content):
    """内部函数: 计算 Switching Rate"""
    pattern = r'VideoReceiveStreamInterface stats: (\d+),.*?frameWidth: (\d+), frameHeight: (\d+).*?framesDecoded: (\d+)'
    matches = re.findall(pattern, log_content, re.DOTALL)

    samples = []
    for match in matches:
        timestamp = int(match[0])
        width = int(match[1])
        height = int(match[2])
        frames = int(match[3])

        if width > 0 and height > 0 and frames > 0:
            # 分辨率映射到档位
            if height >= 900:
                rung = 3
            elif height >= 700:
                rung = 2
            elif height >= 500:
                rung = 1
            else:
                rung = 0

            samples.append({
                'timestamp': timestamp,
                'frames': frames,
                'rung': rung
            })

    if not samples:
        return None

    total_frames = samples[-1]['frames']
    actual_duration = total_frames / 30.0
    segment_duration = 2.0

    # 为每个采样点分配 segment
    segments = defaultdict(list)
    for sample in samples:
        time_s = (sample['frames'] / total_frames) * actual_duration
        seg_idx = int(time_s // segment_duration)
        segments[seg_idx].append(sample['rung'])

    N = int(actual_duration / segment_duration)
    rung_seq = []
    for i in range(N):
        if i not in segments:
            if i == 0:
                rung_seq.append(0)
            else:
                rung_seq.append(rung_seq[-1])
        else:
            rung = Counter(segments[i]).most_common(1)[0][0]
            rung_seq.append(rung)

    N_switch = sum(1 for i in range(N-1) if rung_seq[i+1] != rung_seq[i])
    p_switch = N_switch / (N - 1) if N > 1 else 0.0

    return {
        'switching_rate': p_switch,
        'switch_count': N_switch,
        'total_segments': N,
        'duration_sec': actual_duration
    }


def calculate_rebuffering_internal(log_content):
    """内部函数: 计算 Rebuffering Ratio"""
    pattern = r'\[VideoQuality-CoreFreeze\].*?Freeze Count: (\d+), Total Freeze Duration \(ms\): ([\d.]+), Rebuffering Ratio: ([\d.]+), Playback Duration \(ms\): ([\d.]+)'
    matches = re.findall(pattern, log_content)

    if not matches:
        return None

    last = matches[-1]
    return {
        'rebuffering_ratio': float(last[2]),
        'freeze_count': int(last[0]),
        'freeze_duration_sec': float(last[1]) / 1000.0,
        'playback_duration_sec': float(last[3]) / 1000.0
    }


def calculate_decode_latency_internal(log_content):
    """内部函数: 计算解码延迟"""
    pattern = r'frameWidth: (\d+), frameHeight: (\d+).*?framesDecoded: (\d+).*?totalDecodeTime: ([\d.]+)'
    matches = re.findall(pattern, log_content, re.DOTALL)

    resolution_stats = {}
    prev_frames = 0

    for match in matches:
        width, height, frames, total_time = match
        resolution = f"{width}x{height}"
        frames = int(frames)
        total_time = float(total_time)

        if frames > prev_frames and resolution != "0x0":
            resolution_stats[resolution] = {
                'frames': frames,
                'total_time': total_time,
                'avg_ms_per_frame': (total_time / frames * 1000) if frames > 0 else 0
            }
            prev_frames = frames

    return resolution_stats


def calculate_frame_drops_internal(log_content):
    """内部函数: 计算丢帧率"""
    pattern = r'framesDecoded: (\d+), framesDropped: (\d+)'
    matches = re.findall(pattern, log_content)

    if not matches:
        return None

    final_decoded, final_dropped = matches[-1]
    final_decoded = int(final_decoded)
    final_dropped = int(final_dropped)

    total_frames = final_decoded + final_dropped
    drop_rate = (final_dropped / total_frames) if total_frames > 0 else 0.0

    return {
        'frames_decoded': final_decoded,
        'frames_dropped': final_dropped,
        'drop_rate': drop_rate
    }


def print_metrics_report(metrics):
    """打印格式化的指标报告"""
    print("=" * 80)
    print("WebRTC QoE 指标综合报告")
    print("=" * 80)
    print()

    # 1. Switching Rate
    if metrics['switching_rate']:
        sr = metrics['switching_rate']
        print("1. Switching Rate (分辨率切换率)")
        print("-" * 40)
        print(f"   切换率:      {sr['switching_rate']:.4f} ({sr['switching_rate']*100:.2f}%)")
        print(f"   切换次数:    {sr['switch_count']}")
        print(f"   总 segments: {sr['total_segments']}")
        print(f"   传输时长:    {sr['duration_sec']:.1f} 秒")
        if sr['switching_rate'] < 0.10:
            print(f"   评级:        ✓ 优秀")
        elif sr['switching_rate'] < 0.20:
            print(f"   评级:        ✓ 良好")
        else:
            print(f"   评级:        ⚠ 一般")
        print()

    # 2. Rebuffering Ratio
    if metrics['rebuffering']:
        rb = metrics['rebuffering']
        print("2. Rebuffering Ratio (重缓冲率)")
        print("-" * 40)
        print(f"   重缓冲率:    {rb['rebuffering_ratio']:.4f} ({rb['rebuffering_ratio']*100:.2f}%)")
        print(f"   冻结次数:    {rb['freeze_count']}")
        print(f"   冻结时长:    {rb['freeze_duration_sec']:.2f} 秒")
        print(f"   播放时长:    {rb['playback_duration_sec']:.2f} 秒")
        if rb['rebuffering_ratio'] < 0.01:
            print(f"   评级:        ✓ 优秀")
        elif rb['rebuffering_ratio'] < 0.05:
            print(f"   评级:        ✓ 良好")
        else:
            print(f"   评级:        ⚠ 一般")
        print()

    # 3. 解码延迟
    if metrics['decode_latency']:
        dl = metrics['decode_latency']
        print("3. 解码延迟 (Decode Latency)")
        print("-" * 40)
        print(f"   {'分辨率':<12} {'平均延迟(ms/帧)':<20} {'总帧数':<10}")
        print("   " + "-" * 45)
        for res in sorted(dl.keys()):
            if res != "0x0":
                print(f"   {res:<12} {dl[res]['avg_ms_per_frame']:<20.2f} {dl[res]['frames']:<10}")
        print()

    # 4. 丢帧率
    if metrics['frame_drops']:
        fd = metrics['frame_drops']
        print("4. 丢帧率 (Frame Drop Rate)")
        print("-" * 40)
        print(f"   丢帧率:      {fd['drop_rate']:.4f} ({fd['drop_rate']*100:.2f}%)")
        print(f"   已解码:      {fd['frames_decoded']} 帧")
        print(f"   已丢弃:      {fd['frames_dropped']} 帧")
        if fd['drop_rate'] == 0:
            print(f"   评级:        ✓ 优秀")
        elif fd['drop_rate'] < 0.01:
            print(f"   评级:        ✓ 良好")
        else:
            print(f"   评级:        ⚠ 一般")
        print()

    # 综合评级
    print("=" * 80)
    print("综合评级")
    print("=" * 80)

    grades = []
    if metrics['switching_rate'] and metrics['switching_rate']['switching_rate'] < 0.10:
        grades.append('A')
    elif metrics['switching_rate']:
        grades.append('B')

    if metrics['rebuffering'] and metrics['rebuffering']['rebuffering_ratio'] < 0.05:
        grades.append('A')
    elif metrics['rebuffering']:
        grades.append('B')

    if metrics['frame_drops'] and metrics['frame_drops']['drop_rate'] == 0:
        grades.append('A')
    elif metrics['frame_drops']:
        grades.append('B')

    if grades:
        avg_grade = 'A' if grades.count('A') >= len(grades) / 2 else 'B'
        print(f"整体性能评级: {avg_grade}")
        if avg_grade == 'A':
            print("✓ 传输质量优秀，用户体验良好")
        else:
            print("✓ 传输质量良好，有改进空间")


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <log_file> [--json]")
        sys.exit(1)

    log_file = sys.argv[1]
    output_json = '--json' in sys.argv

    metrics = calculate_all_metrics(log_file)

    if output_json:
        # 输出 JSON 格式
        print(json.dumps(metrics, indent=2))
    else:
        # 输出格式化报告
        print_metrics_report(metrics)


if __name__ == '__main__':
    main()
