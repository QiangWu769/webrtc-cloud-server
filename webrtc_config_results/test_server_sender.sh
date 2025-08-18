#!/bin/bash

echo "🎯 第一步：启动云服务器端基础服务（Xvfb + 信令服务器）..."
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
echo "📁 配置目录: webrtc_config_results"

# 云服务器固定公网IP
PUBLIC_IP="110.42.33.160"
echo "🌐 云服务器公网IP: $PUBLIC_IP"

# 1. 启动虚拟显示
echo "1️⃣ 启动虚拟显示Xvfb..."
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# 2. 启动signaling服务器（监听所有接口）
echo "2️⃣ 启动signaling服务器（监听端口8888）..."
./src/out/Default/peerconnection_server --port=8888 > webrtc_config_results/server.log 2>&1 &
SERVER_PID=$!
sleep 3

# 设置环境变量
export DISPLAY=:99

# 3. 智能等待客户端连接并自动启动发送端
echo "✅ 基础服务启动完成！"
echo ""
echo "🚀 云服务器基础服务已启动："
echo "   - Xvfb虚拟显示 (PID: $XVFB_PID)"
echo "   - 信令服务器 (PID: $SERVER_PID) - 监听端口8888"  
echo ""
echo "🔧 确保云服务器防火墙已开放8888端口"
echo "🌐 客户端连接地址: $PUBLIC_IP:8888"
echo ""
echo "⏳ 正在等待接收端连接..."
echo "📋 请在本地电脑运行: ./test_local_receiver.sh"
echo "📝 监控信令服务器日志: webrtc_config_results/server.log"

# 函数：启动发送端
start_sender() {
    echo ""
    echo "🚀 检测到客户端连接，自动启动发送端..."
    
    # 清理旧的发送端进程
    pkill -f "peerconnection_client.*sender_config" 2>/dev/null || true
    sleep 1
    
    # 启动发送端
    ./src/out/Default/peerconnection_client \
        --config=$(pwd)/webrtc_config_results/sender_config.json > webrtc_config_results/sender.log 2>&1 &
    SENDER_PID=$!
    
    echo "📤 发送端已启动 (PID: $SENDER_PID)"
    echo "📝 发送端日志: webrtc_config_results/sender.log"
    
    # 监控发送端日志
    echo "📊 监控发送端运行状态..."
    timeout 20s tail -f webrtc_config_results/sender.log || true
    
    echo ""
    echo "✅ 发送端运行中..."
    echo "⚠️  若要停止所有服务，请运行: kill $XVFB_PID $SERVER_PID $SENDER_PID"
    
    # 等待发送端完成
    wait $SENDER_PID
    echo "✅ 视频传输完成！"
}

# 监控信令服务器日志，检测客户端连接
echo "🔍 开始监控客户端连接..."

# 确保日志文件存在
touch webrtc_config_results/server.log

# 使用标志文件来控制启动状态
SENDER_STARTED_FLAG="/tmp/sender_started_$$"
rm -f "$SENDER_STARTED_FLAG"

# 在后台监控日志并启动发送端
(
    tail -f webrtc_config_results/server.log | while read line; do
        echo "📋 Server: $line"
        
        # 检测到新成员加入且发送端未启动
        if echo "$line" | grep -q "New member added" && [ ! -f "$SENDER_STARTED_FLAG" ]; then
            echo ""
            echo "🎉 检测到客户端成功连接！"
            
            # 创建标志文件，防止重复启动
            touch "$SENDER_STARTED_FLAG"
            
            # 等待一秒确保接收端完全就绪
            sleep 2
            
            # 启动发送端
            start_sender
            
            break
        fi
    done
) &

MONITOR_PID=$!

# 保持脚本运行，等待所有进程
echo ""
echo "🔄 服务正在运行中..."
echo "⚠️  按 Ctrl+C 停止所有服务"

# 清理函数
cleanup() {
    echo ""
    echo "🧹 正在停止所有服务..."
    kill $XVFB_PID $SERVER_PID $MONITOR_PID 2>/dev/null || true
    pkill -f "peerconnection_client" 2>/dev/null || true
    rm -f "$SENDER_STARTED_FLAG"
    echo "✅ 服务已停止"
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

# 等待进程
wait