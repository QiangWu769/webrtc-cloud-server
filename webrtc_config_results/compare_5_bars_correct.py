#!/usr/bin/env python3
"""
正确的5柱状图对比 - 淡蓝色和深蓝色
基于准确的分辨率数据
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 正确的数据
data = {
    'GoogleCC2': {
        'avg_fps': 17.6,
        'avg_qp': 17.6,
        'total_freezes': 18,
        'total_undecodable': 1352,
        'resolution_1080p_duration': 20,  # 修正：仅维持约20秒，然后降回720p
    },
    'Gain2': {
        'avg_fps': 22.3,
        'avg_qp': 12.3,
        'total_freezes': 14,
        'total_undecodable': 559,
        'resolution_1080p_duration': 0,  # 未达到1080p，但720p维持80秒
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

print("\n" + "="*100)
print("修正后的数据对比")
print("="*100)
print(f"\n{'Metric':<40} {'GoogleCC2':>20} {'Gain2':>20} {'Improvement':>15}")
print("-"*100)
print(f"{'Average FPS':<40} {data['GoogleCC2']['avg_fps']:>20.1f} {data['Gain2']['avg_fps']:>20.1f} {improvements['avg_fps']:>+14.1f}%")
print(f"{'Average QP':<40} {data['GoogleCC2']['avg_qp']:>20.1f} {data['Gain2']['avg_qp']:>20.1f} {improvements['avg_qp']:>+14.1f}%")
print(f"{'Total Freezes':<40} {data['GoogleCC2']['total_freezes']:>20.0f} {data['Gain2']['total_freezes']:>20.0f} {improvements['total_freezes']:>+14.1f}%")
print(f"{'Undecodable Frames':<40} {data['GoogleCC2']['total_undecodable']:>20.0f} {data['Gain2']['total_undecodable']:>20.0f} {improvements['total_undecodable']:>+14.1f}%")
print(f"{'1080p Duration (seconds)':<40} {data['GoogleCC2']['resolution_1080p_duration']:>20.0f} {data['Gain2']['resolution_1080p_duration']:>20.0f} {improvements['resolution_1080p_duration']:>+14.1f}%")
print("\n说明:")
print("  GoogleCC2: 达到1080p但仅维持约20秒，然后降回720p（分辨率不稳定）")
print("  Gain2:     未达到1080p，但稳定维持720p约80秒（分辨率稳定）")
print("="*100 + "\n")

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

output_path = output_dir / 'comparison_5_bars_corrected.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"[*] 修正后的5柱状图已保存到: {output_path}")

output_pdf = output_dir / 'comparison_5_bars_corrected.pdf'
fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
print(f"[*] PDF格式已保存到: {output_pdf}\n")

print("[✓] 完成！")
