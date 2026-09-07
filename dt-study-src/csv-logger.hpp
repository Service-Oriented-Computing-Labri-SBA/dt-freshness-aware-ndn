#ifndef DT_STUDY_CSV_LOGGER_HPP
#define DT_STUDY_CSV_LOGGER_HPP
#include "experiment-config.hpp"
#include <cerrno>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
namespace dtstudy {
inline void EnsureDirectory(const std::string& path){ if(::mkdir(path.c_str(),0755)!=0 && errno!=EEXIST) throw std::runtime_error("Cannot create directory: "+path); }
inline std::string MakeRunDirectory(const ExperimentConfig& cfg){
  EnsureDirectory(cfg.outputRoot); std::ostringstream n; n<<cfg.outputRoot<<'/'<<cfg.arm<<'-'<<cfg.experiment;
  if(cfg.experiment=="e4") n<<"-strict"<<cfg.strictFmaxMs<<"-relaxed"<<cfg.relaxedFmaxMs; else n<<"-fmax"<<cfg.fmaxMs;
  n<<"-native"<<cfg.nativeFreshnessMs<<"-cache"<<cfg.cacheSizePackets<<"-run"<<cfg.run; EnsureDirectory(n.str()); return n.str(); }
struct OfferedRequestRecord{uint32_t run=0;std::string arm,approachName,experiment,consumer;uint64_t requestId=0;uint32_t interestNonce=0,fmaxMs=0;uint64_t sendTimeUs=0;std::string transport;};
struct TimeoutRecord{uint32_t run=0;std::string arm,approachName,experiment,consumer;uint64_t requestId=0;uint32_t interestNonce=0;uint64_t sendTimeUs=0,timeoutTimeUs=0;std::string transport;};
struct RequestRecord{uint32_t run=0;std::string arm,approachName,experiment;double simTimeS=0;std::string consumer;uint64_t requestId=0;uint32_t interestNonce=0,fmaxMs=0;uint64_t sendTimeUs=0,receiveTimeUs=0;double latencyMs=0;uint64_t generationTimeUs=0;double aoiMs=0;uint64_t stateVersion=0;double stateX=0,stateY=0,truthX=0,truthY=0,dtError=0;bool freshnessValid=false;std::string transport;};
class CsvLogger{
public:
 CsvLogger(const ExperimentConfig& cfg,const std::string& d):m_cfg(cfg),m_runDirectory(d){
  m_requests.open((d+"/requests.csv").c_str(),std::ios::out|std::ios::trunc);
  m_offered.open((d+"/offered-requests.csv").c_str(),std::ios::out|std::ios::trunc);
  m_timeouts.open((d+"/timeouts.csv").c_str(),std::ios::out|std::ios::trunc);
  if(!m_requests.is_open()||!m_offered.is_open()||!m_timeouts.is_open()) throw std::runtime_error("Cannot create request CSV files in "+d);
  m_requests<<"run,arm,approach_name,experiment,sim_time_s,consumer,request_id,interest_nonce,fmax_ms,send_time_us,receive_time_us,latency_ms,generation_time_us,aoi_ms,state_version,state_x,state_y,truth_x,truth_y,dt_error,freshness_valid,transport\n";
  m_offered<<"run,arm,approach_name,experiment,consumer,request_id,interest_nonce,fmax_ms,send_time_us,transport\n";
  m_timeouts<<"run,arm,approach_name,experiment,consumer,request_id,interest_nonce,send_time_us,timeout_time_us,transport\n";
  WriteConfig();
  Flush();
 }
 ~CsvLogger(){Flush();}
 void Flush(){if(m_requests.is_open())m_requests.flush();if(m_offered.is_open())m_offered.flush();if(m_timeouts.is_open())m_timeouts.flush();}
 void LogOfferedRequest(const OfferedRequestRecord&r){m_offered<<r.run<<','<<r.arm<<','<<r.approachName<<','<<r.experiment<<','<<r.consumer<<','<<r.requestId<<','<<r.interestNonce<<','<<r.fmaxMs<<','<<r.sendTimeUs<<','<<r.transport<<'\n';}
 void LogTimeout(const TimeoutRecord&r){m_timeouts<<r.run<<','<<r.arm<<','<<r.approachName<<','<<r.experiment<<','<<r.consumer<<','<<r.requestId<<','<<r.interestNonce<<','<<r.sendTimeUs<<','<<r.timeoutTimeUs<<','<<r.transport<<'\n';}
 void LogRequest(const RequestRecord&r){m_requests<<r.run<<','<<r.arm<<','<<r.approachName<<','<<r.experiment<<','<<std::fixed<<std::setprecision(6)<<r.simTimeS<<','<<r.consumer<<','<<r.requestId<<','<<r.interestNonce<<','<<r.fmaxMs<<','<<r.sendTimeUs<<','<<r.receiveTimeUs<<','<<r.latencyMs<<','<<r.generationTimeUs<<','<<r.aoiMs<<','<<r.stateVersion<<','<<std::setprecision(9)<<r.stateX<<','<<r.stateY<<','<<r.truthX<<','<<r.truthY<<','<<r.dtError<<','<<(r.freshnessValid?1:0)<<','<<r.transport<<'\n';}
private:
 void WriteConfig()const{std::ofstream o((m_runDirectory+"/config.csv").c_str(),std::ios::out|std::ios::trunc);if(!o.is_open())throw std::runtime_error("Cannot create config.csv");o<<"key,value\n"<<"arm,"<<m_cfg.arm<<'\n'<<"experiment,"<<m_cfg.experiment<<'\n'<<"run,"<<m_cfg.run<<'\n'<<"simulation_time_s,"<<m_cfg.simulationTimeS<<'\n'<<"warmup_time_s,"<<m_cfg.warmupTimeS<<'\n'<<"update_period_ms,"<<m_cfg.updatePeriodMs<<'\n'<<"request_rate_hz,"<<m_cfg.requestRateHz<<'\n'<<"request_jitter_ms,"<<m_cfg.requestJitterMs<<'\n'<<"request_timeout_ms,"<<m_cfg.requestTimeoutMs<<'\n'<<"strict_fmax_ms,"<<m_cfg.strictFmaxMs<<'\n'<<"relaxed_fmax_ms,"<<m_cfg.relaxedFmaxMs<<'\n'<<"fmax_ms,"<<m_cfg.fmaxMs<<'\n'<<"native_freshness_ms,"<<m_cfg.nativeFreshnessMs<<'\n'<<"cache_size_packets,"<<m_cfg.cacheSizePackets<<'\n'<<"freshness_delivery_guard_ms,"<<m_cfg.freshnessDeliveryGuardMs<<'\n'<<"payload_bytes,"<<m_cfg.payloadBytes<<'\n'<<"access_rate,"<<m_cfg.accessRate<<'\n'<<"core_rate,"<<m_cfg.coreRate<<'\n'<<"access_delay,"<<m_cfg.accessDelay<<'\n'<<"core_delay,"<<m_cfg.coreDelay<<'\n'<<"speed_mps,"<<m_cfg.speedMps<<'\n'<<"lateral_amplitude_m,"<<m_cfg.lateralAmplitudeM<<'\n'<<"lateral_omega_rad_s,"<<m_cfg.lateralOmegaRadS<<'\n';}
 ExperimentConfig m_cfg;std::string m_runDirectory;std::ofstream m_requests,m_offered,m_timeouts;};
} // namespace dtstudy
#endif
