#ifndef DT_STUDY_EXPERIMENT_CONFIG_HPP
#define DT_STUDY_EXPERIMENT_CONFIG_HPP

#include <cstdint>
#include <stdexcept>
#include <string>

namespace dtstudy {

enum class Arm { IP, NDN_NO_CACHE, NDN_NATIVE, NDN_FRESHNESS_AWARE };

inline Arm ParseArm(const std::string& value)
{
  if (value == "A" || value == "a" || value == "ip") return Arm::IP;
  if (value == "B" || value == "b" || value == "ndn-no-cache") return Arm::NDN_NO_CACHE;
  if (value == "C" || value == "c" || value == "ndn-native") return Arm::NDN_NATIVE;
  if (value == "D" || value == "d" || value == "ndn-fa") return Arm::NDN_FRESHNESS_AWARE;
  throw std::runtime_error("Unknown arm '" + value + "'. Use A, B, C, or D.");
}

inline std::string ArmToString(Arm arm)
{
  switch (arm) {
  case Arm::IP: return "A";
  case Arm::NDN_NO_CACHE: return "B";
  case Arm::NDN_NATIVE: return "C";
  case Arm::NDN_FRESHNESS_AWARE: return "D";
  }
  return "UNKNOWN";
}

inline std::string ArmToApproachName(Arm arm)
{
  switch (arm) {
  case Arm::IP: return "IP/UDP - No Cache";
  case Arm::NDN_NO_CACHE: return "NDN - No Cache";
  case Arm::NDN_NATIVE: return "NDN - Native Cache";
  case Arm::NDN_FRESHNESS_AWARE: return "NDN - Freshness-Aware Cache (Proposed)";
  }
  return "UNKNOWN";
}

struct ExperimentConfig
{
  std::string arm = "C";
  std::string experiment = "e4";
  uint32_t run = 1;

  double simulationTimeS = 30.0;
  double warmupTimeS = 2.0;

  uint32_t updatePeriodMs = 10;
  double requestRateHz = 10.0;
  double requestJitterMs = 5.0;
  uint32_t requestTimeoutMs = 80;

  uint32_t strictFmaxMs = 20;
  uint32_t relaxedFmaxMs = 500;
  uint32_t fmaxMs = 100;

  uint32_t nativeFreshnessMs = 500;
  uint32_t cacheSizePackets = 1;
  double freshnessDeliveryGuardMs = 2.0;

  uint32_t payloadBytes = 512;
  std::string accessRate = "100Mbps";
  std::string coreRate = "20Mbps";
  std::string accessDelay = "1ms";
  std::string coreDelay = "5ms";

  double speedMps = 2.0;
  double lateralAmplitudeM = 2.0;
  double lateralOmegaRadS = 0.4;

  std::string outputRoot = "results";
};

} // namespace dtstudy
#endif
