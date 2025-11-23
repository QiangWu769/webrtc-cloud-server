#!/usr/bin/env python3
"""
计算 Switching Rate (分辨率切换率)

Switching Rate = 相邻 segment 之间分辨率切换的次数 / (总 segment 数 - 1)

用法:
    python3 calculate_switching_rate.py <log_file>
"""

import re
import sys
from collections import defaultdict, Counter


def resolution_to_rung(w, h):
    """将分辨率映射到档位"""
    if h >= 900:      # ~1080p
        return 3
    elif h >= 700:    # ~720p
        return 2
    elif h >= 500:    # ~540p
        return 1
    else:             # <= 480p/360p
        return 0


def calculate_switching_rate(log_file, segment_duration=2.0):
    """
    从 WebRTC 日志计算 Switching Rate

    Args:
        log_file: WebRTC 日志文件路径
        segment_duration: 每个 segment 的时长（秒），默认 2.0

    Returns:
        dict: 包含 switching rate 和详细统计信息
    """
    # 读取日志
    with open(log_file, 'r') as f:
        log_content = f.read()

    # 提取采样点数据
    pattern = r'VideoReceiveStreamInterface stats: (\d+),.*?frameWidth: (\d+), frameHeight: (\d+).*?framesDecoded: (\d+)'
    matches = re.findall(pattern, log_content, re.DOTALL)

    samples = []
    for match in matches:
        timestamp = int(match[0])
        width = int(match[1])
        height = int(match[2])
        frames = int(match[3])

        if width > 0 and height > 0 and frames > 0:
            samples.append({
                'timestamp': timestamp,
                'width': width,
                'height': height,
                'frames': frames,
                'rung': resolution_to_rung(width, height)
            })

    if not samples:
        return None

    # 计算实际传输时长（基于帧数）
    total_frames = samples[-1]['frames']
    actual_duration = total_frames / 30.0  # 假设 30 fps

    # 为每个采样点分配归一化时间和 segment
    for sample in samples:
        sample['time_s'] = (sample['frames'] / total_frames) * actual_duration
        sample['segment'] = int(sample['time_s'] // segment_duration)

    # 每个 segment 取多数票决定档位
    segments = defaultdict(list)
    for sample in samples:
        seg_idx = sample['segment']
        segments[seg_idx].append(sample['rung'])

    N = int(actual_duration / segment_duration)  # 总 segment 数

    rung_seq = []
    for i in range(N):
        if i not in segments:
            if i == 0:
                rung_seq.append(0)
            else:
                rung_seq.append(rung_seq[-1])
        else:
            rungs = segments[i]
            rung = Counter(rungs).most_common(1)[0][0]
            rung_seq.append(rung)

    # 计算 Switching Rate
    N_switch = sum(1 for i in range(N-1) if rung_seq[i+1] != rung_seq[i])
    p_switch = N_switch / (N - 1) if N > 1 else 0.0

    # 统计各档位占比
    rung_counts = Counter(rung_seq)
    rung_names = {0: "360p", 1: "540p", 2: "720p", 3: "1080p"}

    return {
        'switching_rate': p_switch,
        'total_segments': N,
        'switch_count': N_switch,
        'transmission_duration': actual_duration,
        'total_frames': total_frames,
        'rung_sequence': rung_seq,
        'rung_distribution': {rung_names[r]: count for r, count in rung_counts.items()}
    }


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <log_file>")
        sys.exit(1)

    log_file = sys.argv[1]

    print("=" * 80)
    print("Switching Rate 计算")
    print("=" * 80)
    print()

    result = calculate_switching_rate(log_file)

    if not result:
        print("错误: 未能从日志中提取有效数据")
        sys.exit(1)

    print(f"实际传输时长: {result['transmission_duration']:.1f} 秒")
    print(f"总 Segment 数 (N): {result['total_segments']}")
    print(f"切换次数 (N_switch): {result['switch_count']}")
    print(f"Switching Rate: {result['switching_rate']:.4f} ({result['switching_rate']*100:.2f}%)")
    print()

    print("各分辨率档位占比:")
    print("-" * 40)
    for resolution, count in sorted(result['rung_distribution'].items()):
        percentage = (count / result['total_segments']) * 100
        print(f"  {resolution}: {count} segments ({percentage:.1f}%)")
    print()

    # 评级
    if result['switching_rate'] < 0.10:
        print("✓ 评级: 优秀 (< 10%)")
    elif result['switching_rate'] < 0.20:
        print("✓ 评级: 良好 (10-20%)")
    elif result['switching_rate'] < 0.30:
        print("⚠ 评级: 一般 (20-30%)")
    else:
        print("✗ 评级: 较差 (> 30%)")


if __name__ == '__main__':
    main()
