#ifndef DT_STUDY_TOPOLOGY_HPP
#define DT_STUDY_TOPOLOGY_HPP

#include "experiment-config.hpp"

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"

namespace dtstudy {

/**
 * Common physical topology used by all protocol arms.
 *
 *   StrictConsumer  --\
 *                     MEC1 -- MEC2 -- MEC3
 *   RelaxedConsumer --/         |
 *                           Robot27Producer
 *
 * E1 and E4 use the static producer attachment at MEC2.  MEC3 is retained in
 * the topology now so the same physical graph can be reused by the mobility
 * experiment in the next milestone.
 */
struct StudyTopology
{
  ns3::Ptr<ns3::Node> strictConsumer;
  ns3::Ptr<ns3::Node> mec1;
  ns3::Ptr<ns3::Node> mec2;
  ns3::Ptr<ns3::Node> mec3;
  ns3::Ptr<ns3::Node> relaxedConsumer;
  ns3::Ptr<ns3::Node> producer;

  ns3::NodeContainer allNodes;

  ns3::NetDeviceContainer strictToMec1;
  ns3::NetDeviceContainer relaxedToMec1;
  ns3::NetDeviceContainer mec1ToMec2;
  ns3::NetDeviceContainer mec2ToMec3;
  ns3::NetDeviceContainer producerToMec2;
};

inline StudyTopology
BuildSharedTopology(const ExperimentConfig& cfg)
{
  StudyTopology topology;
  topology.allNodes.Create(6);

  topology.strictConsumer = topology.allNodes.Get(0);
  topology.mec1 = topology.allNodes.Get(1);
  topology.mec2 = topology.allNodes.Get(2);
  topology.mec3 = topology.allNodes.Get(3);
  topology.relaxedConsumer = topology.allNodes.Get(4);
  topology.producer = topology.allNodes.Get(5);

  ns3::Names::Add("StrictConsumer", topology.strictConsumer);
  ns3::Names::Add("MEC1", topology.mec1);
  ns3::Names::Add("MEC2", topology.mec2);
  ns3::Names::Add("MEC3", topology.mec3);
  ns3::Names::Add("RelaxedConsumer", topology.relaxedConsumer);
  ns3::Names::Add("Robot27Producer", topology.producer);

  ns3::PointToPointHelper access;
  access.SetDeviceAttribute("DataRate", ns3::StringValue(cfg.accessRate));
  access.SetChannelAttribute("Delay", ns3::StringValue(cfg.accessDelay));
  access.SetQueue("ns3::DropTailQueue<Packet>",
                  "MaxSize",
                  ns3::StringValue("200p"));

  ns3::PointToPointHelper core;
  core.SetDeviceAttribute("DataRate", ns3::StringValue(cfg.coreRate));
  core.SetChannelAttribute("Delay", ns3::StringValue(cfg.coreDelay));
  core.SetQueue("ns3::DropTailQueue<Packet>",
                "MaxSize",
                ns3::StringValue("200p"));

  topology.strictToMec1 = access.Install(topology.strictConsumer, topology.mec1);
  topology.relaxedToMec1 = access.Install(topology.relaxedConsumer, topology.mec1);
  topology.mec1ToMec2 = core.Install(topology.mec1, topology.mec2);
  topology.mec2ToMec3 = core.Install(topology.mec2, topology.mec3);
  topology.producerToMec2 = access.Install(topology.producer, topology.mec2);

  return topology;
}

} // namespace dtstudy

#endif // DT_STUDY_TOPOLOGY_HPP
