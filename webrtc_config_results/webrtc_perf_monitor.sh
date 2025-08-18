#!/bin/bash

# WebRTC实时性能监控和火焰图生成脚本
# 结合smart_server.sh，在WebRTC传输过程中自动生成CPU火焰图

echo "🎯 WebRTC实时性能监控启动器"
echo ""

# 参数解析
ROLE="$1"
MONITOR_DURATION=${2:-15}  # 默认监控15秒，与transmission_time_seconds一致

if [ "$ROLE" != "sender" ] && [ "$ROLE" != "receiver" ]; then
    echo "用法: $0 <sender|receiver> [monitor_duration]"
    echo ""
    echo "参数说明:"
    echo "  sender           - 监控云服务器发送端"
    echo "  receiver         - 监控云服务器接收端"
    echo "  monitor_duration - 性能监控时长(秒，默认15)"
    echo ""
    echo "示例:"
    echo "  $0 receiver 20   # 监控接收端20秒"
    echo "  $0 sender       # 监控发送端15秒"
    exit 1
fi

echo "📊 配置信息:"
echo "   - 监控角色: $ROLE"
echo "   - 监控时长: ${MONITOR_DURATION}秒"
echo ""

# 确定工作目录
cd /root/webrtc-checkout

# 启动WebRTC传输（后台运行）
echo "🚀 启动WebRTC传输进程..."
./webrtc_config_results/smart_server.sh $ROLE > webrtc_config_results/monitor_${ROLE}.log 2>&1 &
WEBRTC_PID=$!

echo "✅ WebRTC进程已启动 (PID: $WEBRTC_PID)"
echo "   日志文件: webrtc_config_results/monitor_${ROLE}.log"

# 等待WebRTC进程完全启动
echo "⏳ 等待WebRTC进程启动..."
sleep 5

# 检查进程是否还在运行
if ! kill -0 $WEBRTC_PID 2>/dev/null; then
    echo "❌ WebRTC进程启动失败"
    exit 1
fi

# 等待客户端连接（如果是服务端）
echo "⏳ 等待客户端连接..."
if [ "$ROLE" = "receiver" ]; then
    # 接收端需要等待发送端连接
    while true; do
        CONNECTIONS=$(grep "Total connected:" webrtc_config_results/server.log 2>/dev/null | tail -1 | grep -o '[0-9]\+' || echo "0")
        if [ "$CONNECTIONS" -gt 0 ]; then
            echo "✅ 检测到客户端连接"
            break
        fi
        echo -n "."
        sleep 2
        
        # 检查进程是否还在运行
        if ! kill -0 $WEBRTC_PID 2>/dev/null; then
            echo "❌ WebRTC进程意外退出"
            exit 1
        fi
    done
fi

# 再等待一段时间确保传输开始
echo "⏱️  等待传输稳定..."
sleep 3

# 查找相关的WebRTC进程
echo "🔍 查找WebRTC相关进程..."
WEBRTC_PROCESSES=$(pgrep -f "peerconnection_client|peerconnection_server" | tr '\n' ' ')
echo "   发现进程: $WEBRTC_PROCESSES"

if [ -z "$WEBRTC_PROCESSES" ]; then
    echo "⚠️  未找到WebRTC进程，将监控整个系统"
fi

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
echo "📅 时间戳: $TIMESTAMP"

echo ""
echo "🔥 开始CPU火焰图采集..."
echo "   监控进程: ${WEBRTC_PROCESSES:-"全系统"}"
echo "   持续时间: ${MONITOR_DURATION}秒"
echo ""

# 使用我们的火焰图生成脚本
cd webrtc_config_results
if [ -n "$WEBRTC_PROCESSES" ]; then
    # 创建临时脚本来传递特定PID
    cat > temp_flamegraph.sh << EOF
#!/bin/bash
FLAMEGRAPH_PATH="/root/msquic/FlameGraph"
if [ ! -d "\$FLAMEGRAPH_PATH" ]; then
    FLAMEGRAPH_PATH="/root/quiche/FlameGraph"
fi

TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
PERF_DATA="webrtc_${ROLE}_\${TIMESTAMP}.data"
STACKS_FILE="webrtc_${ROLE}_stacks_\${TIMESTAMP}.txt"
FLAMEGRAPH_SVG="webrtc_${ROLE}_flamegraph_\${TIMESTAMP}.svg"

echo "🎯 采集WebRTC $ROLE 进程性能数据..."
sudo perf record -F 99 -g -p $WEBRTC_PROCESSES -o "\$PERF_DATA" -- sleep $MONITOR_DURATION

echo "🔍 生成调用栈数据..."
sudo perf script -i "\$PERF_DATA" > "\$STACKS_FILE"

echo "🔥 生成火焰图..."
"\$FLAMEGRAPH_PATH/stackcollapse-perf.pl" "\$STACKS_FILE" | \\
"\$FLAMEGRAPH_PATH/flamegraph.pl" \\
    --title "WebRTC $ROLE CPU火焰图" \\
    --subtitle "监控时长: ${MONITOR_DURATION}秒 | \$(date)" \\
    --width 1400 \\
    --height 800 \\
    --colors hot > "\$FLAMEGRAPH_SVG"

echo "✅ 火焰图生成完成: \$FLAMEGRAPH_SVG"

# 生成性能报告
REPORT_FILE="webrtc_${ROLE}_analysis_\${TIMESTAMP}.txt"
cat > "\$REPORT_FILE" << EOL
WebRTC $ROLE CPU性能分析报告
==============================

采集时间: \$(date)
监控时长: ${MONITOR_DURATION}秒
目标进程: $WEBRTC_PROCESSES
采样频率: 99Hz

火焰图文件: \$FLAMEGRAPH_SVG

Top 热点函数:
EOL
sudo perf report -i "\$PERF_DATA" --stdio --sort comm,dso,symbol | head -30 >> "\$REPORT_FILE"

echo "📊 性能报告: \$REPORT_FILE"
rm -f temp_flamegraph.sh
EOF

    chmod +x temp_flamegraph.sh
    ./temp_flamegraph.sh
else
    # 使用原始脚本监控整个系统
    ./create_cpu_flamegraph.sh $MONITOR_DURATION
fi

# 等待WebRTC传输完成
echo ""
echo "⏳ 等待WebRTC传输完成..."
wait $WEBRTC_PID

echo ""
echo "🎉 监控完成!"
echo ""
echo "📁 生成的文件在 webrtc_config_results/ 目录中:"
ls -la webrtc_*flamegraph*.svg 2>/dev/null | head -5
echo ""
echo "💡 在浏览器中打开SVG文件查看火焰图"

# 清理函数
cleanup() {
    echo "🧹 清理进程..."
    kill $WEBRTC_PID 2>/dev/null || true
    pkill -f "peerconnection_client|peerconnection_server" 2>/dev/null || true
    pkill -f "Xvfb" 2>/dev/null || true
}

trap cleanup SIGINT SIGTERM