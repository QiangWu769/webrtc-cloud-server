/*
 * C2R日志开关测试工具
 * 
 * 编译: g++ -std=c++17 test_c2r_switch.cc -o test_c2r_switch
 * 
 * 使用:
 * ./test_c2r_switch                 # 默认关闭
 * C2R_LOG=1 ./test_c2r_switch       # 启用日志
 */

#include <iostream>
#include <cstdlib>

// 简化的C2R开关检测逻辑
bool IsC2RLogEnabled() {
  const char* env_var = std::getenv("C2R_LOG");
  return env_var && std::string(env_var) == "1";
}

int main() {
  std::cout << "=== C2R日志开关测试 ===" << std::endl;
  
  if (IsC2RLogEnabled()) {
    std::cout << "✅ C2R日志已启用" << std::endl;
    std::cout << "[C2R-TEST] MonoUs=1234567890, FrameId=1, RtpTs=12345, Ssrc=67890" << std::endl;
    std::cout << "[C2R-SR-RX] MonoUs=1234567891, SrNtpUs=9876543210123456, RtpTs=12346, Ssrc=67890" << std::endl;
    std::cout << "[C2R-FRAME-META] MonoUs=1234567892, FrameId=1, RtpTs=12345, CaptureNtpUs=9876543210000000, Ssrc=67890" << std::endl;
  } else {
    std::cout << "❌ C2R日志已禁用" << std::endl;
    std::cout << "提示: 使用 C2R_LOG=1 启用日志" << std::endl;
  }
  
  return 0;
}