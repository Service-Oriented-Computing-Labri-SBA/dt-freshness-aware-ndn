#ifndef DT_STUDY_WIRE_FORMAT_HPP
#define DT_STUDY_WIRE_FORMAT_HPP

#include "dt-state.hpp"

#include <cstdint>
#include <iomanip>
#include <sstream>
#include <string>

namespace dtstudy {

inline std::string
EncodeState(const DtState& state, uint32_t targetBytes)
{
  std::ostringstream os;
  os << "DT1," << state.version << ',' << state.generationTimeUs << ','
     << std::setprecision(12) << state.x << ',' << state.y << ',';

  std::string payload = os.str();
  if (payload.size() < targetBytes) {
    payload.append(targetBytes - payload.size(), 'P');
  }
  return payload;
}

inline bool
DecodeState(const std::string& payload, DtState& state)
{
  if (payload.compare(0, 4, "DT1,") != 0) {
    return false;
  }

  std::stringstream ss(payload);
  std::string token;
  std::getline(ss, token, ','); // DT1

  if (!std::getline(ss, token, ',')) return false;
  state.version = std::stoull(token);

  if (!std::getline(ss, token, ',')) return false;
  state.generationTimeUs = std::stoull(token);

  if (!std::getline(ss, token, ',')) return false;
  state.x = std::stod(token);

  if (!std::getline(ss, token, ',')) return false;
  state.y = std::stod(token);

  return true;
}

inline std::string
EncodeIpRequest(uint64_t requestId, uint32_t fmaxMs)
{
  return "REQ1," + std::to_string(requestId) + "," + std::to_string(fmaxMs);
}

inline bool
DecodeIpRequest(const std::string& payload, uint64_t& requestId, uint32_t& fmaxMs)
{
  if (payload.compare(0, 5, "REQ1,") != 0) {
    return false;
  }

  std::stringstream ss(payload);
  std::string token;
  std::getline(ss, token, ','); // REQ1

  if (!std::getline(ss, token, ',')) return false;
  requestId = std::stoull(token);

  if (!std::getline(ss, token, ',')) return false;
  fmaxMs = std::stoul(token);

  return true;
}

inline std::string
EncodeIpResponse(uint64_t requestId, const DtState& state, uint32_t targetBytes)
{
  std::ostringstream os;
  os << "RSP1," << requestId << ',' << state.version << ','
     << state.generationTimeUs << ',' << std::setprecision(12)
     << state.x << ',' << state.y << ',';

  std::string payload = os.str();
  if (payload.size() < targetBytes) {
    payload.append(targetBytes - payload.size(), 'P');
  }
  return payload;
}

inline bool
DecodeIpResponse(const std::string& payload, uint64_t& requestId, DtState& state)
{
  if (payload.compare(0, 5, "RSP1,") != 0) {
    return false;
  }

  std::stringstream ss(payload);
  std::string token;
  std::getline(ss, token, ','); // RSP1

  if (!std::getline(ss, token, ',')) return false;
  requestId = std::stoull(token);

  if (!std::getline(ss, token, ',')) return false;
  state.version = std::stoull(token);

  if (!std::getline(ss, token, ',')) return false;
  state.generationTimeUs = std::stoull(token);

  if (!std::getline(ss, token, ',')) return false;
  state.x = std::stod(token);

  if (!std::getline(ss, token, ',')) return false;
  state.y = std::stod(token);

  return true;
}

/**
 * Simulation-only Arm-D metadata carrier.
 *
 * The NDN content name is deliberately unchanged so strict and relaxed
 * consumers share the same Content Store entry.  F_max travels in the
 * Interest Nonce only for this prototype; it is not proposed as a production
 * NDN packet format.
 *
 *  bits 31..24 : 0xFD experiment marker
 *  bits 23..12 : F_max in milliseconds (0..4095)
 *  bits 11..10 : consumer identifier (0..3)
 *  bits  9..0  : request sequence (0..1023)
 */
inline uint32_t
EncodeFreshnessAwareNonce(uint32_t fmaxMs, uint64_t requestId, uint32_t consumerSalt)
{
  const uint32_t boundedFmax = (fmaxMs > 4095u) ? 4095u : fmaxMs;
  return 0xFD000000u |
         ((boundedFmax & 0x0FFFu) << 12) |
         ((consumerSalt & 0x03u) << 10) |
         (static_cast<uint32_t>(requestId) & 0x03FFu);
}

inline uint32_t
EncodeOrdinaryNonce(uint64_t requestId, uint32_t consumerSalt)
{
  // High byte is kept different from 0xFD so the NFD patch never interprets
  // an Arm-B/C Interest as freshness-aware.
  return ((consumerSalt & 0x7Fu) << 16) |
         (static_cast<uint32_t>(requestId) & 0xFFFFu);
}

} // namespace dtstudy

#endif // DT_STUDY_WIRE_FORMAT_HPP
