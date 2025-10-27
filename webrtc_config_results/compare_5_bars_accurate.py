#!/usr/bin/env python3
"""
准确的6柱状图对比 - 淡蓝色和深蓝色
GainFactor: 1080p维持30秒
GoogleCC: 1080p维持20秒
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 准确的数据
data = {
    'GoogleCC': {
        'avg_fps': 17.6,
        'avg_qp': 17.6,
        'total_freezes': 18,
        'total_undecodable': 1352,
        'resolution_1080p_duration': 20,  # 维持1080p 20秒
        'freeze_rate': 9.08,  # freeze rate 百分比
    },
    'GainFactor': {
        'avg_fps': 22.3,
        'avg_qp': 12.3,
        'total_freezes': 14,
        'total_undecodable': 559,
        'resolution_1080p_duration': 30,  # 维持1080p 30秒
        'freeze_rate': 5.68,  # freeze rate 百分比
    }
}

# 计算改进百分比
improvements = {
    'avg_fps': ((data['GainFactor']['avg_fps'] - data['GoogleCC']['avg_fps']) / data['GoogleCC']['avg_fps']) * 100,
    'avg_qp': ((data['GoogleCC']['avg_qp'] - data['GainFactor']['avg_qp']) / data['GoogleCC']['avg_qp']) * 100,
    'total_freezes': ((data['GoogleCC']['total_freezes'] - data['GainFactor']['total_freezes']) / data['GoogleCC']['total_freezes']) * 100,
    'total_undecodable': ((data['GoogleCC']['total_undecodable'] - data['GainFactor']['total_undecodable']) / data['GoogleCC']['total_undecodable']) * 100,
    'resolution_1080p_duration': ((data['GainFactor']['resolution_1080p_duration'] - data['GoogleCC']['resolution_1080p_duration']) / data['GoogleCC']['resolution_1080p_duration']) * 100,
    'freeze_rate': ((data['GoogleCC']['freeze_rate'] - data['GainFactor']['freeze_rate']) / data['GoogleCC']['freeze_rate']) * 100,
}

print("\n" + "="*100)
print("准确数据对比 - GoogleCC vs GainFactor")
print("="*100)
print(f"\n{'Metric':<40} {'GoogleCC':>20} {'GainFactor':>20} {'Improvement':>15}")
print("-"*100)
print("\n*** QoE Metrics ***")
print(f"{'Average FPS (higher better)':<40} {data['GoogleCC']['avg_fps']:>20.1f} {data['GainFactor']['avg_fps']:>20.1f} {improvements['avg_fps']:>+14.1f}%")
print(f"{'Average QP (lower better)':<40} {data['GoogleCC']['avg_qp']:>20.1f} {data['GainFactor']['avg_qp']:>20.1f} {improvements['avg_qp']:>+14.1f}%")
print(f"{'Total Freezes (lower better)':<40} {data['GoogleCC']['total_freezes']:>20.0f} {data['GainFactor']['total_freezes']:>20.0f} {improvements['total_freezes']:>+14.1f}%")
print(f"{'Freeze Rate % (lower better)':<40} {data['GoogleCC']['freeze_rate']:>20.2f} {data['GainFactor']['freeze_rate']:>20.2f} {improvements['freeze_rate']:>+14.1f}%")
print(f"{'Undecodable Frames (lower better)':<40} {data['GoogleCC']['total_undecodable']:>20.0f} {data['GainFactor']['total_undecodable']:>20.0f} {improvements['total_undecodable']:>+14.1f}%")
print("\n*** Resolution ***")
print(f"{'1080p Duration (seconds)':<40} {data['GoogleCC']['resolution_1080p_duration']:>20.0f} {data['GainFactor']['resolution_1080p_duration']:>20.0f} {improvements['resolution_1080p_duration']:>+14.1f}%")

print("\n" + "="*100)
print("\n*** 总结 ***")
print("✅ GainFactor在QoE指标上全面优胜:")
print(f"   FPS: +{improvements['avg_fps']:.1f}% | QP: +{improvements['avg_qp']:.1f}% | Freezes: +{improvements['total_freezes']:.1f}% | Freeze Rate: +{improvements['freeze_rate']:.1f}% | Undecodable: +{improvements['total_undecodable']:.1f}%")
print("\n✅ GainFactor在1080p维持时间上更优:")
print(f"   GainFactor维持1080p 30秒，GoogleCC维持1080p 20秒 (多50%)")
print("\n结论: GainFactor在用户体验质量和1080p稳定性上都显著更优")
print("="*100 + "\n")

# 颜色 - 淡蓝色和深蓝色
color_light_blue = '#87CEEB'  # 淡蓝色 - GoogleCC
color_dark_blue = '#1E90FF'   # 深蓝色 - GainFactor

# 创建图表 - 6行1列（竖直排列）
fig, axes = plt.subplots(6, 1, figsize=(12, 36))

# 6个指标
metrics = [
    ('Average FPS', 'avg_fps', 'FPS', True),
    ('Average QP', 'avg_qp', 'QP', False),
    ('Total Freezes', 'total_freezes', 'Count', False),
    ('Freeze Rate', 'freeze_rate', 'Percentage (%)', False),
    ('Undecodable Frames', 'total_undecodable', 'Frames', False),
    ('1080p Duration', 'resolution_1080p_duration', 'Seconds', True),
]

for idx, (title, metric_key, ylabel, higher_better) in enumerate(metrics):
    ax = axes[idx]

    val_gcc = data['GoogleCC'][metric_key]
    val_gain = data['GainFactor'][metric_key]
    improvement = improvements[metric_key]

    # 绘制柱状图
    bars = ax.bar([0, 1], [val_gcc, val_gain],
                   color=[color_light_blue, color_dark_blue],
                   alpha=0.9,
                   edgecolor='black',
                   linewidth=1.5,
                   width=0.6)

    # 添加数值标签
    for i, (bar, val) in enumerate(zip(bars, [val_gcc, val_gain])):
        height = bar.get_height()
        if val >= 100:
            label_text = f'{val:.0f}'
        else:
            label_text = f'{val:.2f}' if metric_key == 'freeze_rate' else f'{val:.1f}'
        ax.text(bar.get_x() + bar.get_width()/2., height,
                label_text,
                ha='center', va='bottom', fontsize=14, fontweight='bold')

    # 设置标题和标签
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['GoogleCC', 'GainFactor'], fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax.set_ylim(bottom=0)

    # 添加改进百分比标注
    # 对于"越低越好"的指标，改进应该显示向下箭头
    if higher_better:
        # 越高越好：improvement > 0 显示向上箭头
        improvement_color = 'green' if improvement > 0 else 'red'
        improvement_symbol = '↑' if improvement > 0 else '↓'
        improvement_text = f'{improvement_symbol} {abs(improvement):.1f}%'
    else:
        # 越低越好：improvement > 0 表示降低，显示向下箭头
        improvement_color = 'green' if improvement > 0 else 'red'
        improvement_symbol = '↓' if improvement > 0 else '↑'
        # 对于越低越好的指标，显示"下降XX%"
        if improvement > 0:
            improvement_text = f'{improvement_symbol} 下降 {abs(improvement):.1f}%'
        else:
            improvement_text = f'{improvement_symbol} 上升 {abs(improvement):.1f}%'

    ax.text(0.5, 0.92, improvement_text,
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

plt.tight_layout(pad=4.0, h_pad=6.0)

# 保存图表
output_dir = Path('analysis_results')
output_dir.mkdir(exist_ok=True)

output_path = output_dir / 'comparison_6_bars_accurate.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"[*] 准确的6柱状图已保存到: {output_path}")

output_pdf = output_dir / 'comparison_6_bars_accurate.pdf'
fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
print(f"[*] PDF格式已保存到: {output_pdf}\n")

print("[✓] 完成！")
