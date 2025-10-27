#!/usr/bin/env python3
"""
WebRTC配置对比分析工具 - 论文级别可视化
对比两个不同配置的WebRTC接收端性能指标
"""
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path

class ConfigComparator:
    """
    对比两个WebRTC配置的性能指标类
    """
    def __init__(self, log_file_1, log_file_2, label_1="Config 1", label_2="Config 2"):
        self.log_file_1 = log_file_1
        self.log_file_2 = log_file_2
        self.label_1 = label_1
        self.label_2 = label_2

        # 正则表达式模式
        self.patterns = {
            'bitrate': re.compile(r'\[VideoQuality-Bitrate\] MonoTime: (\d+), SSRC: (\d+), Payload Bytes Received: (\d+)'),
            'framerate': re.compile(r'\[VideoQuality-FrameRate\] MonoTime: (\d+), SSRC: (\d+), Frames Received: (\d+), Frames Decoded: (\d+), Frames Dropped: (\d+), Decoded FPS: (\d+), Frame Size: (\d+)x(\d+)'),
            'freeze': re.compile(r'\[VideoQuality-FreezeRate\] MonoTime: (\d+), SSRC: (\d+), Freeze Count: (\d+)'),
            'jitter': re.compile(r'\[VideoQuality-Jitter\] MonoTime: (\d+), SSRC: (\d+), Jitter \(ms\): (\d+\.?\d*)'),
            'packet_loss': re.compile(r'\[VideoQuality-PacketLoss\] MonoTime: (\d+), SSRC: (\d+), Packets Lost: (\d+)'),
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
                # 匹配比特率
                bitrate_match = self.patterns['bitrate'].search(line)
                if bitrate_match:
                    timestamp = int(bitrate_match.group(1))
                    payload_bytes = int(bitrate_match.group(3))
                    aggregated_data[timestamp]['payload_bytes'] = payload_bytes
                    continue

                # 匹配帧率
                framerate_match = self.patterns['framerate'].search(line)
                if framerate_match:
                    timestamp = int(framerate_match.group(1))
                    frames_received = int(framerate_match.group(3))
                    frames_decoded = int(framerate_match.group(4))
                    frames_dropped = int(framerate_match.group(5))
                    decoded_fps = int(framerate_match.group(6))
                    aggregated_data[timestamp]['decoded_fps'] = decoded_fps
                    aggregated_data[timestamp]['frames_dropped'] = frames_dropped
                    continue

                # 匹配冻结
                freeze_match = self.patterns['freeze'].search(line)
                if freeze_match:
                    timestamp = int(freeze_match.group(1))
                    freeze_count = int(freeze_match.group(3))
                    aggregated_data[timestamp]['freeze_count'] = freeze_count
                    continue

                # 匹配抖动
                jitter_match = self.patterns['jitter'].search(line)
                if jitter_match:
                    timestamp = int(jitter_match.group(1))
                    jitter_ms = float(jitter_match.group(3))
                    aggregated_data[timestamp]['jitter_ms'] = jitter_ms
                    continue

                # 匹配丢包
                packet_loss_match = self.patterns['packet_loss'].search(line)
                if packet_loss_match:
                    timestamp = int(packet_loss_match.group(1))
                    packets_lost = int(packet_loss_match.group(3))
                    aggregated_data[timestamp]['packets_lost'] = packets_lost
                    continue

                # 匹配QP
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

        # 计算比特率
        if 'payload_bytes' in df.columns and len(df) > 1:
            df['time_diff_s'] = df['timestamp'].diff() / 1000.0
            df['bytes_diff'] = df['payload_bytes'].diff()
            df['bitrate_kbps'] = ((df['bytes_diff'] * 8) / df['time_diff_s']) / 1000.0
            df.loc[df['bitrate_kbps'] < 0, 'bitrate_kbps'] = 0
        else:
            df['bitrate_kbps'] = 0

        # 填充缺失值
        for col in ['decoded_fps', 'freeze_count', 'jitter_ms', 'packets_lost', 'avg_qp', 'frames_dropped']:
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
            'avg_bitrate': df1[df1['bitrate_kbps'] > 0]['bitrate_kbps'].mean() if (df1['bitrate_kbps'] > 0).any() else 0,
            'avg_fps': df1['decoded_fps'].mean(),
            'total_freezes': df1['freeze_count'].max() if len(df1) > 0 else 0,
            'avg_jitter': df1['jitter_ms'].mean(),
            'total_packet_loss': df1['packets_lost'].max() if len(df1) > 0 else 0,
            'avg_qp': df1[df1['avg_qp'] > 0]['avg_qp'].mean() if (df1['avg_qp'] > 0).any() else 0,
            'total_dropped_frames': df1['frames_dropped'].max() if 'frames_dropped' in df1.columns and len(df1) > 0 else 0,
        }

        # 配置2统计
        stats[self.label_2] = {
            'avg_bitrate': df2[df2['bitrate_kbps'] > 0]['bitrate_kbps'].mean() if (df2['bitrate_kbps'] > 0).any() else 0,
            'avg_fps': df2['decoded_fps'].mean(),
            'total_freezes': df2['freeze_count'].max() if len(df2) > 0 else 0,
            'avg_jitter': df2['jitter_ms'].mean(),
            'total_packet_loss': df2['packets_lost'].max() if len(df2) > 0 else 0,
            'avg_qp': df2[df2['avg_qp'] > 0]['avg_qp'].mean() if (df2['avg_qp'] > 0).any() else 0,
            'total_dropped_frames': df2['frames_dropped'].max() if 'frames_dropped' in df2.columns and len(df2) > 0 else 0,
        }

        # 计算改进百分比
        improvements = {}
        for key in stats[self.label_1].keys():
            val1 = stats[self.label_1][key]
            val2 = stats[self.label_2][key]

            # 对于越小越好的指标（freeze, jitter, packet_loss, qp, dropped_frames）
            if key in ['total_freezes', 'avg_jitter', 'total_packet_loss', 'avg_qp', 'total_dropped_frames']:
                if val1 > 0:
                    improvements[key] = ((val1 - val2) / val1) * 100  # 正值表示改进
                else:
                    improvements[key] = 0
            # 对于越大越好的指标（bitrate, fps）
            else:
                if val1 > 0:
                    improvements[key] = ((val2 - val1) / val1) * 100  # 正值表示改进
                else:
                    improvements[key] = 0

        stats['improvements'] = improvements

        return stats

    def create_comparison_plots(self, df1, df2, stats):
        """
        创建论文级别的对比图表
        """
        # 使用专业的论文风格
        plt.style.use('seaborn-v0_8-whitegrid')

        # 定义颜色方案 - 使用色盲友好的颜色
        color1 = '#E69F00'  # 橙色 - Config 1
        color2 = '#0072B2'  # 蓝色 - Config 2

        # 创建图表 - 3行2列布局
        fig = plt.figure(figsize=(20, 16))
        gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.25, top=0.93, bottom=0.05, left=0.08, right=0.95)

        # 标题
        fig.suptitle('WebRTC Configuration Performance Comparison\nGoogleCC vs GainController2',
                    fontsize=18, fontweight='bold', y=0.97)

        # 1. 比特率对比
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.plot(df1['time_s'], df1['bitrate_kbps'], '-', color=color1,
                label=f"{self.label_1} (avg: {stats[self.label_1]['avg_bitrate']:.0f} kbps)", linewidth=1.5, alpha=0.8)
        ax1.plot(df2['time_s'], df2['bitrate_kbps'], '-', color=color2,
                label=f"{self.label_2} (avg: {stats[self.label_2]['avg_bitrate']:.0f} kbps)", linewidth=1.5, alpha=0.8)
        ax1.set_xlabel('Time (seconds)', fontsize=11)
        ax1.set_ylabel('Bitrate (kbps)', fontsize=11)
        ax1.set_title('(a) Video Bitrate Comparison', fontsize=12, fontweight='bold', loc='left')
        ax1.legend(loc='upper right', fontsize=9, framealpha=0.9)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(bottom=0)

        # 添加改进百分比标注
        improvement = stats['improvements']['avg_bitrate']
        ax1.text(0.02, 0.98, f'Improvement: {improvement:+.1f}%',
                transform=ax1.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen' if improvement > 0 else 'lightcoral', alpha=0.7))

        # 2. 帧率对比
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.plot(df1['time_s'], df1['decoded_fps'], '-', color=color1,
                label=f"{self.label_1} (avg: {stats[self.label_1]['avg_fps']:.1f} fps)", linewidth=1.5, alpha=0.8)
        ax2.plot(df2['time_s'], df2['decoded_fps'], '-', color=color2,
                label=f"{self.label_2} (avg: {stats[self.label_2]['avg_fps']:.1f} fps)", linewidth=1.5, alpha=0.8)
        ax2.set_xlabel('Time (seconds)', fontsize=11)
        ax2.set_ylabel('Frames Per Second', fontsize=11)
        ax2.set_title('(b) Decoded Frame Rate Comparison', fontsize=12, fontweight='bold', loc='left')
        ax2.legend(loc='upper right', fontsize=9, framealpha=0.9)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(bottom=0)

        improvement = stats['improvements']['avg_fps']
        ax2.text(0.02, 0.98, f'Improvement: {improvement:+.1f}%',
                transform=ax2.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen' if improvement > 0 else 'lightcoral', alpha=0.7))

        # 3. 丢包对比
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.plot(df1['time_s'], df1['packets_lost'], '-', color=color1,
                label=f"{self.label_1} (total: {stats[self.label_1]['total_packet_loss']:.0f})", linewidth=1.5, alpha=0.8)
        ax3.plot(df2['time_s'], df2['packets_lost'], '-', color=color2,
                label=f"{self.label_2} (total: {stats[self.label_2]['total_packet_loss']:.0f})", linewidth=1.5, alpha=0.8)
        ax3.set_xlabel('Time (seconds)', fontsize=11)
        ax3.set_ylabel('Cumulative Packet Loss', fontsize=11)
        ax3.set_title('(c) Packet Loss Comparison (QoS)', fontsize=12, fontweight='bold', loc='left')
        ax3.legend(loc='upper left', fontsize=9, framealpha=0.9)
        ax3.grid(True, alpha=0.3)
        ax3.set_ylim(bottom=0)

        improvement = stats['improvements']['total_packet_loss']
        ax3.text(0.02, 0.98, f'Reduction: {improvement:+.1f}%',
                transform=ax3.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen' if improvement > 0 else 'lightcoral', alpha=0.7))

        # 4. 抖动对比
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.plot(df1['time_s'], df1['jitter_ms'], '-', color=color1,
                label=f"{self.label_1} (avg: {stats[self.label_1]['avg_jitter']:.1f} ms)", linewidth=1.5, alpha=0.8)
        ax4.plot(df2['time_s'], df2['jitter_ms'], '-', color=color2,
                label=f"{self.label_2} (avg: {stats[self.label_2]['avg_jitter']:.1f} ms)", linewidth=1.5, alpha=0.8)
        ax4.set_xlabel('Time (seconds)', fontsize=11)
        ax4.set_ylabel('Jitter (ms)', fontsize=11)
        ax4.set_title('(d) Network Jitter Comparison (QoS)', fontsize=12, fontweight='bold', loc='left')
        ax4.legend(loc='upper right', fontsize=9, framealpha=0.9)
        ax4.grid(True, alpha=0.3)
        ax4.set_ylim(bottom=0)

        improvement = stats['improvements']['avg_jitter']
        ax4.text(0.02, 0.98, f'Reduction: {improvement:+.1f}%',
                transform=ax4.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen' if improvement > 0 else 'lightcoral', alpha=0.7))

        # 5. 视频冻结对比
        ax5 = fig.add_subplot(gs[2, 0])
        ax5.plot(df1['time_s'], df1['freeze_count'], '-', color=color1,
                label=f"{self.label_1} (total: {stats[self.label_1]['total_freezes']:.0f})", linewidth=1.5, alpha=0.8)
        ax5.plot(df2['time_s'], df2['freeze_count'], '-', color=color2,
                label=f"{self.label_2} (total: {stats[self.label_2]['total_freezes']:.0f})", linewidth=1.5, alpha=0.8)
        ax5.set_xlabel('Time (seconds)', fontsize=11)
        ax5.set_ylabel('Cumulative Freeze Count', fontsize=11)
        ax5.set_title('(e) Video Freeze Comparison (QoE)', fontsize=12, fontweight='bold', loc='left')
        ax5.legend(loc='upper left', fontsize=9, framealpha=0.9)
        ax5.grid(True, alpha=0.3)
        ax5.set_ylim(bottom=0)

        improvement = stats['improvements']['total_freezes']
        ax5.text(0.02, 0.98, f'Reduction: {improvement:+.1f}%',
                transform=ax5.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen' if improvement > 0 else 'lightcoral', alpha=0.7))

        # 6. QP对比
        ax6 = fig.add_subplot(gs[2, 1])
        ax6.plot(df1['time_s'], df1['avg_qp'], '-', color=color1,
                label=f"{self.label_1} (avg: {stats[self.label_1]['avg_qp']:.1f})", linewidth=1.5, alpha=0.8)
        ax6.plot(df2['time_s'], df2['avg_qp'], '-', color=color2,
                label=f"{self.label_2} (avg: {stats[self.label_2]['avg_qp']:.1f})", linewidth=1.5, alpha=0.8)
        ax6.set_xlabel('Time (seconds)', fontsize=11)
        ax6.set_ylabel('Average QP', fontsize=11)
        ax6.set_title('(f) Video Quality (QP) Comparison - Lower is Better (QoE)', fontsize=12, fontweight='bold', loc='left')
        ax6.legend(loc='upper right', fontsize=9, framealpha=0.9)
        ax6.grid(True, alpha=0.3)
        ax6.set_ylim(bottom=0)

        improvement = stats['improvements']['avg_qp']
        ax6.text(0.02, 0.98, f'Reduction: {improvement:+.1f}%',
                transform=ax6.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen' if improvement > 0 else 'lightcoral', alpha=0.7))

        # 7. 性能指标柱状图对比
        ax7 = fig.add_subplot(gs[3, :])

        metrics = ['Avg Bitrate\n(kbps)', 'Avg FPS', 'Total Packet\nLoss',
                  'Avg Jitter\n(ms)', 'Total Freezes', 'Avg QP']

        values1 = [
            stats[self.label_1]['avg_bitrate'],
            stats[self.label_1]['avg_fps'],
            stats[self.label_1]['total_packet_loss'],
            stats[self.label_1]['avg_jitter'],
            stats[self.label_1]['total_freezes'],
            stats[self.label_1]['avg_qp']
        ]

        values2 = [
            stats[self.label_2]['avg_bitrate'],
            stats[self.label_2]['avg_fps'],
            stats[self.label_2]['total_packet_loss'],
            stats[self.label_2]['avg_jitter'],
            stats[self.label_2]['total_freezes'],
            stats[self.label_2]['avg_qp']
        ]

        # 归一化数据以便比较（每个指标除以两者中的最大值）
        normalized1 = []
        normalized2 = []
        for v1, v2 in zip(values1, values2):
            max_val = max(v1, v2)
            if max_val > 0:
                normalized1.append(v1 / max_val)
                normalized2.append(v2 / max_val)
            else:
                normalized1.append(0)
                normalized2.append(0)

        x = np.arange(len(metrics))
        width = 0.35

        bars1 = ax7.bar(x - width/2, normalized1, width, label=self.label_1, color=color1, alpha=0.8)
        bars2 = ax7.bar(x + width/2, normalized2, width, label=self.label_2, color=color2, alpha=0.8)

        ax7.set_ylabel('Normalized Value (relative to max)', fontsize=11)
        ax7.set_title('(g) Overall Performance Metrics Comparison (Normalized)', fontsize=12, fontweight='bold', loc='left')
        ax7.set_xticks(x)
        ax7.set_xticklabels(metrics, fontsize=10)
        ax7.legend(loc='upper right', fontsize=10, framealpha=0.9)
        ax7.grid(True, alpha=0.3, axis='y')
        ax7.set_ylim(0, 1.2)

        # 在柱状图上添加原始值
        for i, (bar1, bar2, v1, v2) in enumerate(zip(bars1, bars2, values1, values2)):
            height1 = bar1.get_height()
            height2 = bar2.get_height()
            ax7.text(bar1.get_x() + bar1.get_width()/2., height1,
                    f'{v1:.1f}', ha='center', va='bottom', fontsize=8)
            ax7.text(bar2.get_x() + bar2.get_width()/2., height2,
                    f'{v2:.1f}', ha='center', va='bottom', fontsize=8)

        # 添加注释说明
        note_text = (
            "Note: For Packet Loss, Jitter, Freezes, and QP - lower values indicate better performance.\n"
            "For Bitrate and FPS - higher values indicate better performance."
        )
        fig.text(0.5, 0.01, note_text, ha='center', fontsize=9, style='italic',
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.6))

        return fig

    def create_summary_table(self, stats):
        """
        创建性能对比汇总表
        """
        print("\n" + "="*80)
        print("PERFORMANCE COMPARISON SUMMARY")
        print("="*80)

        metrics = [
            ('Average Bitrate (kbps)', 'avg_bitrate', True),
            ('Average FPS', 'avg_fps', True),
            ('Total Packet Loss', 'total_packet_loss', False),
            ('Average Jitter (ms)', 'avg_jitter', False),
            ('Total Video Freezes', 'total_freezes', False),
            ('Average QP', 'avg_qp', False),
            ('Total Dropped Frames', 'total_dropped_frames', False),
        ]

        print(f"\n{'Metric':<30} {self.label_1:>20} {self.label_2:>20} {'Improvement':>15}")
        print("-"*90)

        for metric_name, metric_key, higher_better in metrics:
            val1 = stats[self.label_1][metric_key]
            val2 = stats[self.label_2][metric_key]
            improvement = stats['improvements'][metric_key]

            # 确定改进的符号
            if higher_better:
                symbol = '↑' if improvement > 0 else '↓'
            else:
                symbol = '↓' if improvement > 0 else '↑'

            print(f"{metric_name:<30} {val1:>20.2f} {val2:>20.2f} {symbol} {abs(improvement):>13.1f}%")

        print("="*80)
        print(f"\nNote: {self.label_1} = GoogleCC (Original)")
        print(f"      {self.label_2} = GainController2")
        print("      ↑ indicates improvement, ↓ indicates degradation")
        print("="*80 + "\n")


def main():
    """
    主函数
    """
    # 配置文件路径
    log_file_1 = '/home/administrator/webrtc-cloud-server/webrtc_config_results/receiver_cloud.log'
    log_file_2 = '/home/administrator/webrtc-cloud-server/webrtc_config_results/10.16receiver_cloud.log'

    # 配置标签
    label_1 = "GoogleCC"
    label_2 = "GainController2"

    print("="*80)
    print("WebRTC Configuration Performance Comparison Tool")
    print("="*80)
    print(f"Configuration 1: {label_1}")
    print(f"  Log file: {log_file_1}")
    print(f"Configuration 2: {label_2}")
    print(f"  Log file: {log_file_2}")
    print("="*80 + "\n")

    try:
        # 创建对比器
        comparator = ConfigComparator(log_file_1, log_file_2, label_1, label_2)

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

        # 创建对比图表
        print("[*] 生成对比图表...")
        fig = comparator.create_comparison_plots(df1, df2, stats)

        # 保存图表
        output_dir = Path('analysis_results')
        output_dir.mkdir(exist_ok=True)

        output_path = output_dir / 'config_comparison_paper.png'
        fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"\n[*] 论文级别对比图表已保存到: {output_path}")

        # 同时保存PDF格式用于论文
        output_pdf = output_dir / 'config_comparison_paper.pdf'
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
