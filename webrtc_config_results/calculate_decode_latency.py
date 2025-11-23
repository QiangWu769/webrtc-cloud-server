#!/usr/bin/env python3
"""
计算不同分辨率下的解码延迟

分析 WebRTC 接收端日志，提取不同分辨率下的解码性能指标

用法:
    python3 calculate_decode_latency.py <log_file>
"""

import re
import sys
from collections import defaultdict


def calculate_decode_latency(log_file):
    """
    从 WebRTC 日志提取不同分辨率的解码延迟统计

    Args:
        log_file: WebRTC 日志文件路径

    Returns:
        dict: 各分辨率的解码延迟统计
    """
    # 读取日志
    with open(log_file, 'r') as f:
        log_content = f.read()

    # 提取所有 VideoReceiveStreamInterface stats
    pattern = r'VideoReceiveStreamInterface stats:.*?frameWidth: (\d+), frameHeight: (\d+).*?framesDecoded: (\d+).*?decode_ms: (\d+), max_decode_ms: (\d+).*?totalDecodeTime: ([\d.]+)'

    matches = re.findall(pattern, log_content, re.DOTALL)

    # 按分辨率分组统计
    resolution_stats = {}
    prev_frames = 0

    for match in matches:
        width, height, frames, decode_ms, max_decode, total_time = match
        resolution = f"{width}x{height}"
        frames = int(frames)

        if frames > prev_frames and resolution != "0x0":  # 排除初始状态
            if resolution not in resolution_stats:
                resolution_stats[resolution] = {
                    'decode_ms_list': [],
                    'max_decode_ms_list': [],
                    'frame_counts': [],
                    'total_decode_times': []
                }

            resolution_stats[resolution]['decode_ms_list'].append(int(decode_ms))
            resolution_stats[resolution]['max_decode_ms_list'].append(int(max_decode))
            resolution_stats[resolution]['frame_counts'].append(frames)
            resolution_stats[resolution]['total_decode_times'].append(float(total_time))
            prev_frames = frames

    # 计算统计结果
    results = {}
    for resolution in sorted(resolution_stats.keys()):
        stats = resolution_stats[resolution]

        if not stats['decode_ms_list']:
            continue

        # 计算平均值
        avg_decode = sum(stats['decode_ms_list']) / len(stats['decode_ms_list'])
        max_decode = max(stats['max_decode_ms_list'])
        final_frames = stats['frame_counts'][-1]
        final_total_time = stats['total_decode_times'][-1]

        # 计算实际平均解码时间(从 totalDecodeTime 计算)
        if final_frames > 0:
            actual_avg = (final_total_time / final_frames) * 1000  # 转换为毫秒
        else:
            actual_avg = 0

        results[resolution] = {
            'sample_count': len(stats['decode_ms_list']),
            'decode_ms_avg': avg_decode,
            'max_decode_ms': max_decode,
            'total_frames': final_frames,
            'total_decode_time_sec': final_total_time,
            'actual_avg_ms_per_frame': actual_avg
        }

    return results


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <log_file>")
        sys.exit(1)

    log_file = sys.argv[1]

    print("=" * 80)
    print("不同分辨率解码延迟统计")
    print("=" * 80)
    print()

    results = calculate_decode_latency(log_file)

    if not results:
        print("错误: 未能从日志中提取解码延迟数据")
        sys.exit(1)

    print(f"{'分辨率':<12} {'实际平均':<15} {'decode_ms':<15} {'max_decode':<12} {'帧数':<10}")
    print(f"{'':12} {'(ms/帧)':<15} {'平均(ms)':<15} {'(ms)':<12} {'':<10}")
    print("-" * 80)

    for resolution in sorted(results.keys()):
        r = results[resolution]
        print(f"{resolution:<12} {r['actual_avg_ms_per_frame']:<15.2f} {r['decode_ms_avg']:<15.1f} "
              f"{r['max_decode_ms']:<12} {r['total_frames']:<10}")

    print()
    print("关键发现:")
    print("-" * 40)

    # 分析低分辨率 vs 高分辨率
    low_res = [k for k in results.keys() if int(k.split('x')[1]) < 600]
    high_res = [k for k in results.keys() if int(k.split('x')[1]) >= 700]

    if low_res:
        low_avg = sum(results[r]['actual_avg_ms_per_frame'] for r in low_res) / len(low_res)
        print(f"低分辨率 (≤540p) 平均延迟: {low_avg:.2f} ms/帧")

    if high_res:
        high_avg = sum(results[r]['actual_avg_ms_per_frame'] for r in high_res) / len(high_res)
        print(f"高分辨率 (≥720p) 平均延迟: {high_avg:.2f} ms/帧")

    if low_res and high_res:
        ratio = high_avg / low_avg
        print(f"延迟增长倍数: {ratio:.2f}x")

    print()

    # 找出主要传输分辨率
    max_frames_res = max(results.items(), key=lambda x: x[1]['total_frames'])
    print(f"主要传输分辨率: {max_frames_res[0]} ({max_frames_res[1]['total_frames']} 帧)")
    print(f"主要分辨率解码延迟: {max_frames_res[1]['actual_avg_ms_per_frame']:.2f} ms/帧")


if __name__ == '__main__':
    main()
