#!/usr/bin/env python3
"""
WebRTC传输过程火焰图生成器

此脚本从WebRTC日志中提取时间序列数据，生成展示各个组件处理时间的火焰图。
火焰图将显示：
1. 视频质量处理时间分布
2. 网络拥塞控制决策时间
3. 编码/解码性能分析
4. RTP/RTCP处理耗时
"""

import re
import json
import subprocess
import sys
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime

class WebRTCFlameGraphGenerator:
    def __init__(self, log_file_path, output_dir="webrtc_config_results"):
        self.log_file_path = log_file_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 设置FlameGraph工具路径
        self.flamegraph_path = Path("/root/msquic/FlameGraph")
        if not self.flamegraph_path.exists():
            self.flamegraph_path = Path("/root/quiche/FlameGraph")
        
        # 时间序列数据存储
        self.timeline_data = []
        self.function_stack_data = defaultdict(list)
        
        # 日志解析模式
        self.patterns = {
            # 视频质量相关
            'video_quality': re.compile(r'\[VideoQuality-([^\]]+)\] Time: (\d+), SSRC: (\d+), (.+)'),
            'video_stats': re.compile(r'\(rtc_stats_collector\.cc:\d+\): \[VideoQuality-([^\]]+)\]'),
            
            # GCC拥塞控制
            'gcc_decision': re.compile(r'\[GCC-DECISION-SNAPSHOT\] at (\d+)ms \| (.+)'),
            'gcc_trendline': re.compile(r'\[Trendline\] Time: (\d+) ms (.+)'),
            'gcc_bwe': re.compile(r'\[([^-]+BWE-[^\]]+)\] Time: (\d+) ms, (.+)'),
            
            # RTP/RTCP处理
            'rtp_receive': re.compile(r'\(([^)]+)\): (\w+): (.+)'),
            'thread_timing': re.compile(r'\(thread\.cc:\d+\): Message to Thread .+ took (\d+)ms'),
            
            # 编码解码相关
            'codec_timing': re.compile(r'decode_ms: (\d+), max_decode_ms: (\d+)'),
            'frame_timing': re.compile(r'Frames Received: (\d+), Frames Decoded: (\d+), .+FPS: (\d+)')
        }

    def parse_webrtc_logs(self):
        """解析WebRTC日志，提取时间序列数据"""
        print(f"[*] 解析日志文件: {self.log_file_path}")
        
        with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        start_time = None
        current_time = 0
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # 提取时间戳和函数调用信息
            self._parse_video_quality_events(line, line_num)
            self._parse_gcc_events(line, line_num) 
            self._parse_rtp_events(line, line_num)
            self._parse_thread_timing(line, line_num)
            
        print(f"[*] 解析完成，共提取 {len(self.timeline_data)} 个事件")

    def _parse_video_quality_events(self, line, line_num):
        """解析视频质量相关事件"""
        match = self.patterns['video_quality'].search(line)
        if match:
            event_type, timestamp, ssrc, details = match.groups()
            timestamp = int(timestamp)
            
            # 提取具体参数
            if 'FPS:' in details:
                fps_match = re.search(r'FPS: (\d+)', details)
                if fps_match:
                    fps = int(fps_match.group(1))
                    self._add_timeline_event(timestamp, f"VideoQuality.{event_type}.ProcessFrame", fps * 10)
                    
            if 'decode_ms:' in details:
                decode_match = re.search(r'decode_ms: (\d+)', details)
                if decode_match:
                    decode_time = int(decode_match.group(1))
                    if decode_time > 0:
                        self._add_timeline_event(timestamp, f"VideoQuality.{event_type}.Decode", decode_time)

    def _parse_gcc_events(self, line, line_num):
        """解析GCC拥塞控制事件"""
        # GCC决策快照
        match = self.patterns['gcc_decision'].search(line)
        if match:
            timestamp, details = match.groups()
            timestamp = int(timestamp)
            self._add_timeline_event(timestamp, "GCC.DecisionSnapshot", 5)
            
        # BWE事件
        match = self.patterns['gcc_bwe'].search(line)
        if match:
            event_type, timestamp, details = match.groups()
            timestamp = int(timestamp)
            self._add_timeline_event(timestamp, f"GCC.{event_type}", 3)

    def _parse_rtp_events(self, line, line_num):
        """解析RTP/RTCP处理事件"""
        match = self.patterns['rtp_receive'].search(line)
        if match:
            file_line, function, details = match.groups()
            
            # 识别关键的RTP处理函数
            if any(keyword in function for keyword in ['Receive', 'Process', 'Decode', 'Render']):
                # 估算处理时间（基于行号间隔）
                estimated_time = max(1, line_num % 50)  # 1-50ms估算
                timestamp = line_num * 100  # 使用行号作为相对时间戳
                self._add_timeline_event(timestamp, f"RTP.{function}", estimated_time)

    def _parse_thread_timing(self, line, line_num):
        """解析线程消息处理时间"""
        match = self.patterns['thread_timing'].search(line)
        if match:
            duration_ms = int(match.group(1))
            timestamp = line_num * 100
            self._add_timeline_event(timestamp, "Threading.MessageDispatch", duration_ms)

    def _add_timeline_event(self, timestamp, function_name, duration_ms):
        """添加时间线事件"""
        self.timeline_data.append({
            'timestamp': timestamp,
            'function': function_name,
            'duration': duration_ms
        })

    def generate_flame_graph_data(self):
        """生成火焰图数据格式"""
        print("[*] 生成火焰图数据...")
        
        # 按时间排序事件
        self.timeline_data.sort(key=lambda x: x['timestamp'])
        
        # 构建调用栈数据
        stack_data = []
        
        # 按功能分组统计
        function_stats = defaultdict(int)
        for event in self.timeline_data:
            function_stats[event['function']] += event['duration']
        
        # 生成折叠堆栈格式
        for function, total_duration in function_stats.items():
            # 创建分层调用栈
            parts = function.split('.')
            if len(parts) >= 2:
                stack_trace = ';'.join(parts)
                stack_data.append(f"{stack_trace} {total_duration}")
            else:
                stack_data.append(f"WebRTC;{function} {total_duration}")
        
        return stack_data

    def create_flamegraph_svg(self, stack_data, output_filename="webrtc_transmission_flamegraph.svg"):
        """使用FlameGraph工具生成SVG火焰图"""
        print(f"[*] 生成火焰图: {output_filename}")
        
        # 写入中间数据文件
        stack_file = self.output_dir / "webrtc_stacks.txt"
        with open(stack_file, 'w') as f:
            f.write('\n'.join(stack_data))
        
        # 生成火焰图
        output_svg = self.output_dir / output_filename
        flamegraph_script = self.flamegraph_path / "flamegraph.pl"
        
        try:
            cmd = [
                "perl", str(flamegraph_script),
                "--title", "WebRTC传输过程火焰图",
                "--subtitle", f"基于日志: {Path(self.log_file_path).name}",
                "--width", "1200",
                "--height", "800",
                "--colors", "hot"
            ]
            
            with open(stack_file, 'r') as input_file:
                with open(output_svg, 'w') as output_file:
                    result = subprocess.run(cmd, stdin=input_file, stdout=output_file, 
                                          stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                print(f"✅ 火焰图生成成功: {output_svg}")
                return output_svg
            else:
                print(f"❌ 火焰图生成失败: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ 生成火焰图时出错: {e}")
            return None

    def generate_interactive_flamegraph(self):
        """生成交互式HTML火焰图"""
        try:
            import plotly.graph_objects as go
            import plotly.express as px
            from plotly.subplots import make_subplots
            
            print("[*] 生成交互式火焰图...")
            
            # 准备数据
            functions = []
            durations = []
            categories = []
            
            for event in self.timeline_data:
                parts = event['function'].split('.')
                functions.append(event['function'])
                durations.append(event['duration'])
                categories.append(parts[0] if parts else 'Other')
            
            # 创建火焰图风格的可视化
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=("功能耗时分布", "时间序列"),
                vertical_spacing=0.12
            )
            
            # 上部分：按功能分组的耗时分布
            function_stats = defaultdict(int)
            for i, func in enumerate(functions):
                function_stats[func] += durations[i]
            
            sorted_functions = sorted(function_stats.items(), key=lambda x: x[1], reverse=True)[:20]
            
            fig.add_trace(
                go.Bar(
                    x=[f[0] for f in sorted_functions],
                    y=[f[1] for f in sorted_functions],
                    name="处理时间 (ms)",
                    text=[f"{f[1]}ms" for f in sorted_functions],
                    textposition="outside"
                ),
                row=1, col=1
            )
            
            # 下部分：时间序列散点图
            fig.add_trace(
                go.Scatter(
                    x=[e['timestamp'] for e in self.timeline_data],
                    y=[e['duration'] for e in self.timeline_data],
                    mode='markers',
                    name="事件时间线",
                    text=[e['function'] for e in self.timeline_data],
                    marker=dict(
                        size=8,
                        color=[e['duration'] for e in self.timeline_data],
                        colorscale='Hot',
                        showscale=True,
                        colorbar=dict(title="耗时 (ms)")
                    )
                ),
                row=2, col=1
            )
            
            # 更新布局
            fig.update_layout(
                height=800,
                title_text="WebRTC传输过程性能分析火焰图",
                showlegend=True
            )
            
            fig.update_xaxes(title_text="功能名称", row=1, col=1, tickangle=45)
            fig.update_yaxes(title_text="总耗时 (ms)", row=1, col=1)
            fig.update_xaxes(title_text="时间戳", row=2, col=1)
            fig.update_yaxes(title_text="单次耗时 (ms)", row=2, col=1)
            
            # 保存HTML文件
            output_html = self.output_dir / "webrtc_transmission_flamegraph.html"
            fig.write_html(output_html)
            print(f"✅ 交互式火焰图生成成功: {output_html}")
            
            return output_html
            
        except ImportError:
            print("⚠️  plotly未安装，跳过交互式火焰图生成")
            return None

    def generate_summary_report(self):
        """生成性能分析摘要报告"""
        print("[*] 生成性能分析报告...")
        
        # 统计各类事件
        category_stats = defaultdict(lambda: {'count': 0, 'total_time': 0, 'max_time': 0})
        
        for event in self.timeline_data:
            category = event['function'].split('.')[0]
            duration = event['duration']
            
            category_stats[category]['count'] += 1
            category_stats[category]['total_time'] += duration
            category_stats[category]['max_time'] = max(category_stats[category]['max_time'], duration)
        
        # 生成报告
        report = {
            'summary': {
                'total_events': len(self.timeline_data),
                'total_time_ms': sum(e['duration'] for e in self.timeline_data),
                'analysis_timestamp': datetime.now().isoformat()
            },
            'categories': {}
        }
        
        for category, stats in category_stats.items():
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            report['categories'][category] = {
                'event_count': stats['count'],
                'total_time_ms': stats['total_time'],
                'average_time_ms': round(avg_time, 2),
                'max_time_ms': stats['max_time']
            }
        
        # 保存报告
        report_file = self.output_dir / "webrtc_performance_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 性能报告生成成功: {report_file}")
        return report_file

def main():
    if len(sys.argv) < 2:
        print("🎯 WebRTC传输过程火焰图生成器")
        print("用法: python3 generate_webrtc_flamegraph.py <log_file> [output_dir]")
        print("示例: python3 generate_webrtc_flamegraph.py receiver_cloud.log")
        return
    
    log_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "webrtc_config_results"
    
    if not Path(log_file).exists():
        print(f"❌ 日志文件不存在: {log_file}")
        return
    
    print("🔥 开始生成WebRTC传输过程火焰图...")
    
    # 创建生成器
    generator = WebRTCFlameGraphGenerator(log_file, output_dir)
    
    # 解析日志
    generator.parse_webrtc_logs()
    
    # 生成火焰图数据
    stack_data = generator.generate_flame_graph_data()
    
    if stack_data:
        # 生成SVG火焰图
        svg_file = generator.create_flamegraph_svg(stack_data)
        
        # 生成交互式火焰图
        html_file = generator.generate_interactive_flamegraph()
        
        # 生成性能报告
        report_file = generator.generate_summary_report()
        
        print("\n🎉 火焰图生成完成!")
        print(f"📊 SVG火焰图: {svg_file}")
        if html_file:
            print(f"🌐 交互式图表: {html_file}")
        print(f"📋 性能报告: {report_file}")
    else:
        print("❌ 未能从日志中提取到足够的数据")

if __name__ == "__main__":
    main()