# WebRTC QoE 指标计算工具

本目录包含用于分析 WebRTC 传输质量的指标计算脚本。

## 计算脚本

### 1. calculate_switching_rate.py
计算分辨率切换率 (Switching Rate)

**用法:**
```bash
python3 calculate_switching_rate.py receiver_cloud.log
```

**输出指标:**
- Switching Rate: 相邻 segment 之间分辨率切换的比例
- 切换次数
- 各分辨率档位占比

**评级标准:**
- 优秀: < 10%
- 良好: 10-20%
- 一般: 20-30%
- 较差: > 30%

---

### 2. calculate_rebuffering_ratio.py
计算重缓冲率 (Rebuffering Ratio)

**用法:**
```bash
python3 calculate_rebuffering_ratio.py receiver_cloud.log
```

**输出指标:**
- Rebuffering Ratio: 冻结时间占总播放时长的比例
- 冻结次数和总时长
- 暂停次数和总时长

**评级标准:**
- A+: 0% (无卡顿)
- A: < 1%
- B: 1-5%
- C: 5-10%
- D: > 10%

---

### 3. calculate_decode_latency.py
计算不同分辨率下的解码延迟

**用法:**
```bash
python3 calculate_decode_latency.py receiver_cloud.log
```

**输出指标:**
- 各分辨率的平均解码延迟 (ms/帧)
- 最大解码延迟
- 解码帧数统计

---

### 4. calculate_qoe_metrics.py (综合工具)
一次性计算所有 QoE 指标

**用法:**
```bash
# 输出格式化报告
python3 calculate_qoe_metrics.py receiver_cloud.log

# 输出 JSON 格式
python3 calculate_qoe_metrics.py receiver_cloud.log --json
```

**输出指标:**
1. Switching Rate (分辨率切换率)
2. Rebuffering Ratio (重缓冲率)
3. Decode Latency (解码延迟)
4. Frame Drop Rate (丢帧率)
5. 综合评级

---

## 数据来源

所有脚本从 WebRTC 接收端日志 (`receiver_cloud.log`) 中提取数据：

- **VideoReceiveStreamInterface stats**: 帧解码、渲染帧率、延迟等
- **VideoQuality-CoreFreeze**: 冻结次数、时长、Rebuffering Ratio
- **VideoQuality-FreezeRate**: 冻结和暂停的详细统计

---

## 示例输出

### Switching Rate
```
================================================================================
Switching Rate 计算
================================================================================

实际传输时长: 118.6 秒
总 Segment 数 (N): 59
切换次数 (N_switch): 4
Switching Rate: 0.0690 (6.90%)

各分辨率档位占比:
----------------------------------------
  360p: 8 segments (13.6%)
  540p: 2 segments (3.4%)
  720p: 13 segments (22.0%)
  1080p: 36 segments (61.0%)

✓ 评级: 优秀 (< 10%)
```

### Rebuffering Ratio
```
================================================================================
Rebuffering Ratio 计算
================================================================================

核心指标:
----------------------------------------
T_total (总播放时长):  118.68 秒
T_rebuf (冻结时间):    1.63 秒
ρ_rebuf (重缓冲率):    0.0137 (1.37%)

详细统计:
----------------------------------------
冻结次数:    6
暂停次数:    0
暂停时长:    0.00 秒

平均每次冻结: 271 ms

✓ 评级: B (良好) - 卡顿较少 (1-5%)
```

### 解码延迟
```
================================================================================
不同分辨率解码延迟统计
================================================================================

分辨率          实际平均             decode_ms       max_decode  帧数
            (ms/帧)          平均(ms)        (ms)
--------------------------------------------------------------------------------
640x360      1.74             1.6             3           438
960x540      2.00             2.8             3           570
1280x720     13.22            8.5             28          3559
1920x1080    13.79            17.4            28          2991

关键发现:
----------------------------------------
低分辨率 (≤540p) 平均延迟: 1.87 ms/帧
高分辨率 (≥720p) 平均延迟: 13.51 ms/帧
延迟增长倍数: 7.23x

主要传输分辨率: 1280x720 (3559 帧)
主要分辨率解码延迟: 13.22 ms/帧
```

---

## QoE 指标定义

### Switching Rate
```
Switching Rate = N_switch / (N - 1)

其中:
- N_switch: 相邻 segment 之间分辨率档位变化的次数
- N: 总 segment 数 (每个 segment 为 2 秒)
```

### Rebuffering Ratio
```
ρ_rebuf = T_rebuf / T_total

其中:
- T_rebuf: 视频冻结的总时长 (秒)
- T_total: 视频总播放时长 (秒)
```

### Decode Latency
```
实际平均解码延迟 = totalDecodeTime / framesDecoded × 1000 (ms/帧)
```

---

## 实验结果文件

- `vp8_experiment_1_results.txt` - VP8 实验 1 完整结果
- `vp8_experiment_2_results.txt` - VP8 实验 2 完整结果
- `quality_metrics_comparison.csv` - 质量指标对比表
- `decode_latency_by_resolution.txt` - 解码延迟详细分析
- `decode_latency_summary.csv` - 解码延迟摘要

---

## 依赖

- Python 3.6+
- 标准库 (re, sys, collections, json)

无需额外安装依赖包。

---

## 参考标准

这些指标的计算方法参考了以下标准:

1. **SODA** (Streaming Over Dynamic Adaptive): Switching Rate 定义
2. **ITU-T P.1203**: 视频质量评估标准
3. **WebRTC Stats**: W3C WebRTC Statistics API
4. **DASH Industry Forum**: 自适应流媒体 QoE 评估
