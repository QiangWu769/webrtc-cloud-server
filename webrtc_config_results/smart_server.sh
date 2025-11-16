#!/bin/bash

# 参数解析
ROLE="$1"
REMOTE_IP="$2"

if [ "$ROLE" != "sender" ] && [ "$ROLE" != "receiver" ]; then
    echo "🎯 智能WebRTC启动脚本"
    echo ""
    echo "用法: $0 <sender|receiver>"
    echo ""
    echo "参数说明:"
    echo "  sender     - 云服务器作为发送端运行（启动信令服务器+发送端客户端）"
    echo "  receiver   - 云服务器作为接收端运行（启动信令服务器+接收端客户端）"
    echo ""
    echo "网络架构:"
    echo "  - 云服务器（有公网IP）: 总是运行信令服务器"
    echo "  - 本地电脑（私网）: 连接到云服务器的信令服务器"
    echo ""
    echo "示例:"
    echo "  $0 sender      # 云服务器作为发送端，等待本地接收端连接"
    echo "  $0 receiver    # 云服务器作为接收端，等待本地发送端连接"
    exit 1
fi

echo "🎯 智能WebRTC启动脚本 - 运行模式: $ROLE"

# 清理现有进程
echo "🧹 清理现有进程..."
pkill -f "Xvfb" 2>/dev/null || true
pkill -f "peerconnection_server" 2>/dev/null || true
pkill -f "peerconnection_client" 2>/dev/null || true
rm -f /tmp/.X99-lock 2>/dev/null || true
sleep 2

# 确定工作目录
cd /mnt/data/webrtc-cloud-server
echo "📂 工作目录: $(pwd)"

# 本地IP（用于发送端模式）
PUBLIC_IP="35.229.115.62"
echo "🌐 本地IP: $PUBLIC_IP"

# 启动基础服务
echo "1️⃣ 启动Xvfb虚拟显示..."
Xvfb :99 -screen 0 1024x768x24 >/dev/null 2>&1 &
XVFB_PID=$!
sleep 2
export DISPLAY=:99

# 云服务器总是启动信令服务器（因为它有公网IP）
echo "2️⃣ 启动信令服务器..."
stdbuf -oL ./src/out/Default/peerconnection_server --port=8888 > webrtc_config_results/server.log 2>&1 &
SERVER_PID=$!
sleep 2

echo "✅ 信令服务器已启动:"
echo "   - Xvfb (PID: $XVFB_PID)"
echo "   - Server (PID: $SERVER_PID)"
echo ""
echo "🌐 信令服务器地址: $PUBLIC_IP:8888"
echo "📋 在本地运行: ./test_local_receiver.sh $([[ $ROLE == "sender" ]] && echo "receiver" || echo "sender") $PUBLIC_IP"
echo ""

if [ "$ROLE" = "sender" ]; then
    # 云服务器作为发送端
    echo "⏳ 等待本地接收端连接..."
    
    CLIENT_STARTED=false
    while true; do
        if [ -f "webrtc_config_results/server.log" ]; then
            CONNECTIONS=$(grep "Total connected:" webrtc_config_results/server.log | tail -1 | grep -o '[0-9]\+' 2>/dev/null || echo "0")
            
            if [ "$CONNECTIONS" -gt 0 ] && [ "$CLIENT_STARTED" = "false" ]; then
                echo ""
                echo "🎉 检测到 $CONNECTIONS 个客户端连接！"
                echo "📋 连接详情:"
                grep "New member added" webrtc_config_results/server.log | tail -1
                
                echo "⏱️  等待3秒后启动发送端..."
                sleep 3
                
                echo "🚀 启动发送端客户端..."
                DISPLAY=:99 ./src/out/Default/peerconnection_client \
                    --config=webrtc_config_results/sender_config.json \
                    --force_fieldtrials=WebRTC-DefaultBitrateLimitsKillSwitch/Enabled/ \
                    > webrtc_config_results/sender_cloud.log 2>&1 &
                CLIENT_PID=$!
                CLIENT_STARTED=true
                
                echo "📤 云服务器发送端已启动 (PID: $CLIENT_PID)"
                echo "   - 🔥 码率限制已解除 (Field Trial: DefaultBitrateLimitsKillSwitch)"
                echo "📝 日志文件: webrtc_config_results/sender_cloud.log"
                echo "📊 监控传输状态..."
                
                wait $CLIENT_PID
                echo "✅ 视频传输完成！"
                break
            fi
        fi
        
        echo -n "."
        sleep 2
    done
    
elif [ "$ROLE" = "receiver" ]; then
    # 云服务器作为接收端
    echo "3️⃣ 创建接收端配置文件..."
    cat > webrtc_config_results/receiver_config_cloud.json << EOF
{
  "video_source": {
    "camera": {"enabled": false},
    "video_file": {"enabled": false},
    "video_disabled": {"enabled": true}
  },
  "video_output": {
    "enabled": true,
    "file_path": "$(pwd)/webrtc_config_results/received_cloud.y4m",
    "width": 1920, "height": 1080, "fps": 30
  },
  "logging": {
    "level": "info", "save_to_file": true,
    "log_output_path": "$(pwd)/webrtc_config_results/receiver_cloud.log"
  },
  "server": {
    "host": "localhost",
    "port": 8888,
    "auto_connect": true,
    "auto_call": false
  },
  "auto_close_on_completion": true,
  "transmission_time_seconds": 15
}
EOF
    
    echo "⏳ 等待本地发送端连接..."
    
    # 等待至少有一个连接再启动接收端
    while true; do
        if [ -f "webrtc_config_results/server.log" ]; then
            CONNECTIONS=$(grep "Total connected:" webrtc_config_results/server.log | tail -1 | grep -o '[0-9]\+' 2>/dev/null || echo "0")
            if [ "$CONNECTIONS" -gt 0 ]; then
                break
            fi
        fi
        echo -n "."
        sleep 2
    done
    
    echo ""
    echo "🎉 检测到本地发送端连接！"
    echo "🚀 启动接收端客户端..."
    
    ./src/out/Default/peerconnection_client \
        --config=webrtc_config_results/receiver_config_cloud.json \
        --force_fieldtrials=WebRTC-DefaultBitrateLimitsKillSwitch/Enabled/ \
        > webrtc_config_results/receiver_cloud.log 2>&1 &
    CLIENT_PID=$!
    
    echo "📥 云服务器接收端已启动 (PID: $CLIENT_PID)"
    echo "   - 🔥 码率限制已解除 (Field Trial: DefaultBitrateLimitsKillSwitch)"
    echo "📝 日志文件: webrtc_config_results/receiver_cloud.log"
    echo "📁 接收视频将保存到: webrtc_config_results/received_cloud.y4m"
    echo "📊 监控接收状态..."
    
    wait $CLIENT_PID
    echo "✅ 视频接收完成！"
    
    echo "📊 检查接收到的视频文件..."
    ls -lh webrtc_config_results/received_cloud.y4m 2>/dev/null || echo "未生成视频文件"
fi

echo ""
echo "🎉 任务完成！"

# 清理函数
cleanup() {
    echo "🧹 清理进程..."
    kill $XVFB_PID $SERVER_PID $CLIENT_PID 2>/dev/null || true
    pkill -f "peerconnection_client" 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM