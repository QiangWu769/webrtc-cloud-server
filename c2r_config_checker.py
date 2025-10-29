#!/usr/bin/env python3
"""
C2R配置检查工具
验证ACT扩展配置和基础设施是否正确
"""

import re
import sys
import os
from pathlib import Path

def check_act_extension_config():
    """检查ACT扩展配置"""
    print("🔧 Step 2: ACT扩展配置检查")
    print("-" * 40)
    
    config_files = [
        "src/api/rtp_headers.h",
        "src/modules/rtp_rtcp/include/rtp_rtcp_defines.h", 
        "src/modules/rtp_rtcp/source/absolute_capture_time_extension.h"
    ]
    
    act_found = False
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    content = f.read()
                    if 'AbsoluteCaptureTime' in content or 'absolute_capture_time' in content:
                        print(f"  ✅ {config_file} - ACT支持")
                        act_found = True
                    else:
                        print(f"  ❌ {config_file} - 未找到ACT相关代码")
            except Exception as e:
                print(f"  ⚠️  {config_file} - 读取失败: {e}")
        else:
            print(f"  ❓ {config_file} - 文件不存在")
    
    if act_found:
        print("  🎯 ACT扩展基础设施: 可用")
    else:
        print("  ❌ ACT扩展基础设施: 需要检查")
    
    return act_found

def check_c2r_receiver_integration():
    """检查C2RReceiver集成"""
    print("\n🎯 Step 1: C2RReceiver框架检查")
    print("-" * 40)
    
    framework_files = [
        "src/c2r_receiver.h",
        "src/c2r_receiver.cc"
    ]
    
    integration_files = [
        "src/video/rtp_video_stream_receiver2.cc",
        "src/video/video_stream_decoder2.cc"
    ]
    
    framework_ok = True
    for file_path in framework_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path} - 框架文件存在")
        else:
            print(f"  ❌ {file_path} - 框架文件缺失")
            framework_ok = False
    
    integration_ok = True
    for file_path in integration_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if 'C2R_ON_' in content or 'c2r_receiver.h' in content:
                        print(f"  ✅ {file_path} - 已集成C2R框架")
                    else:
                        print(f"  ❌ {file_path} - 未集成C2R框架")
                        integration_ok = False
            except Exception as e:
                print(f"  ⚠️  {file_path} - 检查失败: {e}")
        else:
            print(f"  ❌ {file_path} - 文件不存在")
            integration_ok = False
    
    if framework_ok and integration_ok:
        print("  🎯 C2RReceiver框架: 完整集成")
        return True
    else:
        print("  ❌ C2RReceiver框架: 需要修复")
        return False

def check_logging_format():
    """检查日志格式统一"""
    print("\n📝 Step 3: 统一日志格式检查")
    print("-" * 40)
    
    log_patterns = [
        r'\[C2R-ACT-RX\]',
        r'\[C2R-E2E-\w+\]',
        r'\[C2R-PROCESSING\]',
        r'\[C2R-E2E-COMPLETE\]'
    ]
    
    source_files = [
        "src/c2r_receiver.cc",
        "src/video/rtp_video_stream_receiver2.cc",
        "src/video/video_stream_decoder2.cc"
    ]
    
    pattern_found = {pattern: False for pattern in log_patterns}
    
    for source_file in source_files:
        if os.path.exists(source_file):
            try:
                with open(source_file, 'r') as f:
                    content = f.read()
                    
                    for pattern in log_patterns:
                        if re.search(pattern, content):
                            pattern_found[pattern] = True
                            
            except Exception as e:
                print(f"  ⚠️  {source_file} - 检查失败: {e}")
    
    all_patterns_found = True
    for pattern, found in pattern_found.items():
        status = "✅" if found else "❌"
        print(f"  {status} {pattern} - {'已实现' if found else '缺失'}")
        if not found:
            all_patterns_found = False
    
    if all_patterns_found:
        print("  🎯 统一日志格式: 完整实现")
    else:
        print("  ❌ 统一日志格式: 部分缺失")
    
    return all_patterns_found

def check_analysis_tools():
    """检查分析工具"""
    print("\n📊 分析工具检查")
    print("-" * 40)
    
    analysis_tools = [
        "c2r_unified_analyzer.py",
        "c2r_correct_calibration.py",  # 备用工具
        "c2r_config_checker.py"       # 本工具
    ]
    
    tools_ok = True
    for tool in analysis_tools:
        if os.path.exists(tool):
            print(f"  ✅ {tool} - 分析工具可用")
        else:
            print(f"  ❌ {tool} - 分析工具缺失")
            tools_ok = False
    
    return tools_ok

def generate_configuration_guide():
    """生成配置指南"""
    print("\n📋 ACT扩展配置指南")
    print("-" * 40)
    
    print("确保接收端支持ACT扩展的配置代码：")
    print()
    print("```cpp")
    print("// 在VideoReceiveConfig中添加ACT扩展")
    print("video_config.rtp.extensions.push_back(")
    print("    RtpExtension(RtpExtension::kAbsoluteCaptureTimeUri, 13));")
    print()
    print("// 或者使用常量")
    print("video_config.rtp.extensions.push_back(")
    print("    RtpExtension(\"http://www.webrtc.org/experiments/rtp-hdrext/abs-capture-time\", 13));")
    print("```")
    print()
    
    print("验证ACT扩展生效的方法：")
    print("1. 检查日志中是否出现 [C2R-ACT-RX] 事件")
    print("2. 确认 ActCaptureUs 字段有合理的时间戳值")
    print("3. 使用 c2r_unified_analyzer.py 分析覆盖率")

def main():
    print("🎯 C2R配置检查工具")
    print("基于推荐实施步骤的完整性验证")
    print("=" * 50)
    
    # 检查各个步骤
    step1_ok = check_c2r_receiver_integration()
    step2_ok = check_act_extension_config()
    step3_ok = check_logging_format()
    tools_ok = check_analysis_tools()
    
    # 总结
    print("\n🏁 检查结果总结")
    print("=" * 50)
    
    steps = [
        ("Step 1: C2RReceiver框架", step1_ok),
        ("Step 2: ACT扩展配置", step2_ok),
        ("Step 3: 统一日志格式", step3_ok),
        ("分析工具", tools_ok)
    ]
    
    all_ok = True
    for step_name, step_ok in steps:
        status = "✅ 完成" if step_ok else "❌ 待修复"
        print(f"  {step_name}: {status}")
        if not step_ok:
            all_ok = False
    
    if all_ok:
        print("\n🎉 配置检查通过！")
        print("可以开始测试C2R延迟测量功能。")
        print("\n下一步：")
        print("1. 编译并运行接收端")
        print("2. 使用 c2r_unified_analyzer.py 分析日志")
        print("3. 检查ACT扩展覆盖率和延迟数据")
    else:
        print("\n⚠️  配置存在问题，需要修复后再测试。")
        
        # 如果ACT扩展有问题，显示配置指南
        if not step2_ok:
            generate_configuration_guide()

if __name__ == "__main__":
    main()