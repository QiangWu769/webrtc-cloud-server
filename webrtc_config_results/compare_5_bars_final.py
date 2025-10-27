#!/usr/bin/env python3
"""
最终正确的5柱状图对比 - 淡蓝色和深蓝色
基于仔细观察两张分辨率图的准确数据
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 最终正确的数据
# GoogleCC2: 达到1920x1080并维持约50秒 (50s-100s)
# Gain2: 最高到1280x720，维持约60秒 (40s-100s)
data = {
    'GoogleCC2': {
        'avg_fps': 17.6,
        'avg_qp': 17.6,
        'total_freezes': 18,
        'total_undecodable': 1352,
        'resolution_1080p_duration': 50,  # 1920x1080维持约50秒
        'max_resolution': '1920x1080',
    },
    'Gain2': {
        'avg_fps': 22.3,
        'avg_qp': 12.3,
        'total_freezes': 14,
        'total_undecodable': 559,
        'resolution_1080p_duration': 0,  # 未达到1920x1080，最高720p维持60秒
        'max_resolution': '1280x720',
    }
}

# 计算改进百分比
improvements = {
    'avg_fps': ((data['Gain2']['avg_fps'] - data['GoogleCC2']['avg_fps']) / data['GoogleCC2']['avg_fps']) * 100,
    'avg_qp': ((data['GoogleCC2']['avg_qp'] - data['Gain2']['avg_qp']) / data['GoogleCC2']['avg_qp']) * 100,
    'total_freezes': ((data['GoogleCC2']['total_freezes'] - data['Gain2']['total_freezes']) / data['GoogleCC2']['total_freezes']) * 100,
    'total_undecodable': ((data['GoogleCC2']['total_undecodable'] - data['Gain2']['total_undecodable']) / data['GoogleCC2']['total_undecodable']) * 100,
    'resolution_1080p_duration': ((data['Gain2']['resolution_1080p_duration'] - data['GoogleCC2']['resolution_1080p_duration']) / data['GoogleCC2']['resolution_1080p_duration']) * 100 if data['GoogleCC2']['resolution_1080p_duration'] > 0 else -100,
}

print("\n" + "="*110)
print("最终正确数据对比 - GoogleCC2 vs Gain2")
print("="*110)
print(f"\n{'Metric':<45} {'GoogleCC2':>22} {'Gain2':>22} {'Improvement':>15}")
print("-"*110)
print("\n*** QoE Metrics (Quality of Experience) ***")
print(f"{'Average FPS (higher better)':<45} {data['GoogleCC2']['avg_fps']:>22.1f} {data['Gain2']['avg_fps']:>22.1f} {improvements['avg_fps']:>+14.1f}%")
print(f"{'Average QP (lower better)':<45} {data['GoogleCC2']['avg_qp']:>22.1f} {data['Gain2']['avg_qp']:>22.1f} {improvements['avg_qp']:>+14.1f}%")
print(f"{'Total Video Freezes (lower better)':<45} {data['GoogleCC2']['total_freezes']:>22.0f} {data['Gain2']['total_freezes']:>22.0f} {improvements['total_freezes']:>+14.1f}%")
print(f"{'Total Undecodable Frames (lower better)':<45} {data['GoogleCC2']['total_undecodable']:>22.0f} {data['Gain2']['total_undecodable']:>22.0f} {improvements['total_undecodable']:>+14.1f}%")

print("\n*** Resolution Performance ***")
print(f"{'Maximum Resolution Achieved':<45} {data['GoogleCC2']['max_resolution']:>22} {data['Gain2']['max_resolution']:>22} {'GoogleCC2':>15}")
print(f"{'1080p Maintenance Duration (seconds)':<45} {data['GoogleCC2']['resolution_1080p_duration']:>22.0f} {data['Gain2']['resolution_1080p_duration']:>22.0f} {improvements['resolution_1080p_duration']:>+14.1f}%")

print("\n" + "="*110)
print("\n*** 关键发现 ***")
print("\n✅ Gain2在所有QoE指标上全面优胜:")
print(f"   • FPS提升: {improvements['avg_fps']:.1f}% (22.3 vs 17.6)")
print(f"   • QP改善: {improvements['avg_qp']:.1f}% (12.3 vs 17.6，越低越好)")
print(f"   • 冻结减少: {improvements['total_freezes']:.1f}% (14 vs 18)")
print(f"   • 未解码帧减少: {improvements['total_undecodable']:.1f}% (559 vs 1352)")

print("\n❌ Gain2的分辨率劣势:")
print(f"   • GoogleCC2: 达到并维持1920x1080约50秒")
print(f"   • Gain2: 最高仅达到1280x720 (未达到Full HD)")

print("\n*** 权衡分析 ***")
print("选择GoogleCC2: 如果必须要Full HD (1920x1080)分辨率")
print("选择Gain2:     如果优先考虑流畅度和稳定性 (推荐！)")
print("="*110 + "\n")

# 颜色 - 淡蓝色和深蓝色
color_light_blue = '#87CEEB'  # 淡蓝色 - GoogleCC2
color_dark_blue = '#1E90FF'   # 深蓝色 - Gain2

# 创建图表 - 1行5列
fig, axes = plt.subplots(1, 5, figsize=(20, 5))

# 5个指标
metrics = [
    ('Average FPS', 'avg_fps', 'FPS', True),
    ('Average QP', 'avg_qp', 'QP', False),
    ('Total Freezes', 'total_freezes', 'Count', False),
    ('Undecodable Frames', 'total_undecodable', 'Frames', False),
    ('1080p Duration', 'resolution_1080p_duration', 'Seconds', True),
]

for idx, (title, metric_key, ylabel, higher_better) in enumerate(metrics):
    ax = axes[idx]

    val_gcc2 = data['GoogleCC2'][metric_key]
    val_gain2 = data['Gain2'][metric_key]
    improvement = improvements[metric_key]

    # 绘制柱状图
    bars = ax.bar([0, 1], [val_gcc2, val_gain2],
                   color=[color_light_blue, color_dark_blue],
                   alpha=0.9,
                   edgecolor='black',
                   linewidth=1.5,
                   width=0.6)

    # 添加数值标签
    for i, (bar, val) in enumerate(zip(bars, [val_gcc2, val_gain2])):
        height = bar.get_height()
        if val >= 100:
            label_text = f'{val:.0f}'
        else:
            label_text = f'{val:.1f}'
        ax.text(bar.get_x() + bar.get_width()/2., height,
                label_text,
                ha='center', va='bottom', fontsize=14, fontweight='bold')

    # 设置标题和标签
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['GoogleCC2', 'Gain2'], fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax.set_ylim(bottom=0)

    # 添加改进百分比标注
    improvement_color = 'green' if improvement > 0 else 'red'
    improvement_symbol = '↑' if improvement > 0 else '↓'

    ax.text(0.5, 0.92, f'{improvement_symbol} {abs(improvement):.1f}%',
            transform=ax.transAxes,
            fontsize=11,
            fontweight='bold',
            ha='center',
            va='top',
            bbox=dict(boxstyle='round,pad=0.4',
                     facecolor=improvement_color,
                     alpha=0.2,
                     edgecolor=improvement_color,
                     linewidth=2))

plt.tight_layout()

# 保存图表
output_dir = Path('analysis_results')
output_dir.mkdir(exist_ok=True)

output_path = output_dir / 'comparison_5_bars_final.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"[*] 最终5柱状图已保存到: {output_path}")

output_pdf = output_dir / 'comparison_5_bars_final.pdf'
fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
print(f"[*] PDF格式已保存到: {output_pdf}\n")

print("[✓] 分析完成！")
