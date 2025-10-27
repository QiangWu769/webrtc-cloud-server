#!/usr/bin/env python3
"""
WebRTC配置最终对比分析 - 包含1080p维持时间统计
对比指标：QP、FPS、Freeze数、未解码帧数、1080p维持时间
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 从PNG图片中准确读取的数据
data = {
    'GoogleCC2': {
        'avg_fps': 17.6,
        'avg_qp': 17.6,
        'total_freezes': 18,
        'total_undecodable': 1352,
        # 分辨率统计（从Resolution图中读取）
        'resolution_1080p_duration': 80,  # 秒 (从50秒到130秒)
        'final_resolution': '1920x1080',
        'achieved_1080p': True,
    },
    'Gain2': {
        'avg_fps': 22.3,
        'avg_qp': 12.3,
        'total_freezes': 14,
        'total_undecodable': 559,
        # 分辨率统计（从Resolution图中读取）
        'resolution_1080p_duration': 0,  # 秒 (未达到1920x1080，停留在1280x720)
        'final_resolution': '1280x720',
        'achieved_1080p': False,
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

# 打印详细对比表
print("\n" + "="*105)
print("WebRTC Configuration Comparison: GoogleCC2 vs GainController2")
print("Complete QoE Metrics with 1080p Resolution Duration Analysis")
print("="*105)

print(f"\n{'Metric':<45} {'GoogleCC2':>20} {'Gain2':>20} {'Improvement':>15}")
print("-"*105)

print("\n*** Core QoE Metrics ***")
print(f"{'Average FPS (higher better)':<45} {data['GoogleCC2']['avg_fps']:>20.1f} {data['Gain2']['avg_fps']:>20.1f} {improvements['avg_fps']:>+14.1f}%")
print(f"{'Average QP (lower better)':<45} {data['GoogleCC2']['avg_qp']:>20.1f} {data['Gain2']['avg_qp']:>20.1f} {improvements['avg_qp']:>+14.1f}%")
print(f"{'Total Video Freezes (lower better)':<45} {data['GoogleCC2']['total_freezes']:>20.0f} {data['Gain2']['total_freezes']:>20.0f} {improvements['total_freezes']:>+14.1f}%")
print(f"{'Total Undecodable Frames (lower better)':<45} {data['GoogleCC2']['total_undecodable']:>20.0f} {data['Gain2']['total_undecodable']:>20.0f} {improvements['total_undecodable']:>+14.1f}%")

print("\n*** Resolution Performance ***")
print(f"{'Final Resolution Achieved':<45} {data['GoogleCC2']['final_resolution']:>20} {data['Gain2']['final_resolution']:>20} {'GoogleCC2 Wins':>15}")
print(f"{'1080p Maintenance Duration (seconds)':<45} {data['GoogleCC2']['resolution_1080p_duration']:>20.0f} {data['Gain2']['resolution_1080p_duration']:>20.0f} {improvements['resolution_1080p_duration']:>+14.1f}%")
print(f"{'Reached 1080p?':<45} {'Yes':>20} {'No':>20} {'GoogleCC2 Wins':>15}")

print("\n" + "="*105)
print("\n*** Key Findings ***")
print("✓ Gain2 Performance Advantages:")
print(f"  • {abs(improvements['avg_fps']):.1f}% higher FPS ({data['Gain2']['avg_fps']:.1f} vs {data['GoogleCC2']['avg_fps']:.1f})")
print(f"  • {abs(improvements['avg_qp']):.1f}% better video quality (QP: {data['Gain2']['avg_qp']:.1f} vs {data['GoogleCC2']['avg_qp']:.1f})")
print(f"  • {abs(improvements['total_freezes']):.1f}% fewer freezes ({data['Gain2']['total_freezes']:.0f} vs {data['GoogleCC2']['total_freezes']:.0f})")
print(f"  • {abs(improvements['total_undecodable']):.1f}% fewer undecodable frames ({data['Gain2']['total_undecodable']:.0f} vs {data['GoogleCC2']['total_undecodable']:.0f})")

print("\n✗ Gain2 Resolution Limitation:")
print(f"  • Failed to reach 1920x1080 (stopped at {data['Gain2']['final_resolution']})")
print(f"  • GoogleCC2 maintained 1080p for {data['GoogleCC2']['resolution_1080p_duration']:.0f} seconds")
print(f"  • This is a CRITICAL limitation for high-quality video streaming!")

print("\n*** Trade-off Analysis ***")
print("GoogleCC2: Lower QoE metrics BUT achieves and maintains full HD (1920x1080)")
print("Gain2:     Better QoE metrics BUT limited to HD-ready (1280x720)")
print("Recommendation: Choose based on priority - resolution vs smoothness")
print("="*105 + "\n")

# 创建可视化对比图
plt.style.use('seaborn-v0_8-whitegrid')

color_gcc2 = '#E69F00'  # 橙色
color_gain2 = '#009E73'  # 绿色

fig = plt.figure(figsize=(20, 12))
gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.25, top=0.93, bottom=0.08, left=0.06, right=0.97)

fig.suptitle('WebRTC Complete Performance Comparison: GoogleCC2 vs GainController2\n(QoE Metrics + 1080p Resolution Duration)',
            fontsize=17, fontweight='bold', y=0.97)

# 定义5个指标
metrics = [
    ('Average FPS', 'avg_fps', 'FPS', True, 0, 0),
    ('Video Quality (QP)', 'avg_qp', 'QP Value', False, 0, 1),
    ('Total Freezes', 'total_freezes', 'Count', False, 0, 2),
    ('Undecodable Frames', 'total_undecodable', 'Frames', False, 1, 0),
    ('1080p Duration', 'resolution_1080p_duration', 'Seconds', True, 1, 1),
]

for idx, (title, metric_key, ylabel, higher_better, row, col) in enumerate(metrics):
    ax = fig.add_subplot(gs[row, col])

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
        if val >= 100:
            label_text = f'{val:.0f}'
        else:
            label_text = f'{val:.1f}'
        ax.text(bar.get_x() + bar.get_width()/2., height,
               label_text,
               ha='center', va='bottom', fontsize=15, fontweight='bold')

    # 设置标题和标签
    letter = chr(97 + idx)
    ax.set_title(f'({letter}) {title}',
                fontsize=13, fontweight='bold', pad=12, loc='left')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['GoogleCC2', 'Gain2'], fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax.set_ylim(bottom=0)

    # 添加改进百分比
    improvement_color = 'green' if improvement > 0 else 'red'
    improvement_symbol = '↑' if improvement > 0 else '↓'

    ax.text(0.5, 0.90, f'{improvement_symbol} {abs(improvement):.1f}%',
           transform=ax.transAxes,
           fontsize=13,
           fontweight='bold',
           ha='center',
           va='top',
           bbox=dict(boxstyle='round,pad=0.5',
                    facecolor=improvement_color,
                    alpha=0.25,
                    edgecolor=improvement_color,
                    linewidth=2.5))

    # 添加方向说明
    direction = 'Higher is Better' if higher_better else 'Lower is Better'
    ax.text(0.5, 0.05, direction,
           transform=ax.transAxes,
           fontsize=9,
           ha='center',
           style='italic',
           color='gray')

# 第6个子图：分辨率对比总结
ax6 = fig.add_subplot(gs[1, 2])
ax6.axis('off')

# 分辨率对比文本
resolution_text = (
    "Resolution Comparison\n\n"
    "GoogleCC2:\n"
    f"  • Final: {data['GoogleCC2']['final_resolution']} ✓\n"
    f"  • 1080p Duration: {data['GoogleCC2']['resolution_1080p_duration']:.0f}s\n"
    f"  • Achieved Full HD\n\n"
    "Gain2:\n"
    f"  • Final: {data['Gain2']['final_resolution']} ✗\n"
    f"  • 1080p Duration: {data['Gain2']['resolution_1080p_duration']:.0f}s\n"
    f"  • Limited to HD-ready\n\n"
    "Winner: GoogleCC2\n"
    "(Higher resolution capability)"
)

ax6.text(0.5, 0.5, resolution_text,
        transform=ax6.transAxes,
        fontsize=12,
        ha='center',
        va='center',
        bbox=dict(boxstyle='round,pad=1', facecolor='lightyellow', alpha=0.8, edgecolor='orange', linewidth=2))

ax6.set_title('(f) Resolution Performance',
             fontsize=13, fontweight='bold', pad=15, loc='left')

# 底部总结
summary_text = (
    f"Trade-off: Gain2 wins on QoE ({improvements['avg_fps']:+.1f}% FPS, {improvements['avg_qp']:+.1f}% QP, "
    f"{improvements['total_freezes']:+.1f}% freezes, {improvements['total_undecodable']:+.1f}% undecodable) "
    f"BUT GoogleCC2 achieves Full HD (1920x1080) while Gain2 limited to 1280x720"
)
fig.text(0.5, 0.02, summary_text, ha='center', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.7, edgecolor='blue', linewidth=1.5))

# 保存图表
output_dir = Path('analysis_results')
output_dir.mkdir(exist_ok=True)

output_path = output_dir / 'final_comparison_with_1080p_duration.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"[*] 包含1080p维持时间的最终对比图已保存到: {output_path}")

output_pdf = output_dir / 'final_comparison_with_1080p_duration.pdf'
fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
print(f"[*] PDF格式已保存到: {output_pdf}\n")

print("[✓] 完整分析完成！")
