#ifndef DT_STUDY_TRAFFIC_METER_HPP
#define DT_STUDY_TRAFFIC_METER_HPP

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>

namespace dtstudy {

struct LinkCounter
{
  uint64_t packets = 0;
  uint64_t bytes = 0;
};

class BackhaulMeter
{
public:
  void SetMeasurementStart(double seconds) { m_measurementStartS = seconds; }

  void Attach(const ns3::NetDeviceContainer& mec1Mec2,
              const ns3::NetDeviceContainer& mec2Mec3)
  {
    mec1Mec2.Get(0)->TraceConnectWithoutContext(
      "MacTx", ns3::MakeCallback(&BackhaulMeter::OnMec1ToMec2, this));
    mec1Mec2.Get(1)->TraceConnectWithoutContext(
      "MacTx", ns3::MakeCallback(&BackhaulMeter::OnMec2ToMec1, this));
    mec2Mec3.Get(0)->TraceConnectWithoutContext(
      "MacTx", ns3::MakeCallback(&BackhaulMeter::OnMec2ToMec3, this));
    mec2Mec3.Get(1)->TraceConnectWithoutContext(
      "MacTx", ns3::MakeCallback(&BackhaulMeter::OnMec3ToMec2, this));
  }

  void WriteCsv(const std::string& runDir) const
  {
    std::ofstream out((runDir + "/link-traffic.csv").c_str(),
                      std::ios::out | std::ios::trunc);
    if (!out.is_open()) throw std::runtime_error("Cannot create link-traffic.csv");

    out << "link,direction,packets,bytes\n";
    Write(out, "MEC1-MEC2", "MEC1->MEC2", m_mec1ToMec2);
    Write(out, "MEC1-MEC2", "MEC2->MEC1", m_mec2ToMec1);
    Write(out, "MEC2-MEC3", "MEC2->MEC3", m_mec2ToMec3);
    Write(out, "MEC2-MEC3", "MEC3->MEC2", m_mec3ToMec2);
  }

private:
  bool InMeasurementWindow() const
  {
    return ns3::Simulator::Now().GetSeconds() >= m_measurementStartS;
  }

  void Add(LinkCounter& c, ns3::Ptr<const ns3::Packet> p)
  {
    if (!InMeasurementWindow()) return;
    ++c.packets;
    c.bytes += p->GetSize();
  }

  static void Write(std::ofstream& out, const char* link,
                    const char* direction, const LinkCounter& c)
  {
    out << link << ',' << direction << ',' << c.packets << ',' << c.bytes << '\n';
  }

  void OnMec1ToMec2(ns3::Ptr<const ns3::Packet> p) { Add(m_mec1ToMec2, p); }
  void OnMec2ToMec1(ns3::Ptr<const ns3::Packet> p) { Add(m_mec2ToMec1, p); }
  void OnMec2ToMec3(ns3::Ptr<const ns3::Packet> p) { Add(m_mec2ToMec3, p); }
  void OnMec3ToMec2(ns3::Ptr<const ns3::Packet> p) { Add(m_mec3ToMec2, p); }

  double m_measurementStartS = 0.0;
  LinkCounter m_mec1ToMec2, m_mec2ToMec1, m_mec2ToMec3, m_mec3ToMec2;
};

} // namespace dtstudy
#endif
