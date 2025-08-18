#!/bin/bash

# WebRTC传输过程CPU火焰图生成脚本
# 使用perf工具采集真实的CPU调用栈数据，生成标准火焰图

echo "🔥 WebRTC传输过程CPU火焰图生成器"
echo ""

# 参数解析
DURATION=${1:-30}  # 默认采集30秒
OUTPUT_DIR="webrtc_config_results"
FLAMEGRAPH_PATH="/root/msquic/FlameGraph"

if [ ! -d "$FLAMEGRAPH_PATH" ]; then
    FLAMEGRAPH_PATH="/root/quiche/FlameGraph"
fi

if [ ! -d "$FLAMEGRAPH_PATH" ]; then
    echo "❌ 未找到FlameGraph工具，请先安装"
    echo "   git clone https://github.com/brendangregg/FlameGraph.git"
    exit 1
fi

echo "📊 配置信息:"
echo "   - 采集时长: ${DURATION}秒"
echo "   - 输出目录: $OUTPUT_DIR"
echo "   - FlameGraph路径: $FLAMEGRAPH_PATH"
echo ""

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

# 检查是否有WebRTC进程正在运行
echo "🔍 检查WebRTC进程..."
WEBRTC_PIDS=$(pgrep -f "peerconnection_client|peerconnection_server" || echo "")

if [ -z "$WEBRTC_PIDS" ]; then
    echo "⚠️  未检测到运行中的WebRTC进程"
    echo "   请先启动WebRTC传输，然后运行此脚本"
    echo ""
    echo "💡 使用方法:"
    echo "   1. 启动WebRTC传输: ./smart_server.sh receiver"
    echo "   2. 在另一个终端运行: ./create_cpu_flamegraph.sh 30"
    echo ""
    read -p "是否继续监控整个系统的CPU使用情况？(y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    TARGET_OPTION=""
else
    echo "✅ 发现WebRTC进程: $WEBRTC_PIDS"
    # 构建perf目标选项
    TARGET_OPTION="-p $(echo $WEBRTC_PIDS | tr ' ' ',')"
fi

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PERF_DATA="webrtc_perf_${TIMESTAMP}.data"
STACKS_FILE="webrtc_stacks_${TIMESTAMP}.txt"
FLAMEGRAPH_SVG="webrtc_cpu_flamegraph_${TIMESTAMP}.svg"

echo ""
echo "🎯 开始CPU性能采集..."
echo "   目标进程: ${WEBRTC_PIDS:-"全系统"}"
echo "   数据文件: $PERF_DATA"
echo "   持续时间: ${DURATION}秒"
echo ""

# 使用perf采集CPU调用栈数据
echo "⏱️  正在采集性能数据 (${DURATION}秒)..."
if [ -n "$TARGET_OPTION" ]; then
    # 针对特定进程
    sudo perf record -F 99 -g $TARGET_OPTION -o "$PERF_DATA" -- sleep "$DURATION"
else

    # 全系统采集
    sudo perf record -F 99 -g -o "$PERF_DATA" -- sleep "$DURATION"
fi

if [ $? -ne 0 ]; then
    echo "❌ perf数据采集失败"
    exit 1
fi

echo "✅ 性能数据采集完成"
echo ""

# 检查perf数据文件
if [ ! -f "$PERF_DATA" ]; then
    echo "❌ 性能数据文件不存在: $PERF_DATA"
    exit 1
fi

PERF_SIZE=$(du -h "$PERF_DATA" | cut -f1)
echo "📁 性能数据文件大小: $PERF_SIZE"

# 生成调用栈数据
echo "🔍 生成调用栈数据..."
sudo perf script -i "$PERF_DATA" > "$STACKS_FILE"

if [ $? -ne 0 ] || [ ! -s "$STACKS_FILE" ]; then
    echo "❌ 调用栈数据生成失败"
    exit 1
fi

STACK_LINES=$(wc -l < "$STACKS_FILE")
echo "📋 调用栈数据行数: $STACK_LINES"

# 使用FlameGraph工具生成火焰图
echo "🔥 生成火焰图..."

# 折叠调用栈
COLLAPSED_FILE="webrtc_collapsed_${TIMESTAMP}.txt"
"$FLAMEGRAPH_PATH/stackcollapse-perf.pl" "$STACKS_FILE" > "$COLLAPSED_FILE"

if [ $? -ne 0 ] || [ ! -s "$COLLAPSED_FILE" ]; then
    echo "❌ 调用栈折叠失败"
    exit 1
fi

# 生成火焰图SVG
"$FLAMEGRAPH_PATH/flamegraph.pl" \
    --title "WebRTC传输过程CPU火焰图" \
    --subtitle "采集时间: ${DURATION}秒 | $(date)" \
    --width 1400 \
    --height 800 \
    --colors hot \
    "$COLLAPSED_FILE" > "$FLAMEGRAPH_SVG"

if [ $? -ne 0 ] || [ ! -s "$FLAMEGRAPH_SVG" ]; then
    echo "❌ 火焰图生成失败"
    exit 1
fi

# 生成详细的性能分析报告
echo "📊 生成性能分析报告..."
REPORT_FILE="webrtc_cpu_analysis_${TIMESTAMP}.txt"

cat > "$REPORT_FILE" << EOF
WebRTC传输过程CPU性能分析报告
========================================

采集信息:
- 采集时间: $(date)
- 采集时长: ${DURATION}秒
- 目标进程: ${WEBRTC_PIDS:-"全系统"}
- 采样频率: 99Hz

文件信息:
- 原始数据: $PERF_DATA ($PERF_SIZE)
- 调用栈数据: $STACKS_FILE ($STACK_LINES 行)
- 火焰图: $FLAMEGRAPH_SVG

Top CPU消耗函数:
EOF

# 添加CPU热点分析
echo "正在分析CPU热点..." >> "$REPORT_FILE"
sudo perf report -i "$PERF_DATA" --stdio --sort comm,dso,symbol | head -50 >> "$REPORT_FILE"

echo ""
echo "🎉 火焰图生成完成!"
echo ""
echo "📁 生成的文件:"
echo "   🔥 火焰图: $FLAMEGRAPH_SVG"
echo "   📊 性能报告: $REPORT_FILE"
echo "   📋 原始数据: $PERF_DATA"
echo "   📄 调用栈: $STACKS_FILE"
echo ""
echo "💡 查看方法:"
echo "   - 在浏览器中打开: $FLAMEGRAPH_SVG"
echo "   - 或者使用: firefox $FLAMEGRAPH_SVG"
echo ""

# 清理选项
echo "🧹 清理临时文件..."
read -p "是否删除中间文件以节省空间？(保留火焰图和报告) (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$STACKS_FILE" "$COLLAPSED_FILE"
    echo "✅ 已清理中间文件"
fi

echo ""
echo "✨ CPU火焰图分析完成!"