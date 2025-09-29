#!/usr/bin/env python3
"""
WebRTC 接收端视频质量日志分析器
解析并可视化接收比特率、解码帧率和视频冻结三大核心指标。
"""
import re
import matplotlib
matplotlib.use('Agg')  # 设置matplotlib后端以避免图形界面问题
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict

class ReceiverQualityAnalyzer:
    """
    一个专门解析和可视化接收端视频质量日志的类。
    """
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        
        # 使用正则表达式匹配日志中的关键信息（基于实际日志格式）
        self.patterns = {
            # 匹配包含MonoTime时间戳的VideoQuality日志行
            'bitrate': re.compile(r'\[VideoQuality-Bitrate\] MonoTime: (\d+), SSRC: (\d+), Payload Bytes Received: (\d+)'),
            'framerate': re.compile(r'\[VideoQuality-FrameRate\] MonoTime: (\d+), SSRC: (\d+), Frames Received: (\d+), Frames Decoded: (\d+), Frames Dropped: (\d+), Decoded FPS: (\d+), Frame Size: (\d+)x(\d+)'),
            'freeze': re.compile(r'\[VideoQuality-FreezeRate\] MonoTime: (\d+), SSRC: (\d+), Freeze Count: (\d+)'),
            'jitter': re.compile(r'\[VideoQuality-Jitter\] MonoTime: (\d+), SSRC: (\d+), Jitter \(ms\): (\d+\.?\d*)'),
            'packet_loss': re.compile(r'\[VideoQuality-PacketLoss\] MonoTime: (\d+), SSRC: (\d+), Packets Lost: (\d+)'),
            'qp': re.compile(r'\[VideoQuality-QP\] MonoTime: (\d+), SSRC: (\d+), QP Sum: (\d+), Average QP: (\d+\.?\d*)'),
            # 从VideoReceiveStreamInterface stats提取多种延迟信息
            'e2e_delay': re.compile(r'VideoReceiveStreamInterface stats: (\d+), \{.*?decode_ms: (\d+), max_decode_ms: (\d+).*?current_delay_ms: (\d+), target_delay_ms: (\d+).*?jitter_delay_ms: (\d+).*?totalProcessingDelay: ([\d.]+).*?\}')
        }

    def parse_log_file(self):
        """
        解析日志文件，提取并聚合质量数据。
        """
        print(f"[*] 正在解析日志文件: {self.log_file_path}")
        
        # 使用字典按时间戳聚合数据，避免数据分散
        aggregated_data = defaultdict(dict)

        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 匹配比特率数据
                bitrate_match = self.patterns['bitrate'].search(line)
                if bitrate_match:
                    timestamp = int(bitrate_match.group(1))
                    ssrc = int(bitrate_match.group(2))
                    payload_bytes = int(bitrate_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['payload_bytes'] = payload_bytes
                    continue

                # 匹配帧率数据（同时提取分辨率和不可解码帧信息）
                framerate_match = self.patterns['framerate'].search(line)
                if framerate_match:
                    timestamp = int(framerate_match.group(1))
                    ssrc = int(framerate_match.group(2))
                    frames_received = int(framerate_match.group(3))
                    frames_decoded = int(framerate_match.group(4))
                    frames_dropped = int(framerate_match.group(5))
                    decoded_fps = int(framerate_match.group(6))
                    width = int(framerate_match.group(7))
                    height = int(framerate_match.group(8))
                    
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['decoded_fps'] = decoded_fps
                    aggregated_data[timestamp]['width'] = width
                    aggregated_data[timestamp]['height'] = height
                    aggregated_data[timestamp]['total_pixels'] = width * height
                    aggregated_data[timestamp]['aspect_ratio'] = width / height if height > 0 else 0
                    
                    # 记录不可解码帧的绝对数量（而非比率）
                    aggregated_data[timestamp]['undecodable_frames_received'] = frames_received
                    aggregated_data[timestamp]['undecodable_frames_decoded'] = frames_decoded
                    aggregated_data[timestamp]['undecodable_frames_dropped'] = frames_dropped
                    aggregated_data[timestamp]['undecodable_count'] = frames_dropped  # 当前时刻的不可解码帧数量
                    continue

                # 匹配冻结数据
                freeze_match = self.patterns['freeze'].search(line)
                if freeze_match:
                    timestamp = int(freeze_match.group(1))
                    ssrc = int(freeze_match.group(2))
                    freeze_count = int(freeze_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['freeze_count'] = freeze_count
                    continue

                # 匹配网络抖动数据
                jitter_match = self.patterns['jitter'].search(line)
                if jitter_match:
                    timestamp = int(jitter_match.group(1))
                    ssrc = int(jitter_match.group(2))
                    jitter_ms = float(jitter_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['jitter_ms'] = jitter_ms
                    continue

                # 匹配丢包数据
                packet_loss_match = self.patterns['packet_loss'].search(line)
                if packet_loss_match:
                    timestamp = int(packet_loss_match.group(1))
                    ssrc = int(packet_loss_match.group(2))
                    packets_lost = int(packet_loss_match.group(3))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['packets_lost'] = packets_lost
                    continue

                # 匹配量化参数数据
                qp_match = self.patterns['qp'].search(line)
                if qp_match:
                    timestamp = int(qp_match.group(1))
                    ssrc = int(qp_match.group(2))
                    qp_sum = int(qp_match.group(3))
                    avg_qp = float(qp_match.group(4))
                    aggregated_data[timestamp]['ssrc'] = ssrc
                    aggregated_data[timestamp]['qp_sum'] = qp_sum
                    aggregated_data[timestamp]['avg_qp'] = avg_qp
                    continue
                    
                # 匹配端到端延迟数据（从VideoReceiveStreamInterface stats）
                e2e_delay_match = self.patterns['e2e_delay'].search(line)
                if e2e_delay_match:
                    timestamp = int(e2e_delay_match.group(1))
                    decode_ms = int(e2e_delay_match.group(2))
                    max_decode_ms = int(e2e_delay_match.group(3))
                    current_delay_ms = int(e2e_delay_match.group(4))
                    target_delay_ms = int(e2e_delay_match.group(5))
                    jitter_delay_ms = int(e2e_delay_match.group(6))
                    total_processing_delay = float(e2e_delay_match.group(7))
                    
                    # 提取多个延迟组件
                    aggregated_data[timestamp]['decode_ms'] = decode_ms
                    aggregated_data[timestamp]['max_decode_ms'] = max_decode_ms
                    aggregated_data[timestamp]['current_delay_ms'] = current_delay_ms
                    aggregated_data[timestamp]['target_delay_ms'] = target_delay_ms
                    aggregated_data[timestamp]['jitter_delay_ms'] = jitter_delay_ms
                    aggregated_data[timestamp]['total_processing_delay'] = total_processing_delay
                    # 使用current_delay_ms作为主要的端到端延迟指标
                    aggregated_data[timestamp]['total_e2e_delay_ms'] = current_delay_ms
                    continue

        
        # 将聚合后的字典转换为 DataFrame
        df = pd.DataFrame.from_dict(aggregated_data, orient='index')
        df.index.name = 'timestamp'
        df = df.sort_index().reset_index()

        # 计算瞬时比特率
        if 'payload_bytes' in df.columns and len(df) > 1:
            df['time_diff_s'] = df['timestamp'].diff() / 1000.0
            df['bytes_diff'] = df['payload_bytes'].diff()
            # 只有当时间差和字节差都为正时才计算，避免无效值
            df['bitrate_kbps'] = ((df['bytes_diff'] * 8) / df['time_diff_s']) / 1000.0
            df.loc[df['bitrate_kbps'] < 0, 'bitrate_kbps'] = 0 # 负值置为0
        else:
            df['bitrate_kbps'] = 0

        print(f"[*] 解析完成，共找到 {len(df)} 条聚合后的质量数据点。")
        
        # 显示前几行数据用于验证
        if len(df) > 0:
            print(f"[*] 数据样本预览:")
            print(f"  时间戳范围: {df['timestamp'].min()} - {df['timestamp'].max()}")
            print(f"  数据列: {list(df.columns)}")
            print(f"  前3行数据:")
            print(df.head(3).to_string())
        
        return df

    def check_data_availability(self, df):
        """检测每个指标的数据可用性"""
        metrics_status = {
            'bitrate': (df['bitrate_kbps'] > 0).any() if 'bitrate_kbps' in df.columns else False,
            'framerate': (df['decoded_fps'] > 0).any() if 'decoded_fps' in df.columns else False,
            'freeze': (df['freeze_count'] >= 0).any() if 'freeze_count' in df.columns else False,
            'jitter': (df['jitter_ms'] >= 0).any() if 'jitter_ms' in df.columns else False,
            'packet_loss': (df['packets_lost'] >= 0).any() if 'packets_lost' in df.columns else False,
            'qp': (df['avg_qp'] > 0).any() if 'avg_qp' in df.columns else False,
            'resolution': (df['total_pixels'] > 0).any() if 'total_pixels' in df.columns else False,
            'undecodable': (df['undecodable_count'] >= 0).any() if 'undecodable_count' in df.columns else False,
            'e2e_delay': (df['total_e2e_delay_ms'] > 0).any() if 'total_e2e_delay_ms' in df.columns else False
        }
        return metrics_status

    def plot_metric_placeholder(self, ax, metric_name, metric_title):
        """为缺失数据绘制占位符，保持与现有图表风格一致"""
        ax.text(0.5, 0.5, f'No {metric_title} Data Available\n(Requires updated WebRTC logs with new metrics)', 
                ha='center', va='center', transform=ax.transAxes,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.3),
                fontsize=10, style='italic', color='gray')
        ax.set_ylabel(metric_title, fontsize=11)
        ax.set_title(f'{metric_title} Over Time', fontsize=12)
        ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        ax.text(0.02, 0.02, 'Data: Not Available', transform=ax.transAxes, 
                bbox=dict(boxstyle="round,pad=0.2", facecolor="orange", alpha=0.5), fontsize=9)

    def plot_quality_metrics(self, df):
        """
        使用解析出的数据绘制九合一的视频质量图表，按QoS和QoE分类：
        QoS（管道质量）：丢包、抖动
        QoE（内容质量）：比特率、帧率、冻结、QP、分辨率、不可解码帧、端到端延迟
        """
        if df.empty or len(df) < 2:
            print("[!] 数据不足，无法生成图表。")
            return None

        # 数据预处理 - 填充缺失的列
        required_columns = ['timestamp', 'bitrate_kbps', 'decoded_fps', 'freeze_count', 'jitter_ms', 'packets_lost', 'avg_qp', 
                           'width', 'height', 'undecodable_count', 'total_e2e_delay_ms']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0 if col != 'total_e2e_delay_ms' else float('nan')
        
        # 为分辨率创建文本标签（width x height）
        df['resolution_label'] = df.apply(
            lambda row: f"{int(row['width'])}x{int(row['height'])}"
            if pd.notna(row['width']) and pd.notna(row['height']) and row['width'] > 0 and row['height'] > 0
            else 'Unknown', axis=1
        )
        
        # 检测数据可用性
        metrics_status = self.check_data_availability(df)
        print(f"[*] 数据可用性检查:")
        for metric, available in metrics_status.items():
            status = "✅ Available" if available else "❌ Missing"
            print(f"    {metric}: {status}")
        print()
        
        df = df.dropna(subset=['timestamp']).reset_index(drop=True)
        if df.empty or len(df) < 2:
            print("[!] 清理后数据不足，无法生成图表。")
            return None

        start_time_ms = df['timestamp'].iloc[0]
        df['time_s'] = (df['timestamp'] - start_time_ms) / 1000.0
        
        # 通过检测DTLS transport关闭事件来确定数据传输结束时间
        dtls_close_time = None
        try:
            with open(self.log_file_path, 'r') as f:
                for line in f:
                    if "DTLS transport closed by remote" in line:
                        print(f"[*] 检测到DTLS连接关闭: {line.strip()}")
                        break
                    # 检查是否有VideoQuality时间戳在DTLS关闭之前（新格式使用MonoTime）
                    if "[VideoQuality-" in line and "MonoTime: " in line:
                        time_match = re.search(r'MonoTime: (\d+)', line)
                        if time_match:
                            dtls_close_time = int(time_match.group(1))
        except Exception as e:
            print(f"[!] 读取DTLS关闭时间时出错: {e}")
        
        if dtls_close_time:
            # 转换为相对时间（秒）
            dtls_close_relative = (dtls_close_time - start_time_ms) / 1000.0
            # 在DTLS关闭时间基础上增加0.5秒作为显示范围
            time_limit = dtls_close_relative + 0.5
            print(f"[*] DTLS关闭前最后数据时间戳: {dtls_close_time}")
            print(f"[*] 数据传输结束时间: {dtls_close_relative:.1f} 秒")
            print(f"[*] 图表将显示时间范围: 0 - {time_limit:.1f} 秒")
        else:
            # 备用方案：使用启发式方法
            valid_bitrate = df['bitrate_kbps'] > 100
            valid_fps = df['decoded_fps'] > 5
            valid_transmission = valid_bitrate | valid_fps
            
            if valid_transmission.any():
                valid_indices = df[valid_transmission].index
                last_valid_time = df.loc[valid_indices[-1], 'time_s']
                time_limit = last_valid_time + 1.0
                print(f"[*] 未找到DTLS关闭事件，使用启发式方法")
                print(f"[*] 检测到有效数据传输时间范围: 0 - {last_valid_time:.1f} 秒")
                print(f"[*] 图表将显示时间范围: 0 - {time_limit:.1f} 秒")
            else:
                time_limit = df['time_s'].max()
                print("[*] 未检测到明确的传输结束标志，显示全部数据")
        
        plt.style.use('seaborn-v0_8-whitegrid')
        # 创建9个子图，竖直排列，统一时间轴
        fig, axes = plt.subplots(9, 1, figsize=(16, 30), sharex=True)
        fig.suptitle(f'WebRTC Receiver Video Quality Analysis (QoS + QoE)\n({self.log_file_path})', fontsize=16, fontweight='bold')

        # === QoS 指标 (管道质量) ===
        # 1. 丢包累计计数 (Packet Loss) - QoS指标
        axes[0].plot(df['time_s'], df['packets_lost'], 'o-', color='red', label='Cumulative Packets Lost', markersize=3)
        axes[0].fill_between(df['time_s'], df['packets_lost'], alpha=0.2, color='lightcoral')
        axes[0].set_ylabel('Packets Lost', fontsize=11)
        axes[0].set_title('QoS: Packet Loss Count Over Time', fontsize=12)
        axes[0].set_ylim(bottom=0)
        axes[0].grid(True, alpha=0.3)
        total_lost = df['packets_lost'].max() if not df['packets_lost'].isna().all() else 0
        axes[0].text(0.02, 0.95, f'Total: {total_lost:.0f}', transform=axes[0].transAxes, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5), fontsize=10)
        axes[0].legend(fontsize=10)

        # 2. 网络抖动 (Jitter) - QoS指标
        axes[1].plot(df['time_s'], df['jitter_ms'], 'o-', color='orange', label='Jitter (ms)', markersize=3)
        axes[1].fill_between(df['time_s'], df['jitter_ms'], alpha=0.2, color='lightyellow')
        axes[1].set_ylabel('Jitter (ms)', fontsize=11)
        axes[1].set_title('QoS: Network Jitter Over Time', fontsize=12)
        axes[1].set_ylim(bottom=0)
        axes[1].grid(True, alpha=0.3)
        # 计算jitter平均值（包含0值，因为0是有效的jitter值）
        avg_jitter = df['jitter_ms'].mean()
        axes[1].axhline(avg_jitter, color='red', linestyle='--', alpha=0.7, label=f'Avg: {avg_jitter:.1f} ms')
        axes[1].legend(fontsize=10)
        
        # === QoE 指标 (内容质量) ===
        # 3. 接收比特率 (Bitrate) - QoE指标
        axes[2].plot(df['time_s'], df['bitrate_kbps'], 'o-', color='navy', label='Received Bitrate (kbps)', markersize=3)
        axes[2].fill_between(df['time_s'], df['bitrate_kbps'], alpha=0.2, color='lightblue')
        axes[2].set_ylabel('Bitrate (kbps)', fontsize=11)
        axes[2].set_title('QoE: Video Bitrate Over Time', fontsize=12)
        axes[2].set_ylim(bottom=0)
        axes[2].grid(True, alpha=0.3)
        # 计算有效比特率（>0）的平均值用于参考线
        valid_bitrate = df[df['bitrate_kbps'] > 0]['bitrate_kbps']
        if not valid_bitrate.empty:
            avg_bitrate = valid_bitrate.mean()
            axes[2].axhline(avg_bitrate, color='red', linestyle='--', alpha=0.7, label=f'Avg (valid): {avg_bitrate:.0f} kbps')
        axes[2].legend(fontsize=10)

        # 4. 解码帧率 (Frame Rate) - QoE指标
        axes[3].plot(df['time_s'], df['decoded_fps'], 'o-', color='green', label='Decoded FPS', markersize=3)
        axes[3].fill_between(df['time_s'], df['decoded_fps'], alpha=0.2, color='lightgreen')
        axes[3].set_ylabel('Frames Per Second', fontsize=11)
        axes[3].set_title('QoE: Decoded Frame Rate Over Time', fontsize=12)
        axes[3].set_ylim(bottom=0)
        axes[3].grid(True, alpha=0.3)
        # 计算整体平均帧率
        avg_fps = df['decoded_fps'].mean()
        axes[3].axhline(avg_fps, color='red', linestyle='--', alpha=0.7, label=f'Avg: {avg_fps:.1f} FPS')
        axes[3].legend(fontsize=10)

        # 5. 视频冻结累计计数 (Freezes) - QoE指标
        axes[4].plot(df['time_s'], df['freeze_count'], 'o-', color='red', label='Cumulative Freeze Count', markersize=3)
        axes[4].fill_between(df['time_s'], df['freeze_count'], alpha=0.2, color='lightcoral')
        axes[4].set_ylabel('Freeze Count', fontsize=11)
        axes[4].set_title('QoE: Video Freeze Count Over Time', fontsize=12)
        axes[4].set_ylim(bottom=0)
        axes[4].grid(True, alpha=0.3)
        total_freezes = df['freeze_count'].max() if not df['freeze_count'].isna().all() else 0
        axes[4].text(0.02, 0.95, f'Total: {total_freezes:.0f}', transform=axes[4].transAxes, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5), fontsize=10)
        axes[4].legend(fontsize=10)

        # 6. 量化参数 (QP - 视频质量) - QoE指标
        # 显示所有QP数据，包括0值（意味着没有QP数据）
        axes[5].plot(df['time_s'], df['avg_qp'], 'o-', color='purple', label='Average QP', markersize=3)
        axes[5].fill_between(df['time_s'], df['avg_qp'], alpha=0.2, color='plum')
        axes[5].set_ylabel('Average QP', fontsize=11)
        axes[5].set_title('QoE: Video Quality (QP) - Lower is Better', fontsize=12)
        axes[5].set_ylim(bottom=0)
        axes[5].grid(True, alpha=0.3)
        # 只计算有效QP数据的平均值用于参考线
        valid_qp = df[df['avg_qp'] > 0]['avg_qp']
        if not valid_qp.empty:
            avg_qp = valid_qp.mean()
            axes[5].axhline(avg_qp, color='red', linestyle='--', alpha=0.7, label=f'Avg (valid): {avg_qp:.1f}')
        axes[5].legend(fontsize=10)

        # 7. 视频分辨率 (Resolution) - QoE指标
        if metrics_status['resolution']:
            # 有分辨率数据 - 显示分辨率级别变化
            resolution_data = df[(df['width'] > 0) & (df['height'] > 0)].copy()
            if not resolution_data.empty:
                # 创建分辨率级别映射（用于Y轴显示）
                resolution_levels = {
                    '640x360': 1,
                    '960x540': 2, 
                    '1280x720': 3,
                    '1920x1080': 4,
                    '1920x1200': 5,
                    '2560x1440': 6,
                    '3840x2160': 7
                }
                
                # 为每个数据点分配级别
                df['resolution_level'] = df['resolution_label'].map(resolution_levels).fillna(0)
                
                # 使用步进图显示分辨率变化，保持连续性
                df_filtered = df[df['resolution_level'] > 0].copy()
                if len(df_filtered) > 0:
                    # 对数据进行降采样，但保持连续性
                    # 每隔10个数据点取一个，减少密度但保持连续
                    step_size = max(1, len(df_filtered) // 200)  # 控制显示密度
                    df_sampled = df_filtered.iloc[::step_size].copy()
                    
                    # 确保包含最后一个数据点以保持完整性
                    if len(df_filtered) > 0 and df_filtered.index[-1] not in df_sampled.index:
                        df_sampled = pd.concat([df_sampled, df_filtered.iloc[[-1]]])
                    
                    if len(df_sampled) > 0:
                        # 绘制分辨率级别变化（使用步进线保持连续性）
                        axes[6].step(df_sampled['time_s'], df_sampled['resolution_level'], where='post', color='brown', label='Resolution Level', linewidth=2)
                        
                        # 设置Y轴标签为实际分辨率
                        yticks = []
                        ylabels = []
                        for res_label, level in resolution_levels.items():
                            if level in df_sampled['resolution_level'].values and level > 0:
                                yticks.append(level)
                                ylabels.append(res_label)
                        
                        if yticks:
                            axes[6].set_yticks(yticks)
                            axes[6].set_yticklabels(ylabels, fontsize=9)
            
            axes[6].set_ylabel('Resolution', fontsize=11)
            axes[6].set_title('QoE: Video Resolution Changes Over Time', fontsize=12)
            axes[6].set_ylim(bottom=0, top=max(yticks) + 0.5 if yticks else 8)
            axes[6].grid(True, alpha=0.3)
            axes[6].legend(fontsize=10)
        else:
            # 无分辨率数据 - 显示占位符
            self.plot_metric_placeholder(axes[6], 'resolution', 'Video Resolution')

        # 8. 不可解码帧数量 (Undecodable Frames Count) - QoE指标
        if metrics_status['undecodable']:
            # 有不可解码帧数据 - 显示绝对数量变化
            axes[7].plot(df['time_s'], df['undecodable_count'], 'o-', color='darkred', label='Undecodable Frame Count', markersize=3)
            axes[7].fill_between(df['time_s'], df['undecodable_count'], alpha=0.2, color='mistyrose')
            axes[7].set_ylabel('Undecodable Count', fontsize=11)
            axes[7].set_title('QoE: Undecodable Frame Count Over Time', fontsize=12)
            axes[7].set_ylim(bottom=0)
            axes[7].grid(True, alpha=0.3)
            
            # 显示总的不可解码帧数
            total_undecodable = df['undecodable_count'].max() if not df['undecodable_count'].isna().all() else 0
            axes[7].text(0.02, 0.95, f'Peak: {total_undecodable:.0f} frames', 
                        transform=axes[7].transAxes, 
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5), 
                        fontsize=10)
            axes[7].legend(fontsize=10)
        else:
            # 无不可解码帧数据 - 显示占位符
            self.plot_metric_placeholder(axes[7], 'undecodable', 'Undecodable Frame Count')

        # 9. 端到端延迟 (End-to-End Delay) - QoE指标 - 显示真实的延迟组件
        if metrics_status['e2e_delay']:
            # 有端到端延迟数据 - 显示多个真实的延迟组件
            delay_data = df[df['total_e2e_delay_ms'].notna() & (df['total_e2e_delay_ms'] > 0)].copy()
            
            if not delay_data.empty:
                # 绘制多个延迟组件
                x_data = delay_data['time_s'].values
                
                # 主延迟：当前播放延迟 (current_delay_ms)
                axes[8].plot(x_data, delay_data['current_delay_ms'], 'o-', color='indigo', label='Current Playout Delay (ms)', markersize=4, linewidth=2)
                
                # 目标延迟作为参考线
                if (delay_data['target_delay_ms'] > 0).any():
                    axes[8].plot(x_data, delay_data['target_delay_ms'], '--', color='orange', label='Target Delay (ms)', alpha=0.7, linewidth=1.5)
                
                # 抖动缓冲延迟
                if (delay_data['jitter_delay_ms'] > 0).any():
                    axes[8].plot(x_data, delay_data['jitter_delay_ms'], ':', color='green', label='Jitter Buffer Delay (ms)', alpha=0.8, linewidth=1.5)
                
                # 解码延迟
                if (delay_data['decode_ms'] > 0).any():
                    axes[8].plot(x_data, delay_data['decode_ms'], '-.', color='purple', label='Decode Delay (ms)', alpha=0.8, linewidth=1)
                
                # 填充当前延迟区域
                axes[8].fill_between(x_data, delay_data['current_delay_ms'], alpha=0.2, color='lavender')
                
                # 显示平均延迟
                avg_current_delay = delay_data['current_delay_ms'].mean()
                axes[8].axhline(avg_current_delay, color='red', linestyle='--', alpha=0.7, label=f'Avg Current: {avg_current_delay:.1f} ms')
            
            axes[8].set_ylabel('Delay (ms)', fontsize=11)
            axes[8].set_title('QoE: End-to-End Delay Components (Real Data)', fontsize=12)
            axes[8].set_ylim(bottom=0)
            axes[8].grid(True, alpha=0.3)
            axes[8].legend(fontsize=9, loc='upper left')
        else:
            # 无端到端延迟数据 - 显示占位符
            self.plot_metric_placeholder(axes[8], 'e2e_delay', 'End-to-End Delay')

        # 只为最后一个图添加x轴标签
        axes[8].set_xlabel('Time (seconds)', fontsize=12)
        
        # 设置所有子图的x轴范围，只显示有效数据传输的时间段
        for ax in axes:
            ax.set_xlim(0, time_limit)
        
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        # plt.show()  # 注释掉以避免在无界面环境下的问题
        
        return fig

def main():
    # 修改为你的接收端日志文件路径
    receiver_log_file = '/root/webrtc-cloud-server/webrtc_config_results/receiver_cloud.log' 
    
    try:
        analyzer = ReceiverQualityAnalyzer(receiver_log_file)
        quality_df = analyzer.parse_log_file()
        fig = analyzer.plot_quality_metrics(quality_df)
        
        if fig:
            import os
            output_dir = 'analysis_results'
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'receiver_quality_analysis.png')
            # 使用bbox_inches='tight'确保所有内容都被保存
            fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] 图表已保存到: {output_path}")
            
            # 同时保存一份调试版本
            debug_path = os.path.join(output_dir, 'receiver_quality_analysis_debug.png')
            fig.savefig(debug_path, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"[*] 调试版本已保存到: {debug_path}")

    except FileNotFoundError:
        print(f"[!] 错误: 文件未找到 '{receiver_log_file}'")
    except Exception as e:
        print(f"[!] 处理文件时发生未知错误: {e}")

if __name__ == "__main__":
    main()