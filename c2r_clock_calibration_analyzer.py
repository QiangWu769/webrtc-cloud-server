#!/usr/bin/env python3
"""
C2R时钟校准分析器 - 基于ACT和RTCP SR的相对时钟校准
实现真正的端到端延迟测量，无需外部时钟同步
"""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import statistics
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

@dataclass
class SREvent:
    """RTCP SR事件"""
    rx_mono_us: int      # 接收端单调时钟(接收SR的时间)
    send_ntp_us: int     # 发送端NTP时间戳
    send_rtp_ts: int     # 发送端RTP时间戳
    ssrc: int

@dataclass
class FrameEvent:
    """帧事件（带ACT扩展）"""
    assembly_mono_us: int   # 帧组装完成时间(接收端单调时钟)
    decode_mono_us: int     # 解码完成时间(接收端单调时钟)
    capture_ntp_us: int     # 采集时间(发送端NTP时间)
    rtp_ts: int
    frame_id: int
    ssrc: int

class ClockCalibrator:
    """时钟校准器"""
    
    def __init__(self):
        self.sr_events: List[SREvent] = []
        self.frame_events: List[FrameEvent] = []
        self.calibration_params = None
    
    def add_sr_event(self, sr: SREvent):
        """添加SR事件"""
        self.sr_events.append(sr)
    
    def add_frame_event(self, frame: FrameEvent):
        """添加帧事件"""
        self.frame_events.append(frame)
    
    def calibrate_clocks(self, window_size: int = 30) -> Dict:
        """
        执行时钟校准
        建立映射关系: 发送端NTP时间 ↔ 接收端单调时钟
        
        使用滚动窗口线性回归：
        rx_mono_us = α * send_ntp_us + β
        """
        if len(self.sr_events) < 5:
            return {"error": "需要至少5个SR锚点进行校准"}
        
        # 按时间排序
        sorted_srs = sorted(self.sr_events, key=lambda x: x.rx_mono_us)
        
        # 使用最近的SR事件进行线性回归
        recent_srs = sorted_srs[-window_size:]
        
        # 提取数据用于线性回归
        send_ntp_times = np.array([sr.send_ntp_us for sr in recent_srs])
        rx_mono_times = np.array([sr.rx_mono_us for sr in recent_srs])
        
        # 执行线性回归: rx_mono = α * send_ntp + β
        slope, intercept, r_value, p_value, std_err = stats.linregress(send_ntp_times, rx_mono_times)
        
        r_squared = r_value ** 2
        
        # 验证校准质量
        quality = "优秀" if r_squared >= 0.98 else "良好" if r_squared >= 0.95 else "一般" if r_squared >= 0.90 else "较差"
        
        self.calibration_params = {
            'slope': slope,           # α 斜率
            'intercept': intercept,   # β 截距  
            'r_squared': r_squared,   # R² 相关系数
            'sample_count': len(recent_srs),
            'quality': quality,
            'std_error': std_err,
            'time_range_s': (rx_mono_times[-1] - rx_mono_times[0]) / 1000000
        }
        
        return self.calibration_params
    
    def convert_ntp_to_mono(self, send_ntp_us: int) -> Optional[int]:
        """
        将发送端NTP时间转换为对应的接收端单调时钟时间
        使用校准参数: rx_mono = α * send_ntp + β
        """
        if not self.calibration_params:
            return None
        
        return int(self.calibration_params['slope'] * send_ntp_us + self.calibration_params['intercept'])
    
    def calculate_end_to_end_latencies(self) -> List[Dict]:
        """计算端到端延迟"""
        if not self.calibration_params:
            return []
        
        latencies = []
        
        for frame in self.frame_events:
            # 将帧的采集时间(发送端NTP)转换为接收端单调时钟时间
            estimated_capture_mono_us = self.convert_ntp_to_mono(frame.capture_ntp_us)
            
            if estimated_capture_mono_us:
                # 计算端到端延迟
                e2e_latency_us = frame.assembly_mono_us - estimated_capture_mono_us
                
                # 合理性检查
                if 0 < e2e_latency_us < 10000000:  # 0-10秒范围
                    latency_info = {
                        'frame_id': frame.frame_id,
                        'rtp_ts': frame.rtp_ts,
                        'capture_time_ntp': frame.capture_ntp_us,
                        'assembly_time_mono': frame.assembly_mono_us,
                        'decode_time_mono': frame.decode_mono_us,
                        'estimated_capture_mono': estimated_capture_mono_us,
                        'e2e_latency_us': e2e_latency_us,
                        'e2e_latency_ms': e2e_latency_us / 1000,
                        'processing_latency_us': frame.decode_mono_us - frame.assembly_mono_us,
                        'processing_latency_ms': (frame.decode_mono_us - frame.assembly_mono_us) / 1000
                    }
                    latencies.append(latency_info)
        
        return latencies

def parse_logs_for_calibration(log_file: str) -> ClockCalibrator:
    """解析日志文件，提取校准所需的数据"""
    calibrator = ClockCalibrator()
    
    patterns = {
        'sr_rx': r'\[C2R-SR-RX\] MonoUs=(\d+), SrNtpUs=(\d+), RtpTs=(\d+), Ssrc=(\d+)',
        'frame_meta': r'\[C2R-FRAME-META\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), CaptureNtpUs=(\d+), Ssrc=(\d+)',
        'decode': r'\[C2R-DECODE\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), Ssrc=(\d+)'
    }
    
    frame_metas = {}  # rtp_ts -> frame_meta
    decodes = {}      # rtp_ts -> decode
    
    with open(log_file, 'r') as f:
        for line in f:
            # 解析SR事件
            match = re.search(patterns['sr_rx'], line)
            if match:
                sr = SREvent(
                    rx_mono_us=int(match.group(1)),
                    send_ntp_us=int(match.group(2)),
                    send_rtp_ts=int(match.group(3)),
                    ssrc=int(match.group(4))
                )
                calibrator.add_sr_event(sr)
            
            # 解析Frame Meta事件
            match = re.search(patterns['frame_meta'], line)
            if match:
                frame_metas[int(match.group(3))] = {
                    'assembly_mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5))
                }
            
            # 解析Decode事件
            match = re.search(patterns['decode'], line)
            if match:
                decodes[int(match.group(3))] = {
                    'decode_mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                }
    
    # 匹配frame_meta和decode事件
    for rtp_ts, meta in frame_metas.items():
        # 寻找最接近的decode事件
        best_decode = None
        min_rtp_diff = float('inf')
        
        for decode_rtp, decode in decodes.items():
            rtp_diff = abs(decode_rtp - rtp_ts)
            if rtp_diff < min_rtp_diff and decode['ssrc'] == meta['ssrc']:
                min_rtp_diff = rtp_diff
                best_decode = decode
        
        if best_decode and min_rtp_diff < 9000:  # RTP差值小于100ms
            frame_event = FrameEvent(
                assembly_mono_us=meta['assembly_mono_us'],
                decode_mono_us=best_decode['decode_mono_us'],
                capture_ntp_us=meta['capture_ntp_us'],
                rtp_ts=meta['rtp_ts'],
                frame_id=meta['frame_id'],
                ssrc=meta['ssrc']
            )
            calibrator.add_frame_event(frame_event)
    
    return calibrator

def analyze_calibration_quality(calibrator: ClockCalibrator):
    """分析校准质量"""
    print("🔧 时钟校准分析")
    
    # 执行校准
    calib_result = calibrator.calibrate_clocks()
    
    if "error" in calib_result:
        print(f"   ❌ 校准失败: {calib_result['error']}")
        return False
    
    print(f"   📊 校准参数:")
    print(f"     - 样本数量: {calib_result['sample_count']}")
    print(f"     - 时间跨度: {calib_result['time_range_s']:.1f}秒")
    print(f"     - 相关系数 R²: {calib_result['r_squared']:.6f}")
    print(f"     - 校准质量: {calib_result['quality']}")
    print(f"     - 标准误差: {calib_result['std_error']:.2f}")
    
    print(f"   🔍 映射关系:")
    print(f"     rx_mono_us = {calib_result['slope']:.6f} * send_ntp_us + {calib_result['intercept']:.0f}")
    
    if calib_result['r_squared'] < 0.95:
        print(f"   ⚠️  警告: R²较低，校准质量可能不佳")
        print(f"       建议: 增加SR发送频率或检查时钟稳定性")
    
    return True

def analyze_end_to_end_latencies(calibrator: ClockCalibrator):
    """分析端到端延迟"""
    print(f"\n🎯 端到端延迟分析 (基于时钟校准)")
    
    latencies = calibrator.calculate_end_to_end_latencies()
    
    if not latencies:
        print(f"   ❌ 没有可分析的延迟数据")
        return
    
    e2e_delays = [lat['e2e_latency_ms'] for lat in latencies]
    processing_delays = [lat['processing_latency_ms'] for lat in latencies]
    
    print(f"   📊 端到端延迟统计 ({len(latencies)}个样本):")
    print(f"     - 平均延迟: {statistics.mean(e2e_delays):.1f}ms")
    print(f"     - 最小延迟: {min(e2e_delays):.1f}ms")
    print(f"     - 最大延迟: {max(e2e_delays):.1f}ms")
    print(f"     - 中位数延迟: {statistics.median(e2e_delays):.1f}ms")
    if len(e2e_delays) > 1:
        print(f"     - 标准差: {statistics.stdev(e2e_delays):.1f}ms")
    
    print(f"\n   📊 延迟分解:")
    print(f"     - 平均传输延迟: {statistics.mean(e2e_delays) - statistics.mean(processing_delays):.1f}ms")
    print(f"     - 平均处理延迟: {statistics.mean(processing_delays):.1f}ms")
    
    print(f"\n   🔍 最近10帧详情:")
    for lat in latencies[-10:]:
        print(f"     Frame {lat['frame_id']:4d}: E2E={lat['e2e_latency_ms']:6.1f}ms, "
              f"Proc={lat['processing_latency_ms']:5.1f}ms, "
              f"Net={lat['e2e_latency_ms']-lat['processing_latency_ms']:5.1f}ms")
    
    # 延迟分布分析
    if len(e2e_delays) >= 10:
        print(f"\n   📈 延迟分布:")
        percentiles = [50, 90, 95, 99]
        for p in percentiles:
            value = np.percentile(e2e_delays, p)
            print(f"     - P{p}: {value:.1f}ms")

def generate_calibration_plot(calibrator: ClockCalibrator, output_file: str = None):
    """生成校准可视化图表"""
    if not calibrator.calibration_params:
        return
    
    try:
        # 准备数据
        recent_srs = sorted(calibrator.sr_events, key=lambda x: x.rx_mono_us)[-30:]
        send_ntp_times = [sr.send_ntp_us for sr in recent_srs]
        rx_mono_times = [sr.rx_mono_us for sr in recent_srs]
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # 子图1: 时钟校准散点图
        ax1.scatter(send_ntp_times, rx_mono_times, alpha=0.6, s=30)
        
        # 绘制拟合直线
        slope = calibrator.calibration_params['slope']
        intercept = calibrator.calibration_params['intercept']
        line_x = np.array(send_ntp_times)
        line_y = slope * line_x + intercept
        ax1.plot(line_x, line_y, 'r-', linewidth=2, label=f'拟合直线 (R²={calibrator.calibration_params["r_squared"]:.4f})')
        
        ax1.set_xlabel('发送端NTP时间 (微秒)')
        ax1.set_ylabel('接收端单调时钟 (微秒)')
        ax1.set_title('时钟校准: 发送端NTP时间 vs 接收端单调时钟')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 子图2: 端到端延迟时间序列
        latencies = calibrator.calculate_end_to_end_latencies()
        if latencies:
            frame_times = [lat['assembly_time_mono'] / 1000000 for lat in latencies]  # 转换为秒
            e2e_delays = [lat['e2e_latency_ms'] for lat in latencies]
            
            ax2.plot(frame_times, e2e_delays, 'b-', linewidth=1, alpha=0.7)
            ax2.scatter(frame_times, e2e_delays, s=20, alpha=0.6)
            
            ax2.set_xlabel('时间 (秒)')
            ax2.set_ylabel('端到端延迟 (毫秒)')
            ax2.set_title('端到端延迟时间序列')
            ax2.grid(True, alpha=0.3)
            
            # 添加统计信息
            avg_delay = statistics.mean(e2e_delays)
            ax2.axhline(y=avg_delay, color='r', linestyle='--', alpha=0.7, label=f'平均延迟: {avg_delay:.1f}ms')
            ax2.legend()
        
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"   📊 图表已保存到: {output_file}")
        else:
            plt.show()
            
    except ImportError:
        print(f"   ⚠️  matplotlib未安装，跳过图表生成")
    except Exception as e:
        print(f"   ❌ 图表生成失败: {e}")

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_clock_calibration_analyzer.py <receiver_log_file>")
        print("示例: python3 c2r_clock_calibration_analyzer.py webrtc_config_results/receiver_cloud.log")
        print("\n需要安装依赖:")
        print("pip install numpy scipy matplotlib")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        # 解析日志并建立校准器
        calibrator = parse_logs_for_calibration(log_file)
        
        print("=" * 85)
        print("🎯 C2R时钟校准分析 - 真正的端到端延迟测量")
        print("=" * 85)
        
        print(f"\n📊 数据统计:")
        print(f"  - RTCP SR锚点: {len(calibrator.sr_events)}")
        print(f"  - ACT扩展帧: {len(calibrator.frame_events)}")
        
        if len(calibrator.sr_events) < 5:
            print(f"  ❌ SR锚点不足，需要至少5个进行校准")
            return
        
        if len(calibrator.frame_events) == 0:
            print(f"  ❌ 没有ACT扩展帧数据")
            return
        
        # 执行时钟校准分析
        if analyze_calibration_quality(calibrator):
            # 分析端到端延迟
            analyze_end_to_end_latencies(calibrator)
            
            # 生成可视化图表
            generate_calibration_plot(calibrator, "c2r_calibration_analysis.png")
        
        print(f"\n💡 方法说明:")
        print(f"  🔧 时钟校准原理:")
        print(f"    1. 使用RTCP SR建立: 发送端NTP时间 ↔ 接收端单调时钟的映射")
        print(f"    2. 线性回归拟合: rx_mono = α * send_ntp + β")
        print(f"    3. 将ACT的采集时间转换为接收端时钟基准")
        print(f"    4. 计算真实延迟: 接收时间 - 校准后的采集时间")
        
        print(f"\n  ✅ 优势:")
        print(f"    - 无需外部时钟同步")
        print(f"    - 利用WebRTC标准协议")
        print(f"    - 自动时钟漂移校正")
        print(f"    - 高精度延迟测量")
        
        print("=" * 85)
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except ImportError as e:
        print(f"❌ 依赖缺失: {e}")
        print(f"请安装: pip install numpy scipy matplotlib")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()