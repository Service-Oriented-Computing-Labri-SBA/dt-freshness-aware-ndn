#ifndef DT_STUDY_DT_STATE_HPP
#define DT_STUDY_DT_STATE_HPP

#include "ns3/core-module.h"

#include <cmath>
#include <cstdint>
#include <utility>

namespace dtstudy {

struct DtState
{
  uint64_t version = 0;
  uint64_t generationTimeUs = 0;
  double x = 0.0;
  double y = 0.0;
};

/**
 * Continuous physical trajectory plus a periodically sampled Digital Twin.
 *
 * The physical truth is available continuously through GetTruthAt().
 * The producer exposes only m_latest, which is refreshed every updatePeriodMs.
 * This distinction is what makes AoI and DT synchronization error measurable.
 */
class PhysicalStateModel
{
public:
  PhysicalStateModel(uint32_t updatePeriodMs,
                     double speedMps,
                     double lateralAmplitudeM,
                     double lateralOmegaRadS)
    : m_updatePeriodMs(updatePeriodMs)
    , m_speedMps(speedMps)
    , m_lateralAmplitudeM(lateralAmplitudeM)
    , m_lateralOmegaRadS(lateralOmegaRadS)
  {
  }

  void
  Start()
  {
    UpdateSnapshot();
  }

  const DtState&
  GetLatestSnapshot() const
  {
    return m_latest;
  }

  std::pair<double, double>
  GetTruthAt(ns3::Time time) const
  {
    const double t = time.GetSeconds();
    const double x = m_speedMps * t;
    const double y = m_lateralAmplitudeM * std::sin(m_lateralOmegaRadS * t);
    return {x, y};
  }

private:
  void
  UpdateSnapshot()
  {
    const ns3::Time now = ns3::Simulator::Now();
    const auto truth = GetTruthAt(now);

    ++m_latest.version;
    m_latest.generationTimeUs = static_cast<uint64_t>(now.GetMicroSeconds());
    m_latest.x = truth.first;
    m_latest.y = truth.second;

    m_updateEvent = ns3::Simulator::Schedule(ns3::MilliSeconds(m_updatePeriodMs),
                                             &PhysicalStateModel::UpdateSnapshot,
                                             this);
  }

private:
  uint32_t m_updatePeriodMs;
  double m_speedMps;
  double m_lateralAmplitudeM;
  double m_lateralOmegaRadS;

  DtState m_latest;
  ns3::EventId m_updateEvent;
};

} // namespace dtstudy

#endif // DT_STUDY_DT_STATE_HPP
