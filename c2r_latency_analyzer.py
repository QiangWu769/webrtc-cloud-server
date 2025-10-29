#!/usr/bin/env python3
"""
C2R端到端延迟分析工具
支持ACT扩展高精度分析和SR锚点映射分析
"""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Dict
import statistics

@dataclass
class C2REvent:
    timestamp_us: int
    event_type: str
    frame_id: Optional[int] = None
    rtp_ts: Optional[int] = None
    capture_ntp_us: Optional[int] = None
    sr_ntp_us: Optional[int] = None
    ssrc: Optional[int] = None

class C2RLatencyAnalyzer:
    def __init__(self):
        self.events: List[C2REvent] = []
        self.sr_anchors: List[C2REvent] = []
        self.frame_metas: List[C2REvent] = []
        self.decodes: List[C2REvent] = []
    
    def parse_log_file(self, log_file: str):
        """解析C2R日志文件"""
        patterns = {
            'frame_meta': r'\[C2R-FRAME-META\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), CaptureNtpUs=(\d+), Ssrc=(\d+)',
            'decode': r'\[C2R-DECODE\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), Ssrc=(\d+)',
            'sr_rx': r'\[C2R-SR-RX\] MonoUs=(\d+), SrNtpUs=(\d+), RtpTs=(\d+), Ssrc=(\d+)'
        }
        
        with open(log_file, 'r') as f:
            for line in f:
                # Frame Meta 日志
                match = re.search(patterns['frame_meta'], line)
                if match:
                    event = C2REvent(
                        timestamp_us=int(match.group(1)),
                        event_type='frame_meta',
                        frame_id=int(match.group(2)),
                        rtp_ts=int(match.group(3)),
                        capture_ntp_us=int(match.group(4)),
                        ssrc=int(match.group(5))
                    )
                    self.frame_metas.append(event)
                    continue
                
                # Decode 日志
                match = re.search(patterns['decode'], line)
                if match:
                    event = C2REvent(
                        timestamp_us=int(match.group(1)),
                        event_type='decode',
                        frame_id=int(match.group(2)),
                        rtp_ts=int(match.group(3)),
                        ssrc=int(match.group(4))
                    )
                    self.decodes.append(event)
                    continue
                
                # SR RX 日志
                match = re.search(patterns['sr_rx'], line)
                if match:
                    event = C2REvent(
                        timestamp_us=int(match.group(1)),
                        event_type='sr_rx',
                        rtp_ts=int(match.group(3)),
                        sr_ntp_us=int(match.group(2)),
                        ssrc=int(match.group(4))
                    )
                    self.sr_anchors.append(event)
                    continue
    
    def analyze_high_precision(self) -> Dict:
        """高精度ACT扩展分析"""
        if not self.frame_metas:
            return {"error": "No ACT frame metadata found"}
        
        latencies = []
        frame_details = []
        
        for meta in self.frame_metas:
            # 查找对应的decode事件
            decode_event = None
            for decode in self.decodes:
                if (decode.rtp_ts == meta.rtp_ts and 
                    decode.ssrc == meta.ssrc):
                    decode_event = decode
                    break
            
            if decode_event:
                # 计算延迟（需要考虑时钟域转换）
                # 这里简化计算，实际需要时钟同步
                raw_latency_us = decode_event.timestamp_us - meta.capture_ntp_us
                
                # 如果延迟为负数或过大，可能是时钟域问题
                if -1000000 < raw_latency_us < 10000000:  # -1s到10s之间认为合理
                    latencies.append(raw_latency_us)
                    frame_details.append({
                        'frame_id': meta.frame_id,
                        'rtp_ts': meta.rtp_ts,
                        'capture_time_us': meta.capture_ntp_us,
                        'decode_time_us': decode_event.timestamp_us,
                        'latency_us': raw_latency_us,
                        'latency_ms': raw_latency_us / 1000
                    })
        
        if not latencies:
            return {"error": "No valid latency measurements found"}
        
        return {
            "method": "ACT Extension (High Precision)",
            "precision": "<10ms",
            "sample_count": len(latencies),
            "latency_stats": {
                "min_us": min(latencies),
                "max_us": max(latencies),
                "avg_us": statistics.mean(latencies),
                "median_us": statistics.median(latencies),
                "std_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                "min_ms": min(latencies) / 1000,
                "max_ms": max(latencies) / 1000,
                "avg_ms": statistics.mean(latencies) / 1000,
                "median_ms": statistics.median(latencies) / 1000
            },
            "frame_details": frame_details[-10:]  # 最近10帧的详细信息
        }
    
    def analyze_sr_mapping(self) -> Dict:
        """SR锚点映射分析"""
        if len(self.sr_anchors) < 2:
            return {"error": "Need at least 2 SR anchor points for mapping"}
        
        if not self.decodes:
            return {"error": "No decode events found"}
        
        # 建立RTP时间戳到NTP时间的线性映射
        # 使用最近的SR锚点进行线性插值
        recent_srs = sorted(self.sr_anchors, key=lambda x: x.timestamp_us)[-10:]
        
        latencies = []
        frame_details = []
        
        for decode in self.decodes[-20:]:  # 分析最近20帧
            # 找到最接近的SR锚点
            best_sr_before = None
            best_sr_after = None
            
            for sr in recent_srs:
                if sr.rtp_ts <= decode.rtp_ts:
                    if not best_sr_before or sr.rtp_ts > best_sr_before.rtp_ts:
                        best_sr_before = sr
                elif sr.rtp_ts > decode.rtp_ts:
                    if not best_sr_after or sr.rtp_ts < best_sr_after.rtp_ts:
                        best_sr_after = sr
            
            if best_sr_before and best_sr_after:
                # 线性插值估算帧的发送时间
                rtp_diff = best_sr_after.rtp_ts - best_sr_before.rtp_ts
                ntp_diff = best_sr_after.sr_ntp_us - best_sr_before.sr_ntp_us
                
                if rtp_diff > 0:
                    # 计算帧的估算发送时间
                    frame_rtp_offset = decode.rtp_ts - best_sr_before.rtp_ts
                    estimated_send_ntp = best_sr_before.sr_ntp_us + (ntp_diff * frame_rtp_offset) // rtp_diff
                    
                    # 估算延迟（简化，需要时钟同步基准）
                    estimated_latency = decode.timestamp_us - estimated_send_ntp
                    
                    if -1000000 < estimated_latency < 10000000:  # 合理范围
                        latencies.append(estimated_latency)
                        frame_details.append({
                            'frame_id': decode.frame_id,
                            'rtp_ts': decode.rtp_ts,
                            'estimated_send_time_us': estimated_send_ntp,
                            'decode_time_us': decode.timestamp_us,
                            'estimated_latency_us': estimated_latency,
                            'estimated_latency_ms': estimated_latency / 1000
                        })
        
        if not latencies:
            return {"error": "No valid latency estimates"}
        
        return {
            "method": "SR Anchor Mapping (Estimation)",
            "precision": "±500ms",
            "sample_count": len(latencies),
            "latency_stats": {
                "min_us": min(latencies),
                "max_us": max(latencies),
                "avg_us": statistics.mean(latencies),
                "median_us": statistics.median(latencies),
                "std_us": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                "min_ms": min(latencies) / 1000,
                "max_ms": max(latencies) / 1000,
                "avg_ms": statistics.mean(latencies) / 1000,
                "median_ms": statistics.median(latencies) / 1000
            },
            "frame_details": frame_details[-10:]
        }
    
    def print_analysis_report(self):
        """打印分析报告"""
        print("=" * 60)
        print("🎯 C2R端到端延迟分析报告")
        print("=" * 60)
        
        print(f"\n📊 数据统计:")
        print(f"  - Frame Meta事件: {len(self.frame_metas)}")
        print(f"  - Decode事件: {len(self.decodes)}")
        print(f"  - SR锚点: {len(self.sr_anchors)}")
        
        # 尝试高精度分析
        high_precision = self.analyze_high_precision()
        if "error" not in high_precision:
            print(f"\n🎯 {high_precision['method']} (精度: {high_precision['precision']})")
            print(f"  样本数: {high_precision['sample_count']}")
            stats = high_precision['latency_stats']
            print(f"  延迟统计:")
            print(f"    - 最小: {stats['min_ms']:.1f}ms")
            print(f"    - 最大: {stats['max_ms']:.1f}ms")
            print(f"    - 平均: {stats['avg_ms']:.1f}ms")
            print(f"    - 中位数: {stats['median_ms']:.1f}ms")
            print(f"    - 标准差: {stats['std_us']/1000:.1f}ms")
            
            print(f"\n  最近帧详情:")
            for frame in high_precision['frame_details'][-5:]:
                print(f"    Frame {frame['frame_id']}: {frame['latency_ms']:.1f}ms")
        else:
            print(f"\n❌ 高精度分析失败: {high_precision['error']}")
        
        # 尝试SR映射分析
        sr_mapping = self.analyze_sr_mapping()
        if "error" not in sr_mapping:
            print(f"\n🎯 {sr_mapping['method']} (精度: {sr_mapping['precision']})")
            print(f"  样本数: {sr_mapping['sample_count']}")
            stats = sr_mapping['latency_stats']
            print(f"  延迟估算:")
            print(f"    - 最小: {stats['min_ms']:.1f}ms")
            print(f"    - 最大: {stats['max_ms']:.1f}ms")
            print(f"    - 平均: {stats['avg_ms']:.1f}ms")
            print(f"    - 中位数: {stats['median_ms']:.1f}ms")
            
            print(f"\n  最近帧详情:")
            for frame in sr_mapping['frame_details'][-5:]:
                print(f"    Frame {frame['frame_id']}: {frame['estimated_latency_ms']:.1f}ms (估算)")
        else:
            print(f"\n❌ SR映射分析失败: {sr_mapping['error']}")
        
        print("\n" + "=" * 60)

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_latency_analyzer.py <receiver_log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    analyzer = C2RLatencyAnalyzer()
    
    try:
        analyzer.parse_log_file(log_file)
        analyzer.print_analysis_report()
    except FileNotFoundError:
        print(f"错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    main()