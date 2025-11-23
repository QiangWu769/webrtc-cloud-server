#!/usr/bin/env python3
"""
计算 Rebuffering Ratio (重缓冲率/卡顿率)

Rebuffering Ratio = T_rebuf / T_total
- T_rebuf: 视频冻结的总时长（秒）
- T_total: 视频总播放时长（秒）

用法:
    python3 calculate_rebuffering_ratio.py <log_file>
"""

import re
import sys


def calculate_rebuffering_ratio(log_file):
    """
    从 WebRTC 日志提取 Rebuffering Ratio

    WebRTC 日志中有专门的 VideoQuality 统计:
    - [VideoQuality-CoreFreeze]: 包含冻结次数、时长和 Rebuffering Ratio
    - [VideoQuality-FreezeRate]: 包含冻结和暂停的详细统计

    Args:
        log_file: WebRTC 日志文件路径

    Returns:
        dict: 包含 rebuffering ratio 和详细统计信息
    """
    # 读取日志
    with open(log_file, 'r') as f:
        log_content = f.read()

    # 提取 VideoQuality-CoreFreeze 数据
    pattern_core = r'\[VideoQuality-CoreFreeze\].*?MonoTime: (\d+).*?Freeze Count: (\d+), Total Freeze Duration \(ms\): ([\d.]+), Rebuffering Ratio: ([\d.]+), Playback Duration \(ms\): ([\d.]+)'
    matches_core = re.findall(pattern_core, log_content)

    # 提取 VideoQuality-FreezeRate 数据
    pattern_rate = r'\[VideoQuality-FreezeRate\].*?MonoTime: (\d+).*?Freeze Count: (\d+), Total Freezes Duration \(ms\): ([\d.]+), Pause Count: (\d+), Total Pauses Duration \(ms\): ([\d.]+)'
    matches_rate = re.findall(pattern_rate, log_content)

    if not matches_core or not matches_rate:
        return None

    # 获取最终统计数据
    last_core = matches_core[-1]
    last_rate = matches_rate[-1]

    freeze_count = int(last_core[1])
    total_freeze_duration_ms = float(last_core[2])
    rebuffering_ratio = float(last_core[3])
    playback_duration_ms = float(last_core[4])

    pause_count = int(last_rate[3])
    total_pause_duration_ms = float(last_rate[4])

    return {
        'rebuffering_ratio': rebuffering_ratio,
        'freeze_count': freeze_count,
        'total_freeze_duration_sec': total_freeze_duration_ms / 1000.0,
        'pause_count': pause_count,
        'total_pause_duration_sec': total_pause_duration_ms / 1000.0,
        'playback_duration_sec': playback_duration_ms / 1000.0,
        'total_samples_core': len(matches_core),
        'total_samples_rate': len(matches_rate)
    }


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <log_file>")
        sys.exit(1)

    log_file = sys.argv[1]

    print("=" * 80)
    print("Rebuffering Ratio 计算")
    print("=" * 80)
    print()

    result = calculate_rebuffering_ratio(log_file)

    if not result:
        print("错误: 未能从日志中提取 VideoQuality 统计数据")
        print("提示: 请确保日志中包含 [VideoQuality-CoreFreeze] 和 [VideoQuality-FreezeRate] 统计")
        sys.exit(1)

    print("核心指标:")
    print("-" * 40)
    print(f"T_total (总播放时长):  {result['playback_duration_sec']:.2f} 秒")
    print(f"T_rebuf (冻结时间):    {result['total_freeze_duration_sec']:.2f} 秒")
    print(f"ρ_rebuf (重缓冲率):    {result['rebuffering_ratio']:.4f} ({result['rebuffering_ratio']*100:.2f}%)")
    print()

    print("详细统计:")
    print("-" * 40)
    print(f"冻结次数:    {result['freeze_count']}")
    print(f"暂停次数:    {result['pause_count']}")
    print(f"暂停时长:    {result['total_pause_duration_sec']:.2f} 秒")
    print()

    if result['freeze_count'] > 0:
        avg_freeze_duration = result['total_freeze_duration_sec'] / result['freeze_count']
        print(f"平均每次冻结: {avg_freeze_duration*1000:.0f} ms")
        print()

    # 评级
    ratio = result['rebuffering_ratio']
    if ratio == 0:
        print("✓ 评级: A+ (优秀) - 无卡顿")
    elif ratio < 0.01:
        print("✓ 评级: A (优秀) - 卡顿极少 (< 1%)")
    elif ratio < 0.05:
        print("✓ 评级: B (良好) - 卡顿较少 (1-5%)")
    elif ratio < 0.10:
        print("⚠ 评级: C (一般) - 有一定卡顿 (5-10%)")
    else:
        print("✗ 评级: D (较差) - 卡顿较多 (> 10%)")


if __name__ == '__main__':
    main()
