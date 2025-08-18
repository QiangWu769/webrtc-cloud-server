#!/bin/bash

echo "🎯 云服务器端智能启动脚本 v2.0"
echo "📁 使用专用目录: webrtc_config_results"

# 清理现有进程
echo "🧹 清理现有进程..."
pkill -f "Xvfb" 2>/dev/null || true
pkill -f "peerconnection_server" 2>/dev/null || true
pkill -f "peerconnection_client" 2>/dev/null || true
rm -f /tmp/.X99-lock 2>/dev/null || true
sleep 1

# 检查当前目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

echo "📂 工作目录: $(pwd)"

# 云服务器固定公网IP
PUBLIC_IP="110.42.33.160"
echo "🌐 云服务器公网IP: $PUBLIC_IP"

# 1. 启动虚拟显示
echo "1️⃣ 启动虚拟显示Xvfb..."
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 2. 启动signaling服务器
echo "2️⃣ 启动信令服务器（监听端口8888）..."
./src/out/Default/peerconnection_server --port=8888 > webrtc_config_results/server.log 2>&1 &
SERVER_PID=$!
sleep 3

# 设置环境变量
export DISPLAY=:99

echo "✅ 基础服务启动完成！"
echo ""
echo "🚀 云服务器基础服务已启动："
echo "   - Xvfb虚拟显示 (PID: $XVFB_PID)"
echo "   - 信令服务器 (PID: $SERVER_PID) - 监听端口8888"  
echo ""
echo "🔧 确保云服务器防火墙已开放8888端口"
echo "🌐 客户端连接地址: $PUBLIC_IP:8888"
echo ""

# 函数：启动发送端
start_sender() {
    echo "🚀 启动发送端..."
    
    # 清理旧的发送端进程
    pkill -f "peerconnection_client.*sender_config" 2>/dev/null || true
    sleep 1
    
    # 启动发送端
    ./src/out/Default/peerconnection_client \
        --config=$(pwd)/webrtc_config_results/sender_config.json > webrtc_config_results/sender.log 2>&1 &
    SENDER_PID=$!
    
    echo "📤 发送端已启动 (PID: $SENDER_PID)"
    echo "📝 发送端日志: webrtc_config_results/sender.log"
    
    return $SENDER_PID
}

# 函数：检查连接的客户端数量
check_client_count() {
    # 从日志中获取最新的连接数
    local count=$(grep "Total connected:" webrtc_config_results/server.log | tail -1 | grep -o '[0-9]\+' || echo "0")
    echo $count
}

# 智能检测和启动逻辑
echo "⏳ 开始智能监控客户端连接..."
echo "📋 请在本地电脑运行: ./test_local_receiver.sh"

SENDER_STARTED=false
CHECK_INTERVAL=2  # 每2秒检查一次

while true; do
    # 检查当前连接的客户端数量
    CURRENT_CLIENTS=$(check_client_count)
    
    # 如果有客户端连接且发送端未启动
    if [ "$CURRENT_CLIENTS" -gt 0 ] && [ "$SENDER_STARTED" = false ]; then
        echo ""
        echo "🎉 检测到 $CURRENT_CLIENTS 个客户端连接！"
        echo "📋 最新连接信息："
        grep "New member added" webrtc_config_results/server.log | tail -2
        
        echo ""
        echo "⏱️  等待2秒确保接收端就绪..."
        sleep 2
        
        # 启动发送端
        start_sender
        SENDER_PID=$?
        SENDER_STARTED=true
        
        echo ""
        echo "✅ 发送端启动完成！开始视频传输..."
        echo "📊 监控传输进度..."
        
        # 等待发送端完成
        wait $SENDER_PID
        echo "✅ 视频传输完成！"
        break
        
    elif [ "$CURRENT_CLIENTS" -eq 0 ]; then
        echo -n "."  # 显示等待状态
    fi
    
    sleep $CHECK_INTERVAL
done

echo ""
echo "🎉 所有任务完成！"
echo ""
echo "📊 最终状态："
echo "   - 连接的客户端数: $(check_client_count)"
echo "   - 发送端状态: 已完成"

# 清理函数
cleanup() {
    echo ""
    echo "🧹 正在停止所有服务..."
    kill $XVFB_PID $SERVER_PID 2>/dev/null || true
    pkill -f "peerconnection_client" 2>/dev/null || true
    echo "✅ 服务已停止"
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

echo "⚠️  按 Ctrl+C 停止所有服务"