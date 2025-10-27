#!/usr/bin/env python3
"""
WebRTC配置对比分析 - 包含分辨率统计
对比指标：QP、FPS、Freeze数、未解码帧数、分辨率
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
        # 分辨率统计 (从PNG图片的分辨率变化图中观察)
        # GoogleCC2: 从640x360逐步提升到1920x1080
        'resolution_sequence': '640x360 → 960x540 → 1280x720 → 1920x1080',
        'final_resolution': '1920x1080',
        'resolution_changes': 3,  # 分辨率切换次数
    },
    'Gain2': {
        'avg_fps': 22.3,
        'avg_qp': 12.3,
        'total_freezes': 14,
        'total_undecodable': 559,
        # 分辨率统计 (从PNG图片的分辨率变化图中观察)
        # Gain2: 从640x360逐步提升到1920x1080
        'resolution_sequence': '640x360 → 960x540 → 1280x720 → 1920x1080',
        'final_resolution': '1920x1080',
        'resolution_changes': 3,  # 分辨率切换次数
    }
}

# 计算改进百分比
improvements = {
    'avg_fps': ((data['Gain2']['avg_fps'] - data['GoogleCC2']['avg_fps']) / data['GoogleCC2']['avg_fps']) * 100,
    'avg_qp': ((data['GoogleCC2']['avg_qp'] - data['Gain2']['avg_qp']) / data['GoogleCC2']['avg_qp']) * 100,  # QP越低越好
    'total_freezes': ((data['GoogleCC2']['total_freezes'] - data['Gain2']['total_freezes']) / data['GoogleCC2']['total_freezes']) * 100,
    'total_undecodable': ((data['GoogleCC2']['total_undecodable'] - data['Gain2']['total_undecodable']) / data['GoogleCC2']['total_undecodable']) * 100,
}

# 打印详细对比表
print("\n" + "="*100)
print("WebRTC QoE Metrics Comparison with Resolution Statistics")
print("GoogleCC2 vs GainController2")
print("="*100)

print(f"\n{'Metric':<40} {'GoogleCC2':>20} {'Gain2':>20} {'Improvement':>15}")
print("-"*100)

print("\n*** Core QoE Metrics ***")
print(f"{'Average FPS (higher better)':<40} {data['GoogleCC2']['avg_fps']:>20.1f} {data['Gain2']['avg_fps']:>20.1f} {improvements['avg_fps']:>+14.1f}%")
print(f"{'Average QP (lower better)':<40} {data['GoogleCC2']['avg_qp']:>20.1f} {data['Gain2']['avg_qp']:>20.1f} {improvements['avg_qp']:>+14.1f}%")
print(f"{'Total Freezes (lower better)':<40} {data['GoogleCC2']['total_freezes']:>20.0f} {data['Gain2']['total_freezes']:>20.0f} {improvements['total_freezes']:>+14.1f}%")
print(f"{'Undecodable Frames (lower better)':<40} {data['GoogleCC2']['total_undecodable']:>20.0f} {data['Gain2']['total_undecodable']:>20.0f} {improvements['total_undecodable']:>+14.1f}%")

print("\n*** Resolution Statistics ***")
print(f"{'Final Resolution':<40} {data['GoogleCC2']['final_resolution']:>20} {data['Gain2']['final_resolution']:>20} {'Same':>15}")
print(f"{'Resolution Changes':<40} {data['GoogleCC2']['resolution_changes']:>20} {data['Gain2']['resolution_changes']:>20} {'Same':>15}")
print(f"{'Resolution Path':<40}")
print(f"  GoogleCC2: {data['GoogleCC2']['resolution_sequence']}")
print(f"  Gain2:     {data['Gain2']['resolution_sequence']}")

print("\n" + "="*100)
print("\n*** Conclusion ***")
print(f"✓ Gain2 achieves SIGNIFICANTLY BETTER performance across all key QoE metrics:")
print(f"  • {abs(improvements['avg_fps']):.1f}% higher FPS (smoother video)")
print(f"  • {abs(improvements['avg_qp']):.1f}% better video quality (lower QP)")
print(f"  • {abs(improvements['total_freezes']):.1f}% fewer freezes")
print(f"  • {abs(improvements['total_undecodable']):.1f}% fewer undecodable frames")
print(f"✓ Both configurations achieve the same final resolution (1920x1080)")
print(f"✓ Gain2 delivers superior user experience while maintaining same resolution capability")
print("="*100 + "\n")

# 创建可视化对比图
plt.style.use('seaborn-v0_8-whitegrid')

color_gcc2 = '#E69F00'  # 橙色
color_gain2 = '#009E73'  # 绿色

fig = plt.figure(figsize=(18, 10))
gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.25, top=0.93, bottom=0.08, left=0.06, right=0.97)

fig.suptitle('WebRTC QoE Metrics Comparison: GoogleCC2 vs GainController2\n(FPS, QP, Freezes, Undecodable Frames, Resolution)',
            fontsize=17, fontweight='bold', y=0.97)

# 定义5个指标（前4个是数值，第5个是分辨率文本）
metrics = [
    ('Average Frame Rate', 'avg_fps', 'FPS', True, 0, 0),
    ('Video Quality (QP)', 'avg_qp', 'QP Value', False, 0, 1),
    ('Total Freezes', 'total_freezes', 'Count', False, 0, 2),
    ('Undecodable Frames', 'total_undecodable', 'Frames', False, 1, 0),
]

# 绘制前4个数值指标
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

# 第5个子图：分辨率对比（文本表格形式）
ax5 = fig.add_subplot(gs[1, 1:])
ax5.axis('off')

# 创建分辨率对比表格
table_data = [
    ['Configuration', 'Resolution Path', 'Final Resolution', 'Changes'],
    ['GoogleCC2', '640x360 → 960x540 → 1280x720 → 1920x1080', '1920x1080', '3'],
    ['Gain2', '640x360 → 960x540 → 1280x720 → 1920x1080', '1920x1080', '3'],
]

table = ax5.table(cellText=table_data,
                 cellLoc='left',
                 loc='center',
                 colWidths=[0.15, 0.55, 0.15, 0.15])

table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1, 2.5)

# 设置表头样式
for i in range(4):
    cell = table[(0, i)]
    cell.set_facecolor('#404040')
    cell.set_text_props(weight='bold', color='white')

# 设置配置行颜色
table[(1, 0)].set_facecolor(matplotlib.colors.to_rgba(color_gcc2, 0.3))
table[(2, 0)].set_facecolor(matplotlib.colors.to_rgba(color_gain2, 0.3))

for i in range(4):
    table[(1, i)].set_edgecolor('black')
    table[(2, i)].set_edgecolor('black')
    table[(1, i)].set_linewidth(1.5)
    table[(2, i)].set_linewidth(1.5)

ax5.set_title('(e) Resolution Statistics',
             fontsize=13, fontweight='bold', pad=15, loc='left')

# 添加分辨率结论文本
conclusion_text = "Both configurations achieve same resolution capability (1920x1080)\nwith identical adaptation path"
ax5.text(0.5, 0.05, conclusion_text,
        transform=ax5.transAxes,
        fontsize=10,
        ha='center',
        style='italic',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightblue', alpha=0.4))

# 底部总结
summary_text = (
    f"Summary: Gain2 outperforms GoogleCC2 with {improvements['avg_fps']:+.1f}% FPS, "
    f"{improvements['avg_qp']:+.1f}% QP quality, "
    f"{improvements['total_freezes']:+.1f}% freezes, "
    f"{improvements['total_undecodable']:+.1f}% undecodable frames\n"
    f"while maintaining identical resolution capabilities (both reach 1920x1080)"
)
fig.text(0.5, 0.02, summary_text, ha='center', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.7, edgecolor='orange', linewidth=1.5))

# 保存图表
output_dir = Path('analysis_results')
output_dir.mkdir(exist_ok=True)

output_path = output_dir / 'qoe_comparison_with_resolution.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"[*] 包含分辨率统计的对比图已保存到: {output_path}")

output_pdf = output_dir / 'qoe_comparison_with_resolution.pdf'
fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
print(f"[*] PDF格式已保存到: {output_pdf}\n")

print("[✓] 分析完成！")
