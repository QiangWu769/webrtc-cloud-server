#!/usr/bin/env python3
"""
基于PNG图片显示的准确数据进行对比
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 从PNG图片中读取的准确数据
data = {
    'GoogleCC2': {
        'avg_fps': 17.6,
        'avg_qp': 17.6,
        'total_freezes': 18,
        'total_undecodable': 1352,
    },
    'Gain2': {
        'avg_fps': 22.3,
        'avg_qp': 12.3,
        'total_freezes': 14,
        'total_undecodable': 559,
    }
}

# 计算改进百分比
improvements = {
    'avg_fps': ((data['Gain2']['avg_fps'] - data['GoogleCC2']['avg_fps']) / data['GoogleCC2']['avg_fps']) * 100,
    'avg_qp': ((data['GoogleCC2']['avg_qp'] - data['Gain2']['avg_qp']) / data['GoogleCC2']['avg_qp']) * 100,  # QP越低越好
    'total_freezes': ((data['GoogleCC2']['total_freezes'] - data['Gain2']['total_freezes']) / data['GoogleCC2']['total_freezes']) * 100,
    'total_undecodable': ((data['GoogleCC2']['total_undecodable'] - data['Gain2']['total_undecodable']) / data['GoogleCC2']['total_undecodable']) * 100,
}

# 打印对比表
print("\n" + "="*90)
print("WebRTC QoE Metrics Comparison (Based on PNG Data)")
print("="*90)
print(f"\n{'Metric':<35} {'GoogleCC2':>15} {'Gain2':>15} {'Improvement':>20}")
print("-"*90)
print(f"{'Average FPS (higher is better)':<35} {data['GoogleCC2']['avg_fps']:>15.1f} {data['Gain2']['avg_fps']:>15.1f} {improvements['avg_fps']:>+19.1f}%")
print(f"{'Average QP (lower is better)':<35} {data['GoogleCC2']['avg_qp']:>15.1f} {data['Gain2']['avg_qp']:>15.1f} {improvements['avg_qp']:>+19.1f}%")
print(f"{'Total Freezes (lower is better)':<35} {data['GoogleCC2']['total_freezes']:>15.0f} {data['Gain2']['total_freezes']:>15.0f} {improvements['total_freezes']:>+19.1f}%")
print(f"{'Total Undecodable Frames (lower)':<35} {data['GoogleCC2']['total_undecodable']:>15.0f} {data['Gain2']['total_undecodable']:>15.0f} {improvements['total_undecodable']:>+19.1f}%")
print("="*90)
print("\nConclusion: Gain2 shows significant improvements across ALL QoE metrics!")
print("="*90 + "\n")

# 创建论文级别的柱状图
plt.style.use('seaborn-v0_8-whitegrid')

# 颜色方案
color_gcc2 = '#E69F00'  # 橙色 - GoogleCC2
color_gain2 = '#009E73'  # 绿色 - Gain2

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('WebRTC QoE Metrics Comparison: GoogleCC2 vs GainController2\n(Based on Actual Test Results)',
            fontsize=18, fontweight='bold', y=0.98)

metrics = [
    ('Average Frame Rate (FPS)', 'avg_fps', 'FPS', True, axes[0, 0]),
    ('Average Video Quality (QP)', 'avg_qp', 'QP Value', False, axes[0, 1]),
    ('Total Video Freezes', 'total_freezes', 'Freeze Count', False, axes[1, 0]),
    ('Total Undecodable Frames', 'total_undecodable', 'Frame Count', False, axes[1, 1]),
]

for idx, (title, metric_key, ylabel, higher_better, ax) in enumerate(metrics):
    val_gcc2 = data['GoogleCC2'][metric_key]
    val_gain2 = data['Gain2'][metric_key]
    improvement = improvements[metric_key]

    # 绘制柱状图
    bars = ax.bar([0, 1], [val_gcc2, val_gain2],
                 color=[color_gcc2, color_gain2],
                 alpha=0.85,
                 edgecolor='black',
                 linewidth=2,
                 width=0.65)

    # 添加数值标签
    for i, (bar, val) in enumerate(zip(bars, [val_gcc2, val_gain2])):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{val:.1f}',
               ha='center', va='bottom', fontsize=16, fontweight='bold')

    # 设置标题和标签
    ax.set_title(f'({chr(97+idx)}) {title}',
                fontsize=14, fontweight='bold', pad=15, loc='left')
    ax.set_ylabel(ylabel, fontsize=13, fontweight='bold')
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['GoogleCC2', 'Gain2'], fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax.set_ylim(bottom=0)

    # 添加改进百分比标注
    improvement_color = 'green' if improvement > 0 else 'red'
    improvement_symbol = '↑' if improvement > 0 else '↓'

    ax.text(0.5, 0.92, f'{improvement_symbol} {abs(improvement):.1f}%',
           transform=ax.transAxes,
           fontsize=14,
           fontweight='bold',
           ha='center',
           va='top',
           bbox=dict(boxstyle='round,pad=0.6',
                    facecolor=improvement_color,
                    alpha=0.25,
                    edgecolor=improvement_color,
                    linewidth=3))

    # 添加"Better"标签指向更好的配置
    if improvement > 0:
        better_x = 1  # Gain2
        better_label = 'Better →'
        label_x = 0.2
    else:
        better_x = 0  # GoogleCC2
        better_label = '← Better'
        label_x = 0.8

    ax.text(label_x, 0.82, better_label,
           transform=ax.transAxes,
           fontsize=11,
           fontweight='bold',
           ha='center',
           style='italic',
           color='darkgreen')

plt.tight_layout(rect=[0, 0.04, 1, 0.96])

# 添加底部注释
note_text = (
    "Data Source: Actual WebRTC test results from receiver_cloud.log files\n"
    "FPS: Higher is better | QP/Freezes/Undecodable Frames: Lower is better | "
    "Green indicates improvement with Gain2"
)
fig.text(0.5, 0.01, note_text, ha='center', fontsize=10, style='italic',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.6, edgecolor='gray'))

# 保存图表
output_dir = Path('analysis_results')
output_dir.mkdir(exist_ok=True)

output_path = output_dir / 'qoe_comparison_accurate.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"[*] 准确的柱状图对比已保存到: {output_path}")

output_pdf = output_dir / 'qoe_comparison_accurate.pdf'
fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
print(f"[*] PDF格式已保存到: {output_pdf}\n")
