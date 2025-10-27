#!/usr/bin/env python3
"""
WebRTC配置柱状图对比分析 - 论文级别可视化
专注于QoE核心指标：QP、FPS、Freeze数、未解码帧数
"""
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path

class BarChartComparator:
    """
    使用柱状图对比两个WebRTC配置的关键QoE指标
    """
    def __init__(self, log_file_1, log_file_2, label_1="Config 1", label_2="Config 2"):
        self.log_file_1 = log_file_1
        self.log_file_2 = log_file_2
        self.label_1 = label_1
        self.label_2 = label_2

        # 正则表达式模式
        self.patterns = {
            'framerate': re.compile(r'\[VideoQuality-FrameRate\] MonoTime: (\d+), SSRC: (\d+), Frames Received: (\d+), Frames Decoded: (\d+), Frames Dropped: (\d+), Decoded FPS: (\d+), Frame Size: (\d+)x(\d+)'),
            'freeze': re.compile(r'\[VideoQuality-FreezeRate\] MonoTime: (\d+), SSRC: (\d+), Freeze Count: (\d+)'),
            'qp': re.compile(r'\[VideoQuality-QP\] MonoTime: (\d+), SSRC: (\d+), QP Sum: (\d+), Average QP: (\d+\.?\d*)'),
        }

    def parse_log_file(self, log_file_path):
        """
        解析日志文件并返回DataFrame
        """
        print(f"[*] 解析日志文件: {log_file_path}")

        aggregated_data = defaultdict(dict)

        with open(log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 匹配帧率数据
                framerate_match = self.patterns['framerate'].search(line)
                if framerate_match:
                    timestamp = int(framerate_match.group(1))
                    frames_received = int(framerate_match.group(3))
                    frames_decoded = int(framerate_match.group(4))
                    frames_dropped = int(framerate_match.group(5))
                    decoded_fps = int(framerate_match.group(6))

                    aggregated_data[timestamp]['decoded_fps'] = decoded_fps
                    aggregated_data[timestamp]['frames_received'] = frames_received
                    aggregated_data[timestamp]['frames_decoded'] = frames_decoded
                    aggregated_data[timestamp]['frames_dropped'] = frames_dropped
                    # 未解码帧 = 接收帧 - 解码帧
                    aggregated_data[timestamp]['undecodable_frames'] = frames_dropped
                    continue

                # 匹配冻结数据
                freeze_match = self.patterns['freeze'].search(line)
                if freeze_match:
                    timestamp = int(freeze_match.group(1))
                    freeze_count = int(freeze_match.group(3))
                    aggregated_data[timestamp]['freeze_count'] = freeze_count
                    continue

                # 匹配QP数据
                qp_match = self.patterns['qp'].search(line)
                if qp_match:
                    timestamp = int(qp_match.group(1))
                    avg_qp = float(qp_match.group(4))
                    aggregated_data[timestamp]['avg_qp'] = avg_qp
                    continue

        # 转换为DataFrame
        df = pd.DataFrame.from_dict(aggregated_data, orient='index')
        df.index.name = 'timestamp'
        df = df.sort_index().reset_index()

        # 填充缺失值
        for col in ['decoded_fps', 'freeze_count', 'avg_qp', 'undecodable_frames', 'frames_dropped']:
            if col not in df.columns:
                df[col] = 0

        # 转换为相对时间（秒）
        if len(df) > 0:
            start_time_ms = df['timestamp'].iloc[0]
            df['time_s'] = (df['timestamp'] - start_time_ms) / 1000.0
        else:
            df['time_s'] = 0

        print(f"[*] 解析完成，共 {len(df)} 条数据点")

        return df

    def compute_statistics(self, df1, df2):
        """
        计算两个配置的统计数据
        """
        stats = {}

        # 配置1统计
        stats[self.label_1] = {
            'avg_fps': df1['decoded_fps'].mean(),
            'total_freezes': df1['freeze_count'].max() if len(df1) > 0 else 0,
            'avg_qp': df1[df1['avg_qp'] > 0]['avg_qp'].mean() if (df1['avg_qp'] > 0).any() else 0,
            'total_undecodable': df1['undecodable_frames'].max() if len(df1) > 0 else 0,
            'avg_undecodable': df1['undecodable_frames'].mean(),
            # 额外统计
            'min_fps': df1['decoded_fps'].min(),
            'max_fps': df1['decoded_fps'].max(),
            'std_fps': df1['decoded_fps'].std(),
            'min_qp': df1[df1['avg_qp'] > 0]['avg_qp'].min() if (df1['avg_qp'] > 0).any() else 0,
            'max_qp': df1[df1['avg_qp'] > 0]['avg_qp'].max() if (df1['avg_qp'] > 0).any() else 0,
        }

        # 配置2统计
        stats[self.label_2] = {
            'avg_fps': df2['decoded_fps'].mean(),
            'total_freezes': df2['freeze_count'].max() if len(df2) > 0 else 0,
            'avg_qp': df2[df2['avg_qp'] > 0]['avg_qp'].mean() if (df2['avg_qp'] > 0).any() else 0,
            'total_undecodable': df2['undecodable_frames'].max() if len(df2) > 0 else 0,
            'avg_undecodable': df2['undecodable_frames'].mean(),
            # 额外统计
            'min_fps': df2['decoded_fps'].min(),
            'max_fps': df2['decoded_fps'].max(),
            'std_fps': df2['decoded_fps'].std(),
            'min_qp': df2[df2['avg_qp'] > 0]['avg_qp'].min() if (df2['avg_qp'] > 0).any() else 0,
            'max_qp': df2[df2['avg_qp'] > 0]['avg_qp'].max() if (df2['avg_qp'] > 0).any() else 0,
        }

        # 计算改进百分比
        improvements = {}
        for key in ['avg_fps', 'total_freezes', 'avg_qp', 'total_undecodable', 'avg_undecodable']:
            val1 = stats[self.label_1][key]
            val2 = stats[self.label_2][key]

            # 对于越小越好的指标（freeze, qp, undecodable）
            if key in ['total_freezes', 'avg_qp', 'total_undecodable', 'avg_undecodable']:
                if val1 > 0:
                    improvements[key] = ((val1 - val2) / val1) * 100  # 正值表示改进
                else:
                    improvements[key] = 0
            # 对于越大越好的指标（fps）
            else:
                if val1 > 0:
                    improvements[key] = ((val2 - val1) / val1) * 100  # 正值表示改进
                else:
                    improvements[key] = 0

        stats['improvements'] = improvements

        return stats

    def create_bar_comparison(self, df1, df2, stats):
        """
        创建论文级别的柱状图对比
        """
        # 使用专业的论文风格
        plt.style.use('seaborn-v0_8-whitegrid')

        # 定义颜色方案 - 使用色盲友好的颜色
        color1 = '#E69F00'  # 橙色 - GoogleCC2
        color2 = '#009E73'  # 绿色 - Gain2

        # 创建图表 - 2行2列布局
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('WebRTC QoE Metrics Comparison: GoogleCC2 vs GainController2',
                    fontsize=18, fontweight='bold', y=0.98)

        # 准备数据
        metrics = [
            ('Average Frame Rate (FPS)', 'avg_fps', 'FPS', True, axes[0, 0]),
            ('Average Video Quality (QP)', 'avg_qp', 'QP Value', False, axes[0, 1]),
            ('Total Video Freezes', 'total_freezes', 'Freeze Count', False, axes[1, 0]),
            ('Total Undecodable Frames', 'total_undecodable', 'Frame Count', False, axes[1, 1]),
        ]

        for idx, (title, metric_key, ylabel, higher_better, ax) in enumerate(metrics):
            val1 = stats[self.label_1][metric_key]
            val2 = stats[self.label_2][metric_key]
            improvement = stats['improvements'][metric_key]

            # 绘制柱状图
            bars = ax.bar([0, 1], [val1, val2],
                         color=[color1, color2],
                         alpha=0.8,
                         edgecolor='black',
                         linewidth=1.5,
                         width=0.6)

            # 添加数值标签
            for i, (bar, val) in enumerate(zip(bars, [val1, val2])):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{val:.2f}',
                       ha='center', va='bottom', fontsize=14, fontweight='bold')

            # 设置标题和标签
            ax.set_title(f'({chr(97+idx)}) {title}',
                        fontsize=13, fontweight='bold', pad=15, loc='left')
            ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
            ax.set_xticks([0, 1])
            ax.set_xticklabels([self.label_1, self.label_2], fontsize=11, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            ax.set_ylim(bottom=0)

            # 添加改进百分比标注
            if higher_better:
                improvement_color = 'green' if improvement > 0 else 'red'
                improvement_text = f'{"+" if improvement > 0 else ""}{improvement:.1f}%'
            else:
                improvement_color = 'green' if improvement > 0 else 'red'
                improvement_text = f'{"+" if improvement > 0 else ""}{improvement:.1f}%'

            ax.text(0.5, 0.95, improvement_text,
                   transform=ax.transAxes,
                   fontsize=13,
                   fontweight='bold',
                   ha='center',
                   va='top',
                   bbox=dict(boxstyle='round,pad=0.5',
                            facecolor=improvement_color,
                            alpha=0.3,
                            edgecolor=improvement_color,
                            linewidth=2))

            # 添加统计信息（对于FPS和QP）
            if metric_key == 'avg_fps':
                stats_text = (f'{self.label_1}: Min={stats[self.label_1]["min_fps"]:.1f}, '
                            f'Max={stats[self.label_1]["max_fps"]:.1f}, '
                            f'Std={stats[self.label_1]["std_fps"]:.1f}\n'
                            f'{self.label_2}: Min={stats[self.label_2]["min_fps"]:.1f}, '
                            f'Max={stats[self.label_2]["max_fps"]:.1f}, '
                            f'Std={stats[self.label_2]["std_fps"]:.1f}')
                ax.text(0.02, 0.02, stats_text,
                       transform=ax.transAxes,
                       fontsize=8,
                       verticalalignment='bottom',
                       bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.6))

            elif metric_key == 'avg_qp':
                stats_text = (f'{self.label_1}: Min={stats[self.label_1]["min_qp"]:.1f}, '
                            f'Max={stats[self.label_1]["max_qp"]:.1f}\n'
                            f'{self.label_2}: Min={stats[self.label_2]["min_qp"]:.1f}, '
                            f'Max={stats[self.label_2]["max_qp"]:.1f}')
                ax.text(0.02, 0.02, stats_text,
                       transform=ax.transAxes,
                       fontsize=8,
                       verticalalignment='bottom',
                       bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.6))

        plt.tight_layout(rect=[0, 0.03, 1, 0.96])

        # 添加底部注释
        note_text = (
            "Note: For FPS (higher is better), For QP/Freezes/Undecodable Frames (lower is better)\n"
            "Percentage in green box indicates improvement, red indicates degradation"
        )
        fig.text(0.5, 0.01, note_text, ha='center', fontsize=10, style='italic',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.4))

        return fig

    def create_summary_table(self, stats):
        """
        创建性能对比汇总表
        """
        print("\n" + "="*90)
        print("QoE METRICS COMPARISON SUMMARY")
        print("="*90)

        metrics = [
            ('Average FPS', 'avg_fps', True),
            ('  Min FPS', 'min_fps', True),
            ('  Max FPS', 'max_fps', True),
            ('  Std Dev FPS', 'std_fps', False),
            ('Average QP', 'avg_qp', False),
            ('  Min QP', 'min_qp', False),
            ('  Max QP', 'max_qp', False),
            ('Total Video Freezes', 'total_freezes', False),
            ('Total Undecodable Frames', 'total_undecodable', False),
            ('Average Undecodable Frames', 'avg_undecodable', False),
        ]

        print(f"\n{'Metric':<30} {self.label_1:>20} {self.label_2:>20} {'Change':>15}")
        print("-"*90)

        for metric_name, metric_key, higher_better in metrics:
            val1 = stats[self.label_1][metric_key]
            val2 = stats[self.label_2][metric_key]

            if metric_key in stats['improvements']:
                improvement = stats['improvements'][metric_key]
                if higher_better:
                    symbol = '↑' if improvement > 0 else '↓'
                else:
                    symbol = '↓' if improvement > 0 else '↑'
                change_text = f"{symbol} {abs(improvement):>12.1f}%"
            else:
                # 对于没有改进计算的指标，显示绝对差值
                diff = val2 - val1
                change_text = f"  {diff:>13.2f}"

            print(f"{metric_name:<30} {val1:>20.2f} {val2:>20.2f} {change_text:>15}")

        print("="*90)
        print(f"\nNote: {self.label_1} = GoogleCC2")
        print(f"      {self.label_2} = GainController2")
        print("      ↑ indicates improvement, ↓ indicates degradation")
        print("="*90 + "\n")


def main():
    """
    主函数
    """
    # 配置文件路径 - 根据PNG文件对应的日志
    # googlecc2receiver_quality_analysis_debug.png 对应 receiver_cloud.log (最新的10月16日15:30)
    # gain2receiver_quality_analysis_debug.png 对应 10.16receiver_cloud.log
    log_file_1 = '/home/administrator/webrtc-cloud-server/webrtc_config_results/receiver_cloud.log'  # GoogleCC2
    log_file_2 = '/home/administrator/webrtc-cloud-server/webrtc_config_results/10.16receiver_cloud.log'  # Gain2

    # 配置标签
    label_1 = "GoogleCC2"
    label_2 = "Gain2"

    print("="*90)
    print("WebRTC QoE Metrics Bar Chart Comparison Tool")
    print("="*90)
    print(f"Configuration 1: {label_1}")
    print(f"  Log file: {log_file_1}")
    print(f"Configuration 2: {label_2}")
    print(f"  Log file: {log_file_2}")
    print("="*90 + "\n")

    try:
        # 创建对比器
        comparator = BarChartComparator(log_file_1, log_file_2, label_1, label_2)

        # 解析两个日志文件
        df1 = comparator.parse_log_file(log_file_1)
        df2 = comparator.parse_log_file(log_file_2)

        if df1.empty or df2.empty:
            print("[!] 错误: 一个或两个日志文件的数据为空")
            return

        # 计算统计数据
        print("\n[*] 计算统计数据...")
        stats = comparator.compute_statistics(df1, df2)

        # 打印汇总表
        comparator.create_summary_table(stats)

        # 创建柱状图对比
        print("[*] 生成柱状图对比...")
        fig = comparator.create_bar_comparison(df1, df2, stats)

        # 保存图表
        output_dir = Path('analysis_results')
        output_dir.mkdir(exist_ok=True)

        output_path = output_dir / 'qoe_metrics_bar_comparison.png'
        fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"\n[*] 柱状图对比已保存到: {output_path}")

        # 同时保存PDF格式用于论文
        output_pdf = output_dir / 'qoe_metrics_bar_comparison.pdf'
        fig.savefig(output_pdf, dpi=300, bbox_inches='tight', format='pdf')
        print(f"[*] PDF格式已保存到: {output_pdf}")

        print("\n[*] 分析完成！")

    except FileNotFoundError as e:
        print(f"[!] 错误: 文件未找到 - {e}")
    except Exception as e:
        print(f"[!] 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
