#!/bin/bash
# 将YUV转换为压缩的MP4，然后重复到90秒

INPUT_FILE="/root/webrtc-checkout/VCD_th_1920x1080_30.yuv"
TEMP_MP4="/root/webrtc-checkout/temp_video.mp4"
OUTPUT_MP4="/root/webrtc-checkout/VCD_th_1920x1080_30_90s.mp4"
OUTPUT_YUV="/root/webrtc-checkout/VCD_th_1920x1080_30_90s_compressed.yuv"

echo "=== 压缩并扩展到90秒 ==="

# 步骤1: YUV转MP4 (高质量压缩)
echo "步骤1: YUV转MP4 (压缩)..."
ffmpeg -f rawvideo -pix_fmt yuv420p -s 1920x1080 -r 30 -i "$INPUT_FILE" \
       -c:v libx264 -preset medium -crf 18 -y "$TEMP_MP4"

# 步骤2: 重复MP4到90秒 (假设原始是10秒，需要重复9次总共，所以stream_loop=8)
echo "步骤2: 重复到90秒..."
ffmpeg -stream_loop 8 -i "$TEMP_MP4" -c copy -y "$OUTPUT_MP4"

# 步骤3: MP4转回YUV (如果需要)
echo "步骤3: 转回YUV格式..."
ffmpeg -i "$OUTPUT_MP4" -f rawvideo -pix_fmt yuv420p -y "$OUTPUT_YUV"

echo ""
echo "=== 完成! ===" 
echo "原始YUV:     $(ls -lh "$INPUT_FILE" | awk '{print $5}') (10秒)"
echo "压缩MP4:     $(ls -lh "$OUTPUT_MP4" | awk '{print $5}') (90秒)"
echo "压缩后YUV:   $(ls -lh "$OUTPUT_YUV" | awk '{print $5}') (90秒)"

# 计算压缩比
python3 -c "
import os
original_size = os.path.getsize('$INPUT_FILE')
compressed_yuv_size = os.path.getsize('$OUTPUT_YUV')
compression_ratio = original_size / compressed_yuv_size * 9  # 9倍时长
print(f'压缩比: {compression_ratio:.1f}:1')
print(f'体积减少: {(1-compressed_yuv_size/(original_size*9))*100:.1f}%')
"

# 清理临时文件
rm "$TEMP_MP4"