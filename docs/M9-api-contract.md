# M9 API contract

All outer fields use snake_case. `scene_state` preserves existing camelCase live dynamic fields; nested legacy comparison/execution payloads retain original formats. All times are UTC ISO strings, snapshot `simulation_time` is elapsed scenario seconds. All reads are read-only; ingestion occurs through runtime writer and explicit backfill only.

- GET `/api/v1/incidents?type=FLOOD|PIPELINE_LEAK&status=...&start_time=ISO&end_time=ISO&keyword=...&limit=100&offset=0` → `{items: Incident[], total}`.
- Incident: `{id,incident_code,incident_type,source_event_id,scenario_id,title,area_id,status,started_at,detected_at,confirmed_at,response_started_at,stabilized_at,closed_at,peak_risk,peak_water_level,peak_detection_score,created_at,updated_at,source_status,close_result}`; statuses OPEN/DETECTED/CONFIRMED/RESPONDING/STABILIZING/CLOSED/ABORTED.
- GET `/incidents/{id}` → Incident fields plus `comparisons:[]`, `executions:[]`, `work_orders:[]`.
- GET `/incidents/{id}/timeline` → `{items: TimelineEvent[]}`. Event `{id,incident_id,event_time,simulation_time,event_type,event_level,title,description,source,source_id,payload,created_at}` sorted by simulation_time then event_time/id (unknown simulation times last).
- GET `/incidents/{id}/replay?from_time=0&to_time=3600&step_seconds=5` → `{metadata:{incident_id,incident_type,from_time,to_time,step_seconds,gaps,missing_fields,latency_ms,snapshot_count,source_snapshot_count},timeline,snapshots,key_moments}`. from/to are elapsed seconds, step >0. Up to 2000 points; no generated points/interpolation on server. `gaps` entries `{from_time,to_time,duration_seconds,message}`.
- Snapshot `{id,timestamp,simulation_time,risk_score,risk_level,scene_state,source_snapshot_id,missing_fields}`; scene_state dynamic subset `{weather,environment,devices,pipelines,valves,flood,leak,emergency}`. Unknown groups omitted; old records MUST NOT be populated using latest event state. New full snapshots include `recordedAt`, `simulationTime` and all groups. Key moment uses timeline shape plus `source:'snapshot_rule'` for PEAK_RISK/PEAK_WATER.
- GET `/incidents/{id}/metrics` → `{incident_id,incident_type,snapshot_count,response_metrics,peak_metrics,response_effect,prediction_review,missing_fields}`. response_metrics keys `time_to_detect_seconds,time_to_confirm_seconds,time_to_response_seconds,time_to_stabilize_seconds,total_incident_duration_seconds`, wall time definitions. peak_metrics keys `peak_risk,peak_water_level,max_water_area,max_rainfall,min_p03_efficiency,min_pressure,max_flow,max_detection_score,max_affected_buildings`; unavailable null. response_effect `{before,after,environment_note}` snapshots near first actual execution / latest observation. prediction_review `{label:'本事件预测误差',samples,water_mae,risk_mae,physical_water_mae,physical_risk_mae,items,message}` only evaluated records with actuals; no ML for leak.
- POST `/incidents/{id}/close` `{result:string,operator:'demo-user',confirmed:true}` → Incident detail. Calls runtime service; only STABILIZING, repeat CLOSED idempotent. Closed leaves saved devices/valves and history intact.
- GET `/incidents/{id}/review` → `{report: Report|null}`.
- POST `/incidents/{id}/review/generate` → Report `{id,incident_id,generated_at,summary,cause_analysis,response_analysis,prediction_analysis,impact_analysis,lessons,status,metrics}`. Each analysis is a string, lessons string array, metrics immutable generation-time factual object.
- GET `/work-orders?incident_id=...&status=...` → `{items,total}`; GET `/work-orders/{id}` → work order.
- POST `/work-orders` `{incident_id,title,description:'',category:'EMERGENCY',priority:'HIGH',assignee:null,created_by:'demo-user'}` → work order. Unique incident/category, duplicate returns existing main order.
- PATCH `/work-orders/{id}` `{status:'ASSIGNED'|'IN_PROGRESS'|'COMPLETED'|'CANCELLED',assignee?:string,result?:string}` → work order; strict PENDING→ASSIGNED→IN_PROGRESS→COMPLETED; pending/assigned/in-progress can cancel; ASSIGNED requires assignee, COMPLETED requires result. Each work order includes code and timestamps.

Python integration:
`IncidentService(session_factory)`:
- `sync_sources(session)` aggregates legacy sources, returns counts, caller commits.
- `capture(state)` synchronous transaction storing dynamic snapshot and transition timeline, returns incident id or None.
- `close_record(session,id,body,timestamp=None,simulation_time=None)` persists valid close; caller commits.
- `abort_record(session,id,reason,timestamp=None,simulation_time=None)` persists ABORTED except already CLOSED; caller commits.
- `get_incident(session,id)`, `detail(session,id)`, `timeline(session,id)`, `metrics(session,id)`, `generate_report(session,id)`, `create_work_order(session,body)`, `update_work_order(session,id,body)`.
`IncidentReplayService().replay(session,id,from_time=None,to_time=None,step_seconds=5)` only reads database. `snapshots(session,incident)` returns factual merged DTO points prior to downsampling.

Semantic timeline identity: a leakage isolation closes each valve once under `source_id=isolation:{execution_id}:{valve_id}` across source adapters. Later manual reopen/reclose produces a new transition event. RISK_STABILIZED prefers original M7/M8 events; fallback is used only if no stable record exists. `IncidentService.reconcile_derived_events(session)` is an explicit maintenance step after sync_sources, not an API read side effect; it merges proven M9 aliases with original evidence retained in payload.merged_source_records. CLI: `scripts/backfill-incidents.py --reconcile-derived`.
