#!/usr/bin/env python3
"""
C2R NTP增强延迟分析器
利用接收端NTP同步实现真正的端到端延迟测量
"""

import re
import sys
import statistics
from typing import Dict, List, Optional, Tuple

def parse_ntp_enhanced_logs(log_file: str):
    """解析包含NTP同步信息的C2R日志"""
    sr_events = []
    frame_metas = []
    decode_events = []
    
    patterns = {
        # 增强的SR模式：包含本地NTP信息
        'sr_rx_enhanced': r'\[C2R-SR-RX\] MonoUs=(\d+), SrNtpUs=(\d+), RtpTs=(\d+), Ssrc=(\d+), MonoUs=(\d+), NtpUs=(\d+), UtcUs=(\d+), ClockOffsetUs=([-\d]+), NtpSyncGood=(YES|NO)',
        
        # 增强的Frame Meta模式：包含本地NTP信息
        'frame_meta_enhanced': r'\[C2R-FRAME-META\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), CaptureNtpUs=(\d+), Ssrc=(\d+), MonoUs=(\d+), NtpUs=(\d+), UtcUs=(\d+), ClockOffsetUs=([-\d]+)',
        
        # 原有模式兼容
        'sr_rx_legacy': r'\[C2R-SR-RX\] MonoUs=(\d+), SrNtpUs=(\d+), RtpTs=(\d+), Ssrc=(\d+)',
        'frame_meta_legacy': r'\[C2R-FRAME-META\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), CaptureNtpUs=(\d+), Ssrc=(\d+)',
        'decode': r'\[C2R-DECODE\] MonoUs=(\d+), FrameId=(\d+), RtpTs=(\d+), Ssrc=(\d+)'
    }
    
    with open(log_file, 'r') as f:
        for line in f:
            # 增强SR事件
            match = re.search(patterns['sr_rx_enhanced'], line)
            if match:
                sr_events.append({
                    'rx_mono_us': int(match.group(1)),
                    'send_ntp_us': int(match.group(2)),
                    'send_rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4)),
                    'local_mono_us': int(match.group(5)),
                    'local_ntp_us': int(match.group(6)),
                    'local_utc_us': int(match.group(7)),
                    'clock_offset_us': int(match.group(8)),
                    'ntp_sync_good': match.group(9) == 'YES',
                    'enhanced': True
                })
                continue
            
            # 兼容旧版SR事件
            match = re.search(patterns['sr_rx_legacy'], line)
            if match:
                sr_events.append({
                    'rx_mono_us': int(match.group(1)),
                    'send_ntp_us': int(match.group(2)),
                    'send_rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4)),
                    'enhanced': False
                })
                continue
            
            # 增强Frame Meta事件
            match = re.search(patterns['frame_meta_enhanced'], line)
            if match:
                frame_metas.append({
                    'assembly_mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5)),
                    'local_mono_us': int(match.group(6)),
                    'local_ntp_us': int(match.group(7)),
                    'local_utc_us': int(match.group(8)),
                    'clock_offset_us': int(match.group(9)),
                    'enhanced': True
                })
                continue
            
            # 兼容旧版Frame Meta事件
            match = re.search(patterns['frame_meta_legacy'], line)
            if match:
                frame_metas.append({
                    'assembly_mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'capture_ntp_us': int(match.group(4)),
                    'ssrc': int(match.group(5)),
                    'enhanced': False
                })
                continue
            
            # Decode事件
            match = re.search(patterns['decode'], line)
            if match:
                decode_events.append({
                    'decode_mono_us': int(match.group(1)),
                    'frame_id': int(match.group(2)),
                    'rtp_ts': int(match.group(3)),
                    'ssrc': int(match.group(4))
                })
    
    return sr_events, frame_metas, decode_events

def analyze_ntp_sync_quality(sr_events: List[Dict]) -> Dict:
    """分析NTP同步质量"""
    enhanced_srs = [sr for sr in sr_events if sr.get('enhanced', False)]
    
    if not enhanced_srs:
        return {'status': 'no_ntp_data', 'message': '没有NTP同步数据'}
    
    sync_good_count = sum(1 for sr in enhanced_srs if sr.get('ntp_sync_good', False))
    sync_ratio = sync_good_count / len(enhanced_srs)
    
    # 分析时钟偏移稳定性
    clock_offsets = [sr['clock_offset_us'] for sr in enhanced_srs if 'clock_offset_us' in sr]
    
    result = {
        'status': 'available',
        'total_samples': len(enhanced_srs),
        'sync_good_samples': sync_good_count,
        'sync_ratio': sync_ratio,
        'sync_quality': 'excellent' if sync_ratio >= 0.95 else 'good' if sync_ratio >= 0.8 else 'poor'
    }
    
    if clock_offsets:
        result.update({
            'clock_offset_mean_us': statistics.mean(clock_offsets),
            'clock_offset_stdev_us': statistics.stdev(clock_offsets) if len(clock_offsets) > 1 else 0,
            'clock_offset_range_us': [min(clock_offsets), max(clock_offsets)]
        })
    
    return result

def calculate_ntp_synchronized_latency(frame_metas: List[Dict]) -> List[Dict]:
    """使用NTP同步计算真正的端到端延迟"""
    ntp_latencies = []
    
    for frame in frame_metas:
        if not frame.get('enhanced', False):
            continue
        
        if not frame.get('local_ntp_us') or not frame.get('capture_ntp_us'):
            continue
        
        # 方法1：直接NTP域计算
        # 接收端NTP时间 - 发送端NTP时间（ACT）
        ntp_e2e_latency_us = frame['local_ntp_us'] - frame['capture_ntp_us']
        ntp_e2e_latency_ms = ntp_e2e_latency_us / 1000
        
        # 方法2：UTC域计算（更标准）
        if frame.get('local_utc_us'):
            # 将ACT的NTP时间转换为UTC时间
            EPOCH_DIFF_US = 2208988800 * 1000000  # NTP epoch (1900) to Unix epoch (1970)
            capture_utc_us = frame['capture_ntp_us'] - EPOCH_DIFF_US
            utc_e2e_latency_us = frame['local_utc_us'] - capture_utc_us
            utc_e2e_latency_ms = utc_e2e_latency_us / 1000
        else:
            utc_e2e_latency_ms = None
        
        # 合理性检查
        if -1000 < ntp_e2e_latency_ms < 10000:  # -1s到10s之间
            ntp_latencies.append({
                'frame_id': frame['frame_id'],
                'rtp_ts': frame['rtp_ts'],
                'ntp_latency_ms': ntp_e2e_latency_ms,
                'utc_latency_ms': utc_e2e_latency_ms,
                'capture_ntp_us': frame['capture_ntp_us'],
                'local_ntp_us': frame['local_ntp_us'],
                'local_utc_us': frame.get('local_utc_us', 0)
            })
    
    return ntp_latencies

def analyze_ntp_enhanced_latency(sr_events: List[Dict], frame_metas: List[Dict], decode_events: List[Dict]):
    """NTP增强延迟分析"""
    print("🎯 C2R NTP增强延迟分析")
    print("=" * 70)
    
    print(f"📊 数据统计:")
    print(f"  - SR锚点: {len(sr_events)} (增强: {sum(1 for sr in sr_events if sr.get('enhanced'))})")
    print(f"  - Frame Meta: {len(frame_metas)} (增强: {sum(1 for f in frame_metas if f.get('enhanced'))})")
    print(f"  - Decode事件: {len(decode_events)}")
    
    # 分析NTP同步质量
    ntp_quality = analyze_ntp_sync_quality(sr_events)
    print(f"\n🔧 NTP同步质量:")
    print(f"  - 状态: {ntp_quality['status']}")
    
    if ntp_quality['status'] == 'available':
        print(f"  - 同步样本: {ntp_quality['sync_good_samples']}/{ntp_quality['total_samples']}")
        print(f"  - 同步比率: {ntp_quality['sync_ratio']:.1%}")
        print(f"  - 同步质量: {ntp_quality['sync_quality']}")
        
        if 'clock_offset_mean_us' in ntp_quality:
            print(f"  - 时钟偏移均值: {ntp_quality['clock_offset_mean_us']/1000:.1f}ms")
            print(f"  - 时钟偏移标准差: {ntp_quality['clock_offset_stdev_us']/1000:.1f}ms")
    
    # NTP同步延迟计算
    if ntp_quality['status'] == 'available' and ntp_quality['sync_quality'] in ['good', 'excellent']:
        print(f"\n🎯 NTP同步端到端延迟:")
        
        ntp_latencies = calculate_ntp_synchronized_latency(frame_metas)
        
        if ntp_latencies:
            ntp_delays = [lat['ntp_latency_ms'] for lat in ntp_latencies]
            utc_delays = [lat['utc_latency_ms'] for lat in ntp_latencies if lat['utc_latency_ms'] is not None]
            
            print(f"  - 有效样本: {len(ntp_delays)}")
            print(f"  - NTP域延迟:")
            print(f"    平均: {statistics.mean(ntp_delays):.1f}ms")
            print(f"    范围: {min(ntp_delays):.1f}ms ~ {max(ntp_delays):.1f}ms")
            if len(ntp_delays) > 1:
                print(f"    标准差: {statistics.stdev(ntp_delays):.1f}ms")
            
            if utc_delays:
                print(f"  - UTC域延迟:")
                print(f"    平均: {statistics.mean(utc_delays):.1f}ms")
                print(f"    范围: {min(utc_delays):.1f}ms ~ {max(utc_delays):.1f}ms")
            
            # 显示最新几帧的详细信息
            print(f"\n  最新10帧详情:")
            for lat in ntp_latencies[-10:]:
                utc_info = f", UTC={lat['utc_latency_ms']:.1f}ms" if lat['utc_latency_ms'] else ""
                print(f"    Frame {lat['frame_id']:4d}: NTP={lat['ntp_latency_ms']:6.1f}ms{utc_info}")
        else:
            print(f"  ❌ 没有有效的NTP同步延迟数据")
    
    # 后退兼容：使用相对时钟校准方法
    print(f"\n📈 后退兼容分析 (相对时钟校准):")
    
    # 使用之前的方法2进行分析
    from c2r_correct_calibration import build_ntp_to_mono_mapping, estimate_frame_send_time_from_sr
    
    mapping = build_ntp_to_mono_mapping(sr_events)
    if mapping and mapping['r_squared'] > 0.9:
        print(f"  - 时钟映射质量: R²={mapping['r_squared']:.3f}")
        
        calibrated_delays = []
        for frame in frame_metas[-10:]:
            if frame.get('capture_ntp_us'):
                estimated_send_mono = mapping['slope'] * frame['capture_ntp_us'] + mapping['intercept']
                calib_latency_us = frame['assembly_mono_us'] - estimated_send_mono
                calib_latency_ms = calib_latency_us / 1000
                
                if -1000 < calib_latency_ms < 10000:
                    calibrated_delays.append(calib_latency_ms)
        
        if calibrated_delays:
            print(f"  - 校准延迟: 平均{statistics.mean(calibrated_delays):.1f}ms")
    else:
        print(f"  - 时钟校准失败或质量不佳")
    
    # 方法对比与建议
    print(f"\n💡 方法对比与建议:")
    if ntp_quality['status'] == 'available' and ntp_quality['sync_quality'] == 'excellent':
        print(f"  ✅ 推荐使用NTP同步方法 - 精度最高，无需校准")
        print(f"  🎯 可信度: 95%+ (真正的端到端延迟)")
    elif ntp_quality['status'] == 'available' and ntp_quality['sync_quality'] == 'good':
        print(f"  ✅ 可使用NTP同步方法 - 有一定精度")
        print(f"  📊 建议与相对校准方法交叉验证")
    else:
        print(f"  📊 使用相对时钟校准方法")
        print(f"  ⚠️  精度受限于时钟域映射质量")
    
    print("=" * 70)

def main():
    if len(sys.argv) != 2:
        print("用法: python3 c2r_ntp_enhanced_analyzer.py <receiver_log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        sr_events, frame_metas, decode_events = parse_ntp_enhanced_logs(log_file)
        analyze_ntp_enhanced_latency(sr_events, frame_metas, decode_events)
        
        print(f"\n🔬 NTP增强分析原理:")
        print(f"  1. 接收端同时记录单调时钟和NTP时间")
        print(f"  2. 发送端ACT扩展提供帧的NTP采集时间")
        print(f"  3. 直接在NTP域计算延迟: 接收NTP - 采集NTP")
        print(f"  4. 无需复杂的时钟域映射和校准")
        print(f"  5. 提供真正的端到端延迟测量")
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到日志文件 {log_file}")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()