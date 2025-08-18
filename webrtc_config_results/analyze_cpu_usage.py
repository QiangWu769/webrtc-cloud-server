#!/usr/bin/env python3
"""
WebRTC CPU使用情况分析器

基于perf采集的数据和火焰图，分析WebRTC传输过程中的CPU使用模式
"""

import re
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

class WebRTCCPUAnalyzer:
    def __init__(self, data_dir="webrtc_config_results"):
        self.data_dir = Path(data_dir)
        self.cpu_data = {}
        self.function_stats = defaultdict(dict)
        
    def parse_cpu_analysis_report(self, report_file):
        """解析CPU分析报告"""
        print(f"[*] 分析CPU报告: {report_file}")
        
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取基本信息
        info = {}
        info['sampling_duration'] = re.search(r'采集时长: (\d+)秒', content)
        info['target_processes'] = re.findall(r'目标进程: ([\d\s]+)', content)
        info['sample_count'] = re.search(r'Samples: (\d+[KM]?)', content)
        info['event_count'] = re.search(r'Event count \(approx\.\): (\d+)', content)
        
        # 解析CPU热点
        cpu_hotspots = []
        lines = content.split('\n')
        in_hotspot_section = False
        
        for line in lines:
            if 'Children      Self  Command' in line:
                in_hotspot_section = True
                continue
            
            if in_hotspot_section and line.strip().startswith('#'):
                continue
                
            if in_hotspot_section and line.strip():
                # 解析CPU占用行
                match = re.match(r'\s*(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\w+)\s+([^\s]+)\s+(.+)', line)
                if match:
                    children_pct, self_pct, command, shared_obj, symbol = match.groups()
                    cpu_hotspots.append({
                        'children_percent': float(children_pct),
                        'self_percent': float(self_pct),
                        'command': command,
                        'shared_object': shared_obj,
                        'symbol': symbol.split()[0]  # 只取第一部分
                    })
        
        return {
            'info': info,
            'hotspots': cpu_hotspots[:20]  # 取前20个热点
        }
    
    def categorize_functions(self, hotspots):
        """将函数按功能分类"""
        categories = {
            'Network I/O': [],
            'System Calls': [],
            'WebRTC Core': [],
            'Video Processing': [],
            'Audio Processing': [], 
            'Memory Management': [],
            'Threading': [],
            'Other': []
        }
        
        for hotspot in hotspots:
            symbol = hotspot['symbol'].lower()
            shared_obj = hotspot['shared_object'].lower()
            
            # 网络I/O
            if any(keyword in symbol for keyword in ['recvmsg', 'sendmsg', 'recv', 'send', 'socket', 'net']):
                categories['Network I/O'].append(hotspot)
            # 系统调用
            elif any(keyword in symbol for keyword in ['syscall', 'sys_', '__sys', 'entry_', 'kernel']):
                categories['System Calls'].append(hotspot)
            # WebRTC核心
            elif any(keyword in shared_obj for keyword in ['webrtc', 'peerconnection']):
                categories['WebRTC Core'].append(hotspot)
            # 视频处理
            elif any(keyword in symbol for keyword in ['video', 'frame', 'decode', 'encode', 'vp8', 'vp9', 'h264']):
                categories['Video Processing'].append(hotspot)
            # 音频处理
            elif any(keyword in symbol for keyword in ['audio', 'sound', 'pcm', 'opus']):
                categories['Audio Processing'].append(hotspot)
            # 内存管理
            elif any(keyword in symbol for keyword in ['malloc', 'free', 'alloc', 'mem', 'copy']):
                categories['Memory Management'].append(hotspot)
            # 线程相关
            elif any(keyword in symbol for keyword in ['thread', 'pthread', 'lock', 'mutex']):
                categories['Threading'].append(hotspot)
            else:
                categories['Other'].append(hotspot)
        
        return categories
    
    def create_cpu_usage_charts(self, hotspots, output_dir):
        """创建CPU使用情况图表"""
        print("[*] 生成CPU使用情况图表...")
        
        # 分类函数
        categories = self.categorize_functions(hotspots)
        
        # 计算每个分类的总CPU占用
        category_totals = {}
        for cat_name, funcs in categories.items():
            total = sum(func['children_percent'] for func in funcs)
            if total > 0:
                category_totals[cat_name] = total
        
        # 创建图表
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. 按分类的饼图
        if category_totals:
            labels = list(category_totals.keys())
            sizes = list(category_totals.values())
            colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
            
            wedges, texts, autotexts = ax1.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                              colors=colors, startangle=90)
            ax1.set_title('WebRTC CPU使用分类分布', fontsize=14, fontweight='bold')
        
        # 2. Top 15 函数横向条形图
        top_functions = sorted(hotspots, key=lambda x: x['children_percent'], reverse=True)[:15]
        if top_functions:
            func_names = [f"{func['symbol'][:30]}..." if len(func['symbol']) > 30 
                         else func['symbol'] for func in top_functions]
            func_percents = [func['children_percent'] for func in top_functions]
            
            y_pos = np.arange(len(func_names))
            bars = ax2.barh(y_pos, func_percents, color='lightcoral')
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(func_names, fontsize=8)
            ax2.set_xlabel('CPU占用率 (%)')
            ax2.set_title('Top 15 CPU热点函数', fontsize=14, fontweight='bold')
            ax2.invert_yaxis()
            
            # 添加数值标签
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax2.text(width + 0.1, bar.get_y() + bar.get_height()/2, 
                        f'{width:.1f}%', ha='left', va='center', fontsize=7)
        
        # 3. 网络I/O详细分析
        network_funcs = categories.get('Network I/O', [])
        if network_funcs:
            net_names = [f['symbol'][:20] for f in network_funcs[:10]]
            net_percents = [f['children_percent'] for f in network_funcs[:10]]
            
            bars = ax3.bar(range(len(net_names)), net_percents, color='skyblue')
            ax3.set_xticks(range(len(net_names)))
            ax3.set_xticklabels(net_names, rotation=45, ha='right', fontsize=8)
            ax3.set_ylabel('CPU占用率 (%)')
            ax3.set_title('网络I/O函数CPU使用情况', fontsize=14, fontweight='bold')
            
            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
        
        # 4. WebRTC核心组件分析
        webrtc_funcs = categories.get('WebRTC Core', [])
        if webrtc_funcs:
            webrtc_names = [f['symbol'][:20] for f in webrtc_funcs[:8]]
            webrtc_percents = [f['children_percent'] for f in webrtc_funcs[:8]]
            
            bars = ax4.bar(range(len(webrtc_names)), webrtc_percents, color='lightgreen')
            ax4.set_xticks(range(len(webrtc_names)))
            ax4.set_xticklabels(webrtc_names, rotation=45, ha='right', fontsize=8)
            ax4.set_ylabel('CPU占用率 (%)')
            ax4.set_title('WebRTC核心组件CPU使用情况', fontsize=14, fontweight='bold')
            
            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                ax4.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        # 保存图表
        output_file = output_dir / "webrtc_cpu_analysis_charts.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✅ CPU分析图表已保存: {output_file}")
        
        plt.close()
        return output_file
    
    def generate_summary_report(self, analysis_data, output_dir):
        """生成CPU使用情况摘要报告"""
        print("[*] 生成CPU使用摘要报告...")
        
        hotspots = analysis_data['hotspots']
        categories = self.categorize_functions(hotspots)
        
        # 计算分类统计
        category_stats = {}
        for cat_name, funcs in categories.items():
            if funcs:
                total_cpu = sum(f['children_percent'] for f in funcs)
                avg_cpu = total_cpu / len(funcs)
                max_cpu = max(f['children_percent'] for f in funcs)
                category_stats[cat_name] = {
                    'function_count': len(funcs),
                    'total_cpu_percent': round(total_cpu, 2),
                    'average_cpu_percent': round(avg_cpu, 2),
                    'max_cpu_percent': round(max_cpu, 2),
                    'top_function': max(funcs, key=lambda x: x['children_percent'])['symbol']
                }
        
        # 生成报告
        report = {
            'analysis_summary': {
                'total_hotspots': len(hotspots),
                'top_cpu_consumer': hotspots[0]['symbol'] if hotspots else 'N/A',
                'top_cpu_percent': hotspots[0]['children_percent'] if hotspots else 0,
                'analysis_timestamp': Path(list(self.data_dir.glob('*analysis*.txt'))[0]).stat().st_mtime
            },
            'category_breakdown': category_stats,
            'performance_insights': self._generate_insights(category_stats, hotspots)
        }
        
        # 保存JSON报告
        report_file = output_dir / "webrtc_cpu_summary.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 生成文本报告
        text_report = output_dir / "webrtc_cpu_summary.txt"
        self._write_text_report(report, text_report)
        
        print(f"✅ CPU摘要报告已保存: {report_file}")
        print(f"✅ 文本报告已保存: {text_report}")
        
        return report_file, text_report
    
    def _generate_insights(self, category_stats, hotspots):
        """生成性能洞察"""
        insights = []
        
        # 网络I/O分析
        network_cpu = category_stats.get('Network I/O', {}).get('total_cpu_percent', 0)
        if network_cpu > 15:
            insights.append(f"网络I/O占用CPU较高({network_cpu}%)，可能存在网络传输瓶颈")
        
        # 系统调用分析
        syscall_cpu = category_stats.get('System Calls', {}).get('total_cpu_percent', 0)
        if syscall_cpu > 20:
            insights.append(f"系统调用开销较大({syscall_cpu}%)，建议优化I/O操作")
        
        # WebRTC核心分析
        webrtc_cpu = category_stats.get('WebRTC Core', {}).get('total_cpu_percent', 0)
        if webrtc_cpu < 10:
            insights.append("WebRTC核心处理CPU占用较低，性能良好")
        elif webrtc_cpu > 30:
            insights.append(f"WebRTC核心处理CPU占用较高({webrtc_cpu}%)，需要优化")
        
        # 视频处理分析
        video_cpu = category_stats.get('Video Processing', {}).get('total_cpu_percent', 0)
        if video_cpu > 25:
            insights.append(f"视频处理占用CPU较高({video_cpu}%)，建议优化编解码参数")
        
        return insights
    
    def _write_text_report(self, report, output_file):
        """写入文本格式报告"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("WebRTC CPU使用情况分析报告\n")
            f.write("=" * 50 + "\n\n")
            
            # 概况
            summary = report['analysis_summary']
            f.write(f"分析概况:\n")
            f.write(f"  热点函数总数: {summary['total_hotspots']}\n")
            f.write(f"  最高CPU消耗: {summary['top_cpu_consumer']} ({summary['top_cpu_percent']:.1f}%)\n\n")
            
            # 分类详情
            f.write("分类详细分析:\n")
            f.write("-" * 30 + "\n")
            for cat_name, stats in report['category_breakdown'].items():
                f.write(f"\n{cat_name}:\n")
                f.write(f"  函数数量: {stats['function_count']}\n")
                f.write(f"  总CPU占用: {stats['total_cpu_percent']}%\n")
                f.write(f"  平均CPU占用: {stats['average_cpu_percent']}%\n")
                f.write(f"  最高CPU函数: {stats['top_function']}\n")
            
            # 性能洞察
            f.write(f"\n性能洞察:\n")
            f.write("-" * 20 + "\n")
            for insight in report['performance_insights']:
                f.write(f"• {insight}\n")

def main():
    print("🔍 WebRTC CPU使用情况分析器")
    print("")
    
    analyzer = WebRTCCPUAnalyzer()
    
    # 查找最新的CPU分析报告
    analysis_files = list(analyzer.data_dir.glob("webrtc_config_results/*analysis*.txt"))
    if not analysis_files:
        analysis_files = list(analyzer.data_dir.glob("*analysis*.txt"))
    
    if not analysis_files:
        print("❌ 未找到CPU分析报告文件")
        print("   请先运行: ./create_cpu_flamegraph.sh")
        return
    
    # 使用最新的分析文件
    latest_analysis = max(analysis_files, key=lambda f: f.stat().st_mtime)
    print(f"📊 使用分析文件: {latest_analysis}")
    
    # 解析数据
    analysis_data = analyzer.parse_cpu_analysis_report(latest_analysis)
    
    if not analysis_data['hotspots']:
        print("⚠️  未找到CPU热点数据")
        return
    
    print(f"✅ 发现 {len(analysis_data['hotspots'])} 个CPU热点")
    
    # 生成图表
    output_dir = analyzer.data_dir / "analysis_results"
    output_dir.mkdir(exist_ok=True)
    
    chart_file = analyzer.create_cpu_usage_charts(analysis_data['hotspots'], output_dir)
    
    # 生成摘要报告
    report_files = analyzer.generate_summary_report(analysis_data, output_dir)
    
    print("")
    print("🎉 CPU使用情况分析完成!")
    print(f"📊 图表文件: {chart_file}")
    print(f"📋 摘要报告: {report_files[1]}")
    
    # 显示简要结果
    print("\n" + "="*50)
    print("📈 CPU使用情况概览:")
    
    top5 = analysis_data['hotspots'][:5]
    for i, hotspot in enumerate(top5, 1):
        print(f"  {i}. {hotspot['symbol'][:40]} - {hotspot['children_percent']:.1f}%")

if __name__ == "__main__":
    main()