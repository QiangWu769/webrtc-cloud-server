#!/usr/bin/env python3
"""
详细的WebRTC配置对比分析 - 包含帧率统计
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
        'avg_bitrate': 11836,  # kbps (从PNG读取)
        'avg_jitter': 25.4,    # ms (从PNG读取)
        'total_packet_loss': 468,  # 从PNG读取
    },
    'Gain2': {
        'avg_fps': 22.3,
        'avg_qp': 12.3,
        'total_freezes': 14,
        'total_undecodable': 559,
        'avg_bitrate': 10597,  # kbps (从PNG读取)
        'avg_jitter': 26.4,    # ms (从PNG读取)
        'total_packet_loss': 235,  # 从PNG读取
    }
}

# 计算改进百分比
def calculate_improvement(val1, val2, lower_is_better=False):
    """计算改进百分比"""
    if lower_is_better:
        # 对于越小越好的指标
        return ((val1 - val2) / val1) * 100 if val1 > 0 else 0
    else:
        # 对于越大越好的指标
        return ((val2 - val1) / val1) * 100 if val1 > 0 else 0

improvements = {
    'avg_fps': calculate_improvement(data['GoogleCC2']['avg_fps'], data['Gain2']['avg_fps'], False),
    'avg_qp': calculate_improvement(data['GoogleCC2']['avg_qp'], data['Gain2']['avg_qp'], True),
    'total_freezes': calculate_improvement(data['GoogleCC2']['total_freezes'], data['Gain2']['total_freezes'], True),
    'total_undecodable': calculate_improvement(data['GoogleCC2']['total_undecodable'], data['Gain2']['total_undecodable'], True),
    'avg_bitrate': calculate_improvement(data['GoogleCC2']['avg_bitrate'], data['Gain2']['avg_bitrate'], False),
    'avg_jitter': calculate_improvement(data['GoogleCC2']['avg_jitter'], data['Gain2']['avg_jitter'], True),
    'total_packet_loss': calculate_improvement(data['GoogleCC2']['total_packet_loss'], data['Gain2']['total_packet_loss'], True),
}

# 打印详细对比表
print("\n" + "="*100)
print("WebRTC Configuration Detailed Comparison: GoogleCC2 vs GainController2")
print("="*100)
print(f"\n{'Metric':<40} {'GoogleCC2':>18} {'Gain2':>18} {'Improvement':>20}")
print("-"*100)

# QoE指标
print("\n*** QoE Metrics (Quality of Experience) ***")
print(f"{'Average FPS (↑ better)':<40} {data['GoogleCC2']['avg_fps']:>18.1f} {data['Gain2']['avg_fps']:>18.1f} {improvements['avg_fps']:>+19.1f}%")
print(f"{'Average QP (↓ better)':<40} {data['GoogleCC2']['avg_qp']:>18.1f} {data['Gain2']['avg_qp']:>18.1f} {improvements['avg_qp']:>+19.1f}%")
print(f"{'Total Video Freezes (↓ better)':<40} {data['GoogleCC2']['total_freezes']:>18.0f} {data['Gain2']['total_freezes']:>18.0f} {improvements['total_freezes']:>+19.1f}%")
print(f"{'Total Undecodable Frames (↓ better)':<40} {data['GoogleCC2']['total_undecodable']:>18.0f} {data['Gain2']['total_undecodable']:>18.0f} {improvements['total_undecodable']:>+19.1f}%")

# QoS指标
print("\n*** QoS Metrics (Quality of Service - Network) ***")
print(f"{'Average Bitrate kbps (↑ better)':<40} {data['GoogleCC2']['avg_bitrate']:>18.0f} {data['Gain2']['avg_bitrate']:>18.0f} {improvements['avg_bitrate']:>+19.1f}%")
print(f"{'Average Jitter ms (↓ better)':<40} {data['GoogleCC2']['avg_jitter']:>18.1f} {data['Gain2']['avg_jitter']:>18.1f} {improvements['avg_jitter']:>+19.1f}%")
print(f"{'Total Packet Loss (↓ better)':<40} {data['GoogleCC2']['total_packet_loss']:>18.0f} {data['Gain2']['total_packet_loss']:>18.0f} {improvements['total_packet_loss']:>+19.1f}%")

print("\n" + "="*100)

# 统计Gain2的优势
positive_improvements = sum(1 for v in improvements.values() if v > 0)
total_metrics = len(improvements)

print(f"\n*** Summary ***")
print(f"Gain2 shows improvement in {positive_improvements}/{total_metrics} metrics ({positive_improvements/total_metrics*100:.1f}%)")
print(f"\nMost Significant Improvements:")
sorted_improvements = sorted(improvements.items(), key=lambda x: x[1], reverse=True)
for i, (metric, imp) in enumerate(sorted_improvements[:3], 1):
    metric_name = metric.replace('_', ' ').title()
    print(f"  {i}. {metric_name}: {imp:+.1f}%")

print("="*100 + "\n")

# 创建综合对比图
plt.style.use('seaborn-v0_8-whitegrid')

# 颜色方案
color_gcc2 = '#E69F00'  # 橙色
color_gain2 = '#009E73'  # 绿色

# 创建 2行3列的布局 - 前4个是主要QoE指标，后3个是次要指标
fig = plt.figure(figsize=(20, 13))
gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.3, top=0.93, bottom=0.08, left=0.06, right=0.97)

fig.suptitle('WebRTC Configuration Comprehensive Comparison: GoogleCC2 vs GainController2\n(Based on Actual Test Results)',
            fontsize=18, fontweight='bold', y=0.97)

# 定义所有指标
all_metrics = [
    ('Average FPS', 'avg_fps', 'FPS', False, 0, 0),
    ('Average QP', 'avg_qp', 'QP Value', True, 0, 1),
    ('Total Freezes', 'total_freezes', 'Count', True, 0, 2),
    ('Undecodable Frames', 'total_undecodable', 'Frames', True, 1, 0),
    ('Average Bitrate', 'avg_bitrate', 'kbps', False, 1, 1),
    ('Packet Loss', 'total_packet_loss', 'Packets', True, 1, 2),
]

for idx, (title, metric_key, ylabel, lower_better, row, col) in enumerate(all_metrics):
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
        # 根据数值大小调整格式
        if val >= 100:
            label_text = f'{val:.0f}'
        else:
            label_text = f'{val:.1f}'
        ax.text(bar.get_x() + bar.get_width()/2., height,
               label_text,
               ha='center', va='bottom', fontsize=14, fontweight='bold')

    # 设置标题和标签
    letter = chr(97 + idx)
    ax.set_title(f'({letter}) {title}',
                fontsize=13, fontweight='bold', pad=12, loc='left')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['GoogleCC2', 'Gain2'], fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax.set_ylim(bottom=0)

    # 添加改进百分比标注
    improvement_color = 'green' if improvement > 0 else 'red'
    improvement_symbol = '↑' if improvement > 0 else '↓'

    box_y = 0.90 if improvement > 0 else 0.85
    ax.text(0.5, box_y, f'{improvement_symbol} {abs(improvement):.1f}%',
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

    # 添加指标说明
    if lower_better:
        direction_text = 'Lower is Better'
    else:
        direction_text = 'Higher is Better'

    ax.text(0.5, 0.05, direction_text,
           transform=ax.transAxes,
           fontsize=9,
           ha='center',
           style='italic',
           color='gray')

# 添加底部综合说明
note_text = (
    f"Data Source: Actual WebRTC receiver test results | "
    f"Gain2 Configuration shows improvement in {positive_improvements}/{total_metrics} metrics\n"
    f"Key Wins for Gain2: {improvements['avg_fps']:+.1f}% FPS, "
    f"{improvements['avg_qp']:+.1f}% QP, "
    f"{improvements['total_undecodable']:+.1f}% Undecodable Frames, "
    f"{improvements['total_freezes']:+.1f}% Freezes"
)
fig.text(0.5, 0.02, note_text, ha='center', fontsize=10,
        bbox=dict(boxstyle='round,pad=0.6', facecolor='lightyellow', alpha=0.7, edgecolor='orange', linewidth=1.5))

# 保存图表
output_dir = Path('analysis_results')
output_dir.mkdir(exist_ok=True)

output_path = output_dir / 'comprehensive_comparison_paper.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"[*] 综合对比图已保存到: {output_path}")

output_pdf = output_dir / 'comprehensive_comparison_paper.pdf'
fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
print(f"[*] PDF格式已保存到: {output_pdf}\n")

print(f"[✓] 分析完成！Gain2配置在关键QoE指标上表现优异。")
