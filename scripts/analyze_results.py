#!/usr/bin/env python3
"""Analyze DT freshness-study v0.3 using complete request-level distributions."""
from __future__ import annotations
import argparse, math
from pathlib import Path
import numpy as np
import pandas as pd
E1_THRESHOLDS_MS=[10,20,50,100,200,500,1000,2000]
NODE_NAMES={0:"StrictConsumer",1:"MEC1",2:"MEC2",3:"MEC3",4:"RelaxedConsumer",5:"Robot27Producer"}
APPROACH_NAMES={"A":"IP/UDP - No Cache","B":"NDN - No Cache","C":"NDN - Native Cache","D":"NDN - Freshness-Aware Cache (Proposed)"}
REQUEST_COLUMNS=["run","arm","approach_name","experiment","sim_time_s","consumer","request_id","interest_nonce","fmax_ms","send_time_us","receive_time_us","latency_ms","generation_time_us","aoi_ms","state_version","state_x","state_y","truth_x","truth_y","dt_error","freshness_valid","transport"]
OFFERED_COLUMNS=["run","arm","approach_name","experiment","consumer","request_id","interest_nonce","fmax_ms","send_time_us","transport"]
TIMEOUT_COLUMNS=["run","arm","approach_name","experiment","consumer","request_id","interest_nonce","send_time_us","timeout_time_us","transport"]
def safe_csv(path,columns=None):
 if not path.exists() or path.stat().st_size==0:return pd.DataFrame(columns=columns or [])
 try:return pd.read_csv(path)
 except pd.errors.EmptyDataError:return pd.DataFrame(columns=columns or [])
def read_config(d):
 p=d/'config.csv'
 if not p.exists():return {}
 f=pd.read_csv(p);return dict(zip(f.key.astype(str),f.value.astype(str)))
def cf(c,k):
 try:return float(c[k])
 except:return math.nan
def load_events(d,c):
 p=d/'cache-events.csv'
 if not p.exists() or p.stat().st_size==0:return pd.DataFrame()
 e=pd.read_csv(p);w=cf(c,'warmup_time_s')*1e6
 if 'time_us' in e and not math.isnan(w):e=e[e.time_us>=w].copy()
 if 'node_context' in e:e['node_name']=e.node_context.map(NODE_NAMES).fillna(e.node_context.map(lambda x:f'Node{x}'))
 return e
def nonce_sets(e):
 if e.empty or 'nonce' not in e:return set(),set()
 h=set(pd.to_numeric(e.loc[e.event=='HIT','nonce'],errors='coerce').dropna().astype('uint64').astype(int));s=set(pd.to_numeric(e.loc[e.event=='STALE_REJECT','nonce'],errors='coerce').dropna().astype('uint64').astype(int));return h,s
def desc(s,p):
 s=pd.to_numeric(s,errors='coerce').dropna().astype(float)
 if s.empty:return {f'{p}_{k}':math.nan for k in ['min','mean','median','std','max']}
 return {f'{p}_min':float(s.min()),f'{p}_mean':float(s.mean()),f'{p}_median':float(s.median()),f'{p}_std':float(s.std(ddof=1)) if len(s)>1 else 0.0,f'{p}_max':float(s.max())}
def backhaul(d,n):
 p=d/'link-traffic.csv'
 if not p.exists():return math.nan,math.nan,math.nan
 t=safe_csv(p,['time_s','link','direction','packets','bytes'])
 if t.empty:return 0.0,0.0,(0.0 if n else math.nan)
 pk=float(pd.to_numeric(t.get('packets',pd.Series(dtype=float)),errors='coerce').fillna(0).sum());b=float(pd.to_numeric(t.get('bytes',pd.Series(dtype=float)),errors='coerce').fillna(0).sum());per=b/n if n else math.nan
 pd.DataFrame([{'backhaul_packets':pk,'backhaul_bytes':b,'backhaul_bytes_per_offered_request':per}]).to_csv(d/'network-summary.csv',index=False);return pk,b,per
def process(d):
 rp,op,tp=d/'requests.csv',d/'offered-requests.csv',d/'timeouts.csv'
 if not rp.exists() or not op.exists():return [],None,None,None
 req=safe_csv(rp,REQUEST_COLUMNS);off=safe_csv(op,OFFERED_COLUMNS);to=safe_csv(tp,TIMEOUT_COLUMNS);c=read_config(d);e=load_events(d,c);hits,stales=nonce_sets(e)
 for f in [req,off,to]:
  if f is not None and not f.empty:
   f['source_dir']=str(d)
   if 'approach_name' not in f and 'arm' in f:f['approach_name']=f.arm.map(APPROACH_NAMES)
   f['native_freshness_ms']=cf(c,'native_freshness_ms');f['cache_size_packets']=cf(c,'cache_size_packets');f['freshness_delivery_guard_ms']=cf(c,'freshness_delivery_guard_ms')
 if not req.empty:
  req['interest_nonce']=pd.to_numeric(req.interest_nonce,errors='coerce');req['cache_hit']=req.interest_nonce.apply(lambda v:math.nan if pd.isna(v) else int(int(v)!=0 and int(v) in hits));req['stale_rejected']=req.interest_nonce.apply(lambda v:math.nan if pd.isna(v) else int(int(v)!=0 and int(v) in stales));req['valid_cache_hit']=np.where(req.cache_hit.isna(),np.nan,((req.cache_hit==1)&(req.freshness_valid==1)).astype(float));req.to_csv(d/'requests-enriched.csv',index=False)
 if not e.empty:e.to_csv(d/'cache-events-filtered.csv',index=False);e.groupby(['node_context','node_name','event'],dropna=False).size().reset_index(name='events').to_csv(d/'cache-summary.csv',index=False)
 pk,b,bpo=backhaul(d,len(off));rows=[]
 for consumer in sorted(set(off.consumer.astype(str))):
  og=off[off.consumer.astype(str)==consumer];rg=req[req.consumer.astype(str)==consumer] if not req.empty else req;tg=to[to.consumer.astype(str)==consumer] if not to.empty else to;n_off,n_sat,n_to=len(og),len(rg),len(tg);arm=str(og.arm.iloc[0]);approach=str(og.approach_name.iloc[0])
  row={'source_dir':str(d),'run':int(og.run.iloc[0]),'arm':arm,'approach_name':approach,'experiment':str(og.experiment.iloc[0]),'consumer':consumer,'fmax_ms':float(og.fmax_ms.iloc[0]),'native_freshness_ms':cf(c,'native_freshness_ms'),'cache_size_packets':cf(c,'cache_size_packets'),'freshness_delivery_guard_ms':cf(c,'freshness_delivery_guard_ms'),'n_offered':n_off,'n_satisfied':n_sat,'n_timeouts':n_to,'satisfaction_ratio':n_sat/n_off if n_off else math.nan,'timeout_ratio':n_to/n_off if n_off else math.nan,'freshness_valid_ratio':float(rg.freshness_valid.mean()) if n_sat else math.nan,'freshness_violation_ratio':float(1-rg.freshness_valid.mean()) if n_sat else math.nan,'cache_hit_ratio_request_level':float(rg.cache_hit.mean()) if n_sat and rg.cache_hit.notna().any() else math.nan,'valid_cache_hit_ratio_request_level':float(rg.valid_cache_hit.mean()) if n_sat and rg.valid_cache_hit.notna().any() else math.nan,'freshness_valid_hit_ratio':float(rg.loc[rg.cache_hit==1,'freshness_valid'].mean()) if n_sat and (rg.cache_hit==1).any() else math.nan,'stale_reject_request_ratio':float(rg.stale_rejected.mean()) if n_sat and rg.stale_rejected.notna().any() else math.nan,'backhaul_packets_run':pk,'backhaul_bytes_run':b,'backhaul_bytes_per_offered_request_run':bpo};row.update(desc(rg.latency_ms,'latency_ms'));row.update(desc(rg.aoi_ms,'aoi_ms'));row.update(desc(rg.dt_error,'dt_error'));rows.append(row)
 return rows,req,off,to
def ci95(s):
 s=pd.to_numeric(s,errors='coerce').dropna().astype(float);return math.nan if len(s)<2 else float(1.96*s.std(ddof=1)/math.sqrt(len(s)))
def write_ci(summary,path):
 metrics=[c for c in summary.columns if c.endswith(('_mean','_median','_std','_min','_max','_ratio','_run')) and c!='run'];keys=['experiment','arm','approach_name','consumer','fmax_ms','native_freshness_ms','cache_size_packets','freshness_delivery_guard_ms'];rows=[]
 for key,g in summary.groupby(keys,dropna=False):
  r=dict(zip(keys,key));r['n_runs']=int(g.run.nunique())
  for m in metrics:
   v=pd.to_numeric(g[m],errors='coerce')
   if v.notna().any():r[m+'_across_runs_mean']=float(v.mean());r[m+'_across_runs_ci95']=ci95(v)
  rows.append(r)
 pd.DataFrame(rows).to_csv(path,index=False)
def e1refs(root,allreq):
 ref=allreq[(allreq.experiment=='e1')&allreq.arm.isin(['A','B','C'])];rows=[]
 for th in E1_THRESHOLDS_MS:
  for (arm,name,run,c),g in ref.groupby(['arm','approach_name','run','consumer']):rows.append({'arm':arm,'approach_name':name,'run':run,'consumer':c,'evaluation_fmax_ms':th,'n_requests':len(g),'freshness_violation_ratio':float((g.aoi_ms>th).mean())})
 pd.DataFrame(rows).to_csv(root/'e1-reference-thresholds.csv',index=False)
def pairing(root,off):
 rows=[]
 for (exp,run,c),g in off.groupby(['experiment','run','consumer']):
  traces=[]
  for source,sg in g.groupby('source_dir'):
   sg=sg.sort_values('request_id');traces.append((source,str(sg.arm.iloc[0]),str(sg.approach_name.iloc[0]),tuple(sg.request_id.astype('uint64')),tuple(sg.send_time_us.astype('uint64'))))
  if not traces:continue
  ref=sorted(traces,key=lambda x:x[1])[0]
  for source,arm,name,ids,times in traces:rows.append({'experiment':exp,'run':run,'consumer':c,'reference_source':ref[0],'source_dir':source,'arm':arm,'approach_name':name,'reference_requests':len(ref[3]),'requests':len(ids),'exact_request_id_match':int(ids==ref[3]),'exact_send_trace_match':int(times==ref[4])})
 pd.DataFrame(rows).to_csv(root/'pairing-validation.csv',index=False)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('results_root',nargs='?',default='results');a=ap.parse_args();root=Path(a.results_root).expanduser().resolve();rows=[];reqs=[];offs=[];tos=[]
 for rp in sorted(root.glob('*/requests.csv')):
  r,q,o,t=process(rp.parent);rows.extend(r)
  if q is not None and not q.empty:reqs.append(q)
  if o is not None and not o.empty:offs.append(o)
  if t is not None and not t.empty:tos.append(t)
 if not rows:raise SystemExit(f'No analyzable run directories under {root}')
 summary=pd.DataFrame(rows);summary.to_csv(root/'summary.csv',index=False);write_ci(summary,root/'summary-ci95.csv');allreq=pd.concat(reqs,ignore_index=True) if reqs else pd.DataFrame(columns=REQUEST_COLUMNS+['source_dir','native_freshness_ms','cache_size_packets','freshness_delivery_guard_ms','cache_hit','stale_rejected','valid_cache_hit']);alloff=pd.concat(offs,ignore_index=True) if offs else pd.DataFrame(columns=OFFERED_COLUMNS+['source_dir','native_freshness_ms','cache_size_packets','freshness_delivery_guard_ms']);allreq.to_csv(root/'all-requests.csv',index=False);alloff.to_csv(root/'all-offered-requests.csv',index=False);(pd.concat(tos,ignore_index=True) if tos else pd.DataFrame(columns=TIMEOUT_COLUMNS+['source_dir'])).to_csv(root/'all-timeouts.csv',index=False);e1refs(root,allreq);pairing(root,alloff);pd.DataFrame([{'run_directories':int(summary.source_dir.nunique()),'offered_requests':len(alloff),'satisfied_requests':len(allreq),'timeouts':sum(len(x) for x in tos),'missing_send_time_us':int(alloff.send_time_us.isna().sum()) if 'send_time_us' in alloff else 0,'missing_request_id':int(alloff.request_id.isna().sum()) if 'request_id' in alloff else 0,'status':'PASS' if len(alloff)>0 and alloff.send_time_us.notna().all() and alloff.request_id.notna().all() else 'FAIL'}]).to_csv(root/'analysis-data-quality.csv',index=False);print('Wrote',root/'summary.csv');print('All request samples:',len(allreq));print('All offered requests:',len(alloff))
if __name__=='__main__':main()
