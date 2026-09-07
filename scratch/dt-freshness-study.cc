/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * @file dt-freshness-study.cc
 * @brief Controlled IP/NDN Digital-Twin freshness experiment for ndnSIM.
 *
 * Implemented arms:
 *   A - IPv4/UDP source retrieval (no cache)
 *   B - NDN with Content Store disabled
 *   C - NDN native FreshnessPeriod + MustBeFresh
 *   D - NDN cache with request-specific expected-arrival-age validation
 *
 * Implemented experiments in v0.3:
 *   smoke - short end-to-end validation
 *   e1    - static freshness/efficiency sweep foundation
 *   e4    - heterogeneous strict/relaxed freshness requirements
 */

#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"
#include "ns3/ndnSIM-module.h"
#include "ns3/point-to-point-module.h"

#include "../dt-study-src/csv-logger.hpp"
#include "../dt-study-src/dt-state.hpp"
#include "../dt-study-src/experiment-config.hpp"
#include "../dt-study-src/ip-apps.hpp"
#include "../dt-study-src/ndn-apps.hpp"
#include "../dt-study-src/topology.hpp"
#include "../dt-study-src/traffic-meter.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

namespace ns3 {
namespace {

using dtstudy::Arm;
using dtstudy::ArmToString;
using dtstudy::BackhaulMeter;
using dtstudy::BuildSharedTopology;
using dtstudy::CsvLogger;
using dtstudy::DtNdnConsumer;
using dtstudy::DtNdnProducer;
using dtstudy::DtUdpClient;
using dtstudy::DtUdpServer;
using dtstudy::ExperimentConfig;
using dtstudy::MakeRunDirectory;
using dtstudy::ParseArm;
using dtstudy::PhysicalStateModel;
using dtstudy::StudyTopology;

constexpr uint16_t IP_SERVER_PORT = 9000;
constexpr char DT_PREFIX[] = "/dt/robot27/state";

bool
UseStrictConsumer(const ExperimentConfig& cfg)
{
  return cfg.experiment == "smoke" ||
         cfg.experiment == "e1" ||
         cfg.experiment == "e4";
}

bool
UseRelaxedConsumer(const ExperimentConfig& cfg)
{
  return cfg.experiment == "e4";
}

uint32_t
StrictBudgetMs(const ExperimentConfig& cfg)
{
  return cfg.experiment == "e4" ? cfg.strictFmaxMs : cfg.fmaxMs;
}

void
InstallIpArm(const ExperimentConfig& cfg,
             const StudyTopology& topology,
             const std::shared_ptr<PhysicalStateModel>& stateModel,
             const std::shared_ptr<CsvLogger>& logger)
{
  InternetStackHelper internet;
  internet.Install(topology.allNodes);

  Ipv4AddressHelper address;

  address.SetBase("10.1.1.0", "255.255.255.0");
  address.Assign(topology.strictToMec1);

  address.SetBase("10.1.2.0", "255.255.255.0");
  address.Assign(topology.relaxedToMec1);

  address.SetBase("10.1.3.0", "255.255.255.0");
  address.Assign(topology.mec1ToMec2);

  address.SetBase("10.1.4.0", "255.255.255.0");
  address.Assign(topology.mec2ToMec3);

  address.SetBase("10.1.5.0", "255.255.255.0");
  Ipv4InterfaceContainer producerInterfaces = address.Assign(topology.producerToMec2);

  Ipv4GlobalRoutingHelper::PopulateRoutingTables();

  const Ipv4Address producerAddress = producerInterfaces.GetAddress(0);

  Ptr<DtUdpServer> server = CreateObject<DtUdpServer>();
  server->Configure(IP_SERVER_PORT, stateModel, cfg.payloadBytes);
  topology.producer->AddApplication(server);
  server->SetStartTime(Seconds(0.0));
  server->SetStopTime(Seconds(cfg.simulationTimeS));

  if (UseStrictConsumer(cfg)) {
    Ptr<DtUdpClient> client = CreateObject<DtUdpClient>();
    client->Configure("strict",
                      producerAddress,
                      IP_SERVER_PORT,
                      StrictBudgetMs(cfg),
                      cfg.requestRateHz,
                      cfg.requestJitterMs,
                      cfg.requestTimeoutMs,
                      cfg.run,
                      cfg.experiment,
                      stateModel,
                      logger,
                      1,
                      cfg.warmupTimeS,
                      100);
    topology.strictConsumer->AddApplication(client);
    client->SetStartTime(Seconds(0.0));
    client->SetStopTime(Seconds(cfg.simulationTimeS));
  }

  if (UseRelaxedConsumer(cfg)) {
    Ptr<DtUdpClient> client = CreateObject<DtUdpClient>();
    client->Configure("relaxed",
                      producerAddress,
                      IP_SERVER_PORT,
                      cfg.relaxedFmaxMs,
                      cfg.requestRateHz,
                      cfg.requestJitterMs,
                      cfg.requestTimeoutMs,
                      cfg.run,
                      cfg.experiment,
                      stateModel,
                      logger,
                      2,
                      cfg.warmupTimeS,
                      150);
    topology.relaxedConsumer->AddApplication(client);
    client->SetStartTime(Seconds(0.0));
    client->SetStopTime(Seconds(cfg.simulationTimeS));
  }
}

/**
 * Install NDN stacks while keeping caching restricted to MEC nodes.
 *
 * This separation is essential experimentally: if consumers also had a CS,
 * a consumer could satisfy its own next request locally and the measured
 * cache benefit would no longer isolate MEC in-network caching.
 */
void
InstallNdnStacks(const ExperimentConfig& cfg,
                  Arm arm,
                  const StudyTopology& topology)
{
  NodeContainer endpoints;
  endpoints.Add(topology.strictConsumer);
  endpoints.Add(topology.relaxedConsumer);
  endpoints.Add(topology.producer);

  ndn::StackHelper endpointStack;
  endpointStack.setPolicy("nfd::cs::lru");
  endpointStack.setCsSize(0);
  endpointStack.Install(endpoints);

  NodeContainer mecNodes;
  mecNodes.Add(topology.mec1);
  mecNodes.Add(topology.mec2);
  mecNodes.Add(topology.mec3);

  ndn::StackHelper mecStack;
  mecStack.setPolicy("nfd::cs::lru");
  mecStack.setCsSize(arm == Arm::NDN_NO_CACHE ? 0 : cfg.cacheSizePackets);
  mecStack.Install(mecNodes);
}

void
InstallNdnArm(const ExperimentConfig& cfg,
              Arm arm,
              const StudyTopology& topology,
              const std::shared_ptr<PhysicalStateModel>& stateModel,
              const std::shared_ptr<CsvLogger>& logger,
              const std::string& runDirectory)
{
  InstallNdnStacks(cfg, arm, topology);

  ndn::StrategyChoiceHelper::InstallAll(
    DT_PREFIX,
    "/localhost/nfd/strategy/best-route");

  ndn::GlobalRoutingHelper routing;
  routing.InstallAll();
  routing.AddOrigins(DT_PREFIX, topology.producer);
  ndn::GlobalRoutingHelper::CalculateRoutes();

  Ptr<DtNdnProducer> producer = CreateObject<DtNdnProducer>();
  producer->Configure(DT_PREFIX,
                      stateModel,
                      cfg.nativeFreshnessMs,
                      cfg.payloadBytes);
  topology.producer->AddApplication(producer);
  producer->SetStartTime(Seconds(0.0));
  producer->SetStopTime(Seconds(cfg.simulationTimeS));

  if (UseStrictConsumer(cfg)) {
    Ptr<DtNdnConsumer> consumer = CreateObject<DtNdnConsumer>();
    consumer->Configure("strict",
                        DT_PREFIX,
                        arm,
                        StrictBudgetMs(cfg),
                        cfg.requestRateHz,
                        cfg.requestJitterMs,
                        cfg.requestTimeoutMs,
                        cfg.run,
                        cfg.experiment,
                        stateModel,
                        logger,
                        1,
                        cfg.warmupTimeS,
                        100);
    topology.strictConsumer->AddApplication(consumer);
    consumer->SetStartTime(Seconds(0.0));
    consumer->SetStopTime(Seconds(cfg.simulationTimeS));
  }

  if (UseRelaxedConsumer(cfg)) {
    Ptr<DtNdnConsumer> consumer = CreateObject<DtNdnConsumer>();
    consumer->Configure("relaxed",
                        DT_PREFIX,
                        arm,
                        cfg.relaxedFmaxMs,
                        cfg.requestRateHz,
                        cfg.requestJitterMs,
                        cfg.requestTimeoutMs,
                        cfg.run,
                        cfg.experiment,
                        stateModel,
                        logger,
                        2,
                        cfg.warmupTimeS,
                        150);
    topology.relaxedConsumer->AddApplication(consumer);
    consumer->SetStartTime(Seconds(0.0));
    consumer->SetStopTime(Seconds(cfg.simulationTimeS));
  }

  // Detailed NDN trace for debugging/secondary analysis.  Cache hit/miss
  // accounting uses the supplied NFD instrumentation patch because the stock
  // The legacy CsTracer is not used for publication cache metrics; exact NFD CS events are logged by the supplied Forwarder instrumentation.
  ndn::L3RateTracer::InstallAll(runDirectory + "/ndn-l3-rate-trace.tsv",
                                Seconds(0.5));
}

bool
ValidateConfiguration(const ExperimentConfig& cfg, Arm arm)
{
  if (cfg.experiment != "smoke" &&
      cfg.experiment != "e1" &&
      cfg.experiment != "e4") {
    std::cerr << "v0.3 implements only: smoke, e1, e4.\n";
    return false;
  }

  if (cfg.simulationTimeS <= cfg.warmupTimeS) {
    std::cerr << "simulationTime must be greater than warmupTime.\n";
    return false;
  }

  if (cfg.requestRateHz <= 0.0 || cfg.updatePeriodMs == 0 || cfg.requestJitterMs < 0.0 ||
      cfg.requestTimeoutMs == 0 || cfg.freshnessDeliveryGuardMs < 0.0) {
    std::cerr << "requestRateHz/updatePeriodMs/requestTimeoutMs must be positive; "
              << "requestJitterMs/freshnessDeliveryGuardMs must be non-negative.\n";
    return false;
  }

  const double minimumRequestIntervalMs = (1000.0 / cfg.requestRateHz) - cfg.requestJitterMs;
  if (minimumRequestIntervalMs <= static_cast<double>(cfg.requestTimeoutMs)) {
    std::cerr << "Fixed-workload invariant requires requestTimeoutMs < minimum request interval. "
              << "Current minimum interval is " << minimumRequestIntervalMs << " ms.\n";
    return false;
  }

  if (arm == Arm::NDN_FRESHNESS_AWARE) {
    const uint32_t maxBudgetMs = cfg.experiment == "e4"
      ? std::max(cfg.strictFmaxMs, cfg.relaxedFmaxMs)
      : cfg.fmaxMs;

    if (maxBudgetMs > 4095u) {
      std::cerr << "Arm D's simulation-only nonce carrier currently supports "
                << "F_max <= 4095 ms.\n";
      return false;
    }
  }

  return true;
}

} // unnamed namespace

int
main(int argc, char* argv[])
{
  ExperimentConfig cfg;

  CommandLine cmd;
  cmd.AddValue("arm",
               "A=IP, B=NDN no cache, C=NDN native, D=NDN freshness-aware",
               cfg.arm);
  cmd.AddValue("experiment", "smoke, e1, or e4 in v0.3", cfg.experiment);
  cmd.AddValue("run", "Run/seed identifier", cfg.run);
  cmd.AddValue("simulationTime", "Simulation duration [s]", cfg.simulationTimeS);
  cmd.AddValue("warmupTime", "Warm-up excluded from measurement [s]", cfg.warmupTimeS);
  cmd.AddValue("updatePeriodMs", "DT update period [ms]", cfg.updatePeriodMs);
  cmd.AddValue("requestRateHz", "Consumer request rate [Hz]", cfg.requestRateHz);
  cmd.AddValue("requestJitterMs",
               "Symmetric request-interval jitter [ms]; 0 disables jitter",
               cfg.requestJitterMs);
  cmd.AddValue("requestTimeoutMs",
               "Application request timeout [ms]; must be below minimum request interval",
               cfg.requestTimeoutMs);
  cmd.AddValue("fmaxMs", "E1 freshness budget [ms]", cfg.fmaxMs);
  cmd.AddValue("strictFmaxMs", "Strict consumer F_max [ms]", cfg.strictFmaxMs);
  cmd.AddValue("relaxedFmaxMs", "Relaxed consumer F_max [ms]", cfg.relaxedFmaxMs);
  cmd.AddValue("nativeFreshnessMs",
               "Arm C producer FreshnessPeriod [ms]",
               cfg.nativeFreshnessMs);
  cmd.AddValue("cacheSize", "MEC Content Store capacity [packets]", cfg.cacheSizePackets);
  cmd.AddValue("freshnessDeliveryGuardMs",
               "Arm D downstream delivery-age guard [ms]",
               cfg.freshnessDeliveryGuardMs);
  cmd.AddValue("payloadBytes", "Approximate DT Data payload bytes", cfg.payloadBytes);
  cmd.AddValue("outputRoot", "Result root directory", cfg.outputRoot);
  cmd.AddValue("accessRate", "Access-link data rate", cfg.accessRate);
  cmd.AddValue("coreRate", "Core-link data rate", cfg.coreRate);
  cmd.AddValue("accessDelay", "Access-link propagation delay", cfg.accessDelay);
  cmd.AddValue("coreDelay", "Core-link propagation delay", cfg.coreDelay);
  cmd.Parse(argc, argv);

  Arm arm;
  try {
    arm = ParseArm(cfg.arm);
  }
  catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 2;
  }

  cfg.arm = ArmToString(arm);

  if (!ValidateConfiguration(cfg, arm)) {
    return 2;
  }

  RngSeedManager::SetRun(cfg.run);

  const std::string runDirectory = MakeRunDirectory(cfg);
  auto logger = std::make_shared<CsvLogger>(cfg, runDirectory);
  auto stateModel = std::make_shared<PhysicalStateModel>(
    cfg.updatePeriodMs,
    cfg.speedMps,
    cfg.lateralAmplitudeM,
    cfg.lateralOmegaRadS);

  StudyTopology topology = BuildSharedTopology(cfg);

  // Measure the same physical MEC core links using the same trace source in
  // every arm, rather than comparing protocol-specific accounting methods.
  BackhaulMeter backhaulMeter;
  backhaulMeter.SetMeasurementStart(cfg.warmupTimeS);
  backhaulMeter.Attach(topology.mec1ToMec2, topology.mec2ToMec3);

  stateModel->Start();

  if (arm == Arm::IP) {
    InstallIpArm(cfg, topology, stateModel, logger);
  }
  else {
    // The optional NFD instrumentation patch reads this environment variable
    // and emits exact CS HIT/MISS/STALE_REJECT events.  For B/C it is purely
    // observational; only the Arm-D nonce marker activates freshness rejection.
    const std::string cacheCsv = runDirectory + "/cache-events.csv";
    std::remove(cacheCsv.c_str());
    ::setenv("DT_STUDY_CACHE_CSV", cacheCsv.c_str(), 1);

    const uint64_t deliveryGuardUs = static_cast<uint64_t>(
      std::llround(cfg.freshnessDeliveryGuardMs * 1000.0));
    const std::string deliveryGuardUsText = std::to_string(deliveryGuardUs);
    ::setenv("DT_STUDY_DELIVERY_GUARD_US", deliveryGuardUsText.c_str(), 1);

    InstallNdnArm(cfg, arm, topology, stateModel, logger, runDirectory);
  }

  Simulator::Stop(Seconds(cfg.simulationTimeS));
  Simulator::Run();

  logger->Flush();
  backhaulMeter.WriteCsv(runDirectory);
  Simulator::Destroy();
  logger->Flush();

  std::cout << "Experiment complete.\n"
            << "Results: " << runDirectory << '\n'
            << "Primary CSV: " << runDirectory << "/requests.csv\n";

  return 0;
}

} // namespace ns3

int
main(int argc, char* argv[])
{
  return ns3::main(argc, argv);
}
