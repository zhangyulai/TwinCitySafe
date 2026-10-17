"""Idempotent archive writer and data-based review; never re-runs simulation."""
from copy import deepcopy
from datetime import datetime, UTC
from hashlib import sha256
import json
from uuid import uuid4, uuid5, NAMESPACE_URL
from sqlalchemy import select, func
from fastapi import HTTPException
from app.models.incident import Incident, IncidentSnapshot, IncidentTimelineEvent, WorkOrder, ReviewReport
from app.models.flood import FloodScenarioRecord, FloodSnapshot
from app.models.leak import PipelineLeakEvent, PipelineLeakSnapshot, PipelineLeakIsolation
from app.models.emergency import EmergencyComparison, EmergencyExecution
from app.models.risk_prediction import RiskPredictionRecord
from app.schemas.incident import CreateWorkOrder, UpdateWorkOrder, CloseIncident
from app.services.incident_replay_service import IncidentReplayService, iso, row_dict, risk_level

TERMINAL = {'CLOSED', 'ABORTED'}


def date(value):
    if not value: return None
    if isinstance(value, str): value = datetime.fromisoformat(value.replace('Z','+00:00'))
    return value.replace(tzinfo=value.tzinfo or UTC)


def identifier(*parts):
    return str(uuid5(NAMESPACE_URL, 'TwinCitySafe:incident:' + ':'.join(str(part) for part in parts)))


def elapsed_difference(later, earlier):
    return max(0., (date(later)-date(earlier)).total_seconds()) if later and earlier else None


def body_dict(body):
    return body.model_dump() if hasattr(body, 'model_dump') else dict(body)


class IncidentService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.replays = IncidentReplayService()

    @staticmethod
    def get_incident(session, incident_id):
        return IncidentReplayService.require(session, incident_id)

    @staticmethod
    def ensure(session, kind, source_id, scenario_id, started_at=None, area_id=None):
        id = identifier(kind, source_id)
        row = session.get(Incident, id)
        if row is None:
            now = datetime.now(UTC)
            row = Incident(id=id, incident_code=f'INC-{(date(started_at) or now):%Y%m%d}-{id.replace("-", "").upper()}',
                incident_type=kind, source_event_id=source_id, scenario_id=scenario_id,
                title='B2 地下停车场暴雨内涝' if kind == 'FLOOD' else '地下供水管网泄漏',
                area_id=area_id or ('B2' if kind == 'FLOOD' else 'WATER_NETWORK'), status='OPEN',
                started_at=date(started_at), created_at=now, updated_at=now)
            session.add(row); session.flush()
        elif row.started_at is None and started_at: row.started_at = date(started_at)
        return row

    @staticmethod
    def write_event(session, incident, event_type, source, source_id, timestamp, simulation_time,
                    title, payload=None, level='info', description=''):
        timestamp = date(timestamp)
        if timestamp is None: return None  # A missing timestamp cannot be reconstructed honestly.
        event_id = identifier(incident.id, event_type, source_id)
        cached = session.info.setdefault('m9_event_ids', set())
        existing=next((row for row in session.new if isinstance(row,IncidentTimelineEvent) and row.id==event_id),None)
        if existing is None:existing=session.get(IncidentTimelineEvent,event_id)
        if existing is not None:
            # Supplement only an exact original observation, never infer a missing time.
            if existing.simulation_time is None and simulation_time is not None:
                existing.simulation_time=simulation_time
                existing.payload={**(existing.payload or {}),'timing_evidence':{
                    'source':source,'source_id':str(source_id),'event_time':iso(timestamp)}}
            cached.add(event_id);return existing
        row = IncidentTimelineEvent(id=event_id, incident_id=incident.id, event_time=timestamp,
            simulation_time=simulation_time, event_type=event_type, event_level=level, title=title,
            description=description or title, source=source, source_id=str(source_id), payload=deepcopy(payload or {}))
        session.add(row); cached.add(event_id)
        target = {'ANOMALY_DETECTED':'detected_at','LEAK_SUSPECTED':'detected_at', 'LEAK_CONFIRMED':'confirmed_at',
            'ANOMALY_CONFIRMED':'confirmed_at','EXECUTION_STARTED':'response_started_at','RISK_STABILIZED':'stabilized_at'}.get(event_type)
        if target:
            old = getattr(incident,target)
            if old is None or timestamp < date(old): setattr(incident,target,timestamp)
        return row

    def _source_flood(self, session, source):
        existed = session.get(Incident,identifier('FLOOD',source.id)) is not None
        incident = self.ensure(session,'FLOOD',source.id,source.id,source.started_at,'B2')
        incident.source_status = source.status
        self.write_event(session,incident,'SCENARIO_STARTED','flood_scenario',source.id,source.started_at,0,
                         '暴雨内涝场景启动',{'scenario':source.scenario,'focus_target_id':'B2'})
        rows = list(session.scalars(select(FloodSnapshot).where(FloodSnapshot.scenario_id==source.id).order_by(FloodSnapshot.simulation_time)))
        previous = None
        for row in rows:
            level = risk_level(row.risk_score)
            if previous is None or level != risk_level(previous.risk_score):
                self.write_event(session,incident,'RISK_LEVEL_CHANGED','flood_snapshot',f'risk:{row.simulation_time:g}:{level}',row.timestamp,row.simulation_time,
                    f'内涝风险进入 {level}',{'risk_score':row.risk_score,'risk_level':level,'focus_target_id':'B2'},level='warning' if row.risk_score>=40 else 'info')
            if row.risk_score >= 20:
                self.write_event(session,incident,'ANOMALY_DETECTED','flood_snapshot','first-flood-detection',row.timestamp,row.simulation_time,'内涝异常达到监测阈值',{'risk_score':row.risk_score})
            if row.risk_score >= 40:
                self.write_event(session,incident,'ANOMALY_CONFIRMED','flood_snapshot','first-flood-confirmation',row.timestamp,row.simulation_time,'内涝规则风险达到确认阈值',{'risk_score':row.risk_score})
            previous = row
        if rows:
            incident.peak_risk=max(row.risk_score for row in rows)
            incident.peak_water_level=max(row.water_level for row in rows)
        if incident.status not in TERMINAL:
            reset = bool(source.alarm and source.alarm.get('status') == 'ended_by_reset')
            if reset or (not existed and source.status in ('stopped','interrupted','reset','aborted')):
                self.abort_record(session,incident.id,'旧场景已重置或停止，未记录正式关闭',source.updated_at,
                                  source.elapsed_simulation_seconds)
            else: incident.status='CONFIRMED' if incident.confirmed_at else 'DETECTED' if incident.detected_at else 'OPEN'
        return incident

    def _leak_events(self, session, incident, state):
        for event in state.get('events',[]):
            stage=event.get('stage',''); message=event.get('message','管网状态变化')
            if event.get('sequence')==1: kind='SCENARIO_STARTED'
            elif stage=='STABILIZING': kind='RISK_STABILIZED'
            elif stage=='ISOLATING':
                execution=state.get('execution') or {}
                if execution.get('id') and execution.get('valves'):
                    for valve in execution['valves']:
                        self.write_event(session,incident,'VALVE_CLOSED','leak_event',
                            f'isolation:{execution["id"]}:{valve}',event.get('timestamp'),event.get('simulationTime'),
                            f'{valve} 已关闭',{'focus_target_id':valve,'execution_id':execution['id'],
                                'source_event_id':f'{incident.source_event_id}:{event.get("sequence")}',
                                'stage':stage,'message':message})
                    continue
                kind='ISOLATION_STAGE_CHANGED'
            elif stage=='SUSPECTED': kind='LEAK_SUSPECTED'
            elif stage in ('CONFIRMED','HIGH'): kind='LEAK_CONFIRMED'
            else: kind='RISK_LEVEL_CHANGED'
            self.write_event(session,incident,kind,'leak_event',f'{incident.source_event_id}:{event.get("sequence")}',
                event.get('timestamp'),event.get('simulationTime'),message,
                {'stage':stage,'message':message},'warning' if stage in ('HIGH','CONFIRMED') else 'info')

    def _source_leak(self, session, source):
        state=source.state_json or {}
        first=session.scalar(select(PipelineLeakSnapshot).where(PipelineLeakSnapshot.scenario_id==source.scenario_id).order_by(PipelineLeakSnapshot.simulation_time).limit(1))
        starts=[e.get('timestamp') for e in state.get('events',[]) if e.get('sequence')==1 and e.get('timestamp')]
        # If original start was not preserved, do not relabel the first sampled time as event start.
        started=starts[0] if starts else None
        incident=self.ensure(session,'PIPELINE_LEAK',source.id,source.scenario_id,started,source.pipeline_id)
        incident.source_status=source.status
        if source.pipeline_id:incident.area_id=source.pipeline_id
        if source.detected_at and incident.detected_at is None:incident.detected_at=source.detected_at
        if source.confirmed_at and incident.confirmed_at is None:incident.confirmed_at=source.confirmed_at
        self._leak_events(session,incident,state)
        rows=list(session.scalars(select(PipelineLeakSnapshot).where(PipelineLeakSnapshot.scenario_id==source.scenario_id).order_by(PipelineLeakSnapshot.simulation_time)))
        if rows:
            incident.peak_risk=max(r.risk_score for r in rows)
            incident.peak_detection_score=max(r.detection_score for r in rows)
        for field,kind,title in [('detected_at','LEAK_SUSPECTED','管网泄漏疑似异常'),('confirmed_at','LEAK_CONFIRMED','管网泄漏确认')]:
            value=getattr(source,field)
            if value and not any(e['event_type']==kind for e in self._pending_and_saved_events(session,incident.id)):
                self.write_event(session,incident,kind,'leak_event',source.id+':'+field,value,None,title)
        if incident.status not in TERMINAL:
            if source.status.lower() in ('reset','interrupted','aborted'):
                self.abort_record(session,incident.id,'源泄漏场景重置或重启中断',first.timestamp if first else datetime.now(UTC),None)
            else:
                incident.status='STABILIZING' if source.status=='STABILIZING' or state.get('currentStage')=='STABILIZING' else 'RESPONDING' if state.get('execution') else 'CONFIRMED' if incident.confirmed_at else 'DETECTED' if incident.detected_at else 'OPEN'
        return incident

    @staticmethod
    def _pending_and_saved_events(session, incident_id):
        result=[{'event_type':r.event_type} for r in session.scalars(select(IncidentTimelineEvent).where(IncidentTimelineEvent.incident_id==incident_id))]
        result.extend({'event_type':r.event_type} for r in session.new if isinstance(r,IncidentTimelineEvent) and r.incident_id==incident_id)
        return result

    def _emergency_history(self, session, incident, update_status=True):
        if incident.incident_type=='FLOOD':
            comparisons=list(session.scalars(select(EmergencyComparison).where(EmergencyComparison.scenario_id==incident.scenario_id)))
            for row in comparisons:
                data=row.results_json
                self.write_event(session,incident,'PLAN_COMPARED','emergency_comparison',row.id,row.compared_at,data.get('baseline_simulation_time'),
                    '四分支应急方案比较',{'comparison_id':row.id,'baseline_state_hash':row.baseline_state_hash})
            for row in session.scalars(select(EmergencyExecution).where(EmergencyExecution.scenario_id==incident.scenario_id).order_by(EmergencyExecution.started_at)):
                self._execution_events(session,incident,row.state_json,row.id,row.started_at)
                if update_status and incident.status not in TERMINAL:
                    incident.status='STABILIZING' if row.state_json.get('phase')=='STABILIZING' else 'RESPONDING'
        else:
            for row in session.scalars(select(PipelineLeakIsolation).where(PipelineLeakIsolation.scenario_id==incident.scenario_id)):
                data=row.comparison_json
                self.write_event(session,incident,'PLAN_COMPARED','leak_isolation',row.id,row.created_at,data.get('simulationTime'),
                    '管网隔离方案比较',{'comparison_id':row.id,'state_hash':row.state_hash,'focus_target_id':data.get('pipelineId')})
                execution=row.execution_json
                if execution:
                    stamp=execution.get('timestamp')
                    # Original M8 executions did not store simulation time: null is truthful.
                    at=execution.get('simulation_time',execution.get('simulationTime'))
                    for kind,title in [('PLAN_SELECTED','人工确认隔离方案'),('EXECUTION_STARTED','软件隔离开始')]:
                        self.write_event(session,incident,kind,'leak_isolation',row.id,stamp,at,title,execution)
                    for valve in execution.get('valves',[]):
                        self.write_event(session,incident,'VALVE_CLOSED','leak_isolation',f'isolation:{execution.get("id",row.id)}:{valve}',stamp,at,f'{valve} 已关闭',{'focus_target_id':valve,'execution_id':execution.get('id')})
                    if update_status and incident.status not in TERMINAL and incident.status!='STABILIZING':incident.status='RESPONDING'
        if incident.response_started_at:
            self.create_work_order(session,CreateWorkOrder(incident_id=incident.id,title='B2 地下停车场内涝应急处置' if incident.incident_type=='FLOOD' else f'{incident.area_id} 管网泄漏隔离处置'), automatic=True)

    def _execution_events(self, session, incident, data, id, started):
        at=data.get('simulation_started_at')
        payload={'execution_id':id,'plan_code':data.get('plan_code'),'comparison_id':data.get('comparison_id')}
        for kind,title in [('PLAN_SELECTED','人工选择 '+str(data.get('plan_code','应急方案'))),('EXECUTION_STARTED','应急方案执行开始')]:
            self.write_event(session,incident,kind,'emergency_execution',id,started,at,title,payload)
        steps={step.get('index'):step for step in data.get('steps',[])}
        for event in data.get('events',[]):
            step=steps.get(event.get('step')); status=event.get('status'); message=event.get('message','应急执行状态变化')
            if step:
                kind='ACTION_COMPLETED' if status=='completed' else 'ACTION_STARTED' if status=='executing' else 'ACTION_UPDATED'
                focus=step.get('action',{}).get('target_id')
            else:
                kind='RISK_STABILIZED' if '风险开始回落' in message or str(status).upper()=='STABILIZING' else 'EXECUTION_UPDATED'
                focus=None
            self.write_event(session,incident,kind,'emergency_execution',f'{id}:{event.get("sequence")}',event.get('timestamp'),event.get('simulation_time'),message,
                {**payload,'step':event.get('step'),'focus_target_id':focus,'status':status})
            if step and status in ('executing','completed') and step.get('action',{}).get('action_type')=='CLOSE_ENTRANCE':
                self.write_event(session,incident,'ENTRANCE_CLOSED','emergency_execution',f'{id}:entrance:{step.get("index")}',event.get('timestamp'),event.get('simulation_time'),'B2 入口封控',{'focus_target_id':'B2-ENTRANCE'})

    def sync_sources(self, session):
        """Explicit backfill/periodic ingestion. Safe to repeat; caller commits transaction."""
        before=session.scalar(select(func.count()).select_from(Incident)) or 0
        incidents=[]
        for row in session.scalars(select(FloodScenarioRecord)):incidents.append(self._source_flood(session,row))
        for row in session.scalars(select(PipelineLeakEvent)):incidents.append(self._source_leak(session,row))
        for incident in incidents:
            self._emergency_history(session,incident)
            if incident.incident_type=='FLOOD':
                for prediction in session.scalars(select(RiskPredictionRecord).where(RiskPredictionRecord.scenario_id==incident.scenario_id)):
                    self.write_event(session,incident,'FORECAST_GENERATED','risk_prediction',prediction.id,prediction.generated_at,prediction.origin_time,
                        f'+{prediction.horizon_minutes} 分钟预测已保存',{'prediction_id':prediction.id,'horizon_minutes':prediction.horizon_minutes,'model_version':prediction.model_version})
        session.flush()
        # Index summaries use all saved observations, including M9 transition captures.
        for incident in incidents:
            points=self.replays.snapshots(session,incident)
            risks=[p['risk_score'] for p in points if p.get('risk_score') is not None]
            waters=[p['scene_state'].get('flood',{}).get('waterLevel') for p in points if incident.incident_type=='FLOOD']
            scores=[p['scene_state'].get('leak',{}).get('detectionScore') for p in points if incident.incident_type=='PIPELINE_LEAK']
            incident.peak_risk=max(risks) if risks else None
            incident.peak_water_level=max((v for v in waters if v is not None),default=None)
            incident.peak_detection_score=max((v for v in scores if v is not None),default=None)
        session.flush()
        after=session.scalar(select(func.count()).select_from(Incident)) or 0
        return {'incidents_created':after-before,'incidents_total':after,
            'timeline_total':session.scalar(select(func.count()).select_from(IncidentTimelineEvent)) or 0}

    def capture(self, state):
        data=state.model_dump(mode='json',by_alias=True) if hasattr(state,'model_dump') else deepcopy(state)
        f=data.get('flood') or {}; leak=data.get('leak') or {}
        kind='FLOOD' if f.get('scenarioId') else 'PIPELINE_LEAK' if leak.get('scenarioId') else None
        if kind is None:return None
        current=f if kind=='FLOOD' else leak
        source_id=current.get('eventId') if kind=='PIPELINE_LEAK' else current['scenarioId']
        if not source_id:return None
        at=float(current.get('elapsedSimulationSeconds',0));stamp=date(data.get('timestamp')) or datetime.now(UTC)
        with self.session_factory() as session:
            started=current.get('startedAt')
            if kind=='PIPELINE_LEAK':
                started=next((e.get('timestamp') for e in current.get('events',[]) if e.get('sequence')==1),None)
            incident=self.ensure(session,kind,source_id,current['scenarioId'],started,'B2' if kind=='FLOOD' else None)
            if incident.status in TERMINAL:return incident.id
            incident.updated_at=stamp;incident.source_status=current.get('status')
            if kind=='PIPELINE_LEAK':
                suspects=current.get('suspectedSegments') or []
                if suspects:incident.area_id=suspects[0].get('pipeline_id')
            previous=session.scalar(select(IncidentSnapshot).where(IncidentSnapshot.incident_id==incident.id).order_by(IncidentSnapshot.simulation_time.desc(),IncidentSnapshot.timestamp.desc()).limit(1))
            scene={key:deepcopy(data.get(key)) for key in ('weather','environment','devices','pipelines','valves','flood','leak','emergency')}
            for device in scene.get('devices') or []:device.pop('name',None)
            # Dynamic render state only; avoid repeating event logs/analyses in every sample.
            for branch in ('flood','leak'):
                if scene.get(branch):
                    scene[branch].pop('events',None)
                    scene[branch].pop('targetPipelineId',None)
            if scene.get('emergency'):scene['emergency'].pop('events',None)
            scene['simulationTime']=data.get('simulationTime')
            scene['running']=data.get('running')
            scene['speed']=data.get('speed')
            state_hash=sha256(json.dumps(scene,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            scene['recordedAt']=iso(stamp)
            previous_dynamic={k:v for k,v in previous.scene_state.items() if k!='recordedAt'} if previous else None
            current_dynamic={k:v for k,v in scene.items() if k!='recordedAt'}
            if previous and previous.simulation_time==at and previous_dynamic==current_dynamic:
                duplicate=previous.id
            else:
                duplicate=session.scalar(select(IncidentSnapshot.id).where(IncidentSnapshot.incident_id==incident.id,IncidentSnapshot.simulation_time==at,IncidentSnapshot.state_hash==state_hash))
                if duplicate is not None and previous is not None:
                    # A→B→A at one paused clock is a real second transition, not a retry of A.
                    state_hash=sha256((state_hash+':after:'+previous.id).encode()).hexdigest()
                    duplicate=session.scalar(select(IncidentSnapshot.id).where(IncidentSnapshot.incident_id==incident.id,IncidentSnapshot.simulation_time==at,IncidentSnapshot.state_hash==state_hash))
            if duplicate is None:
                session.add(IncidentSnapshot(id=str(uuid4()),incident_id=incident.id,timestamp=stamp,simulation_time=at,
                    risk_score=current.get('riskScore',0),risk_level=current.get('riskLevel',risk_level(current.get('riskScore',0))),
                    scene_state=scene,state_hash=state_hash,missing_fields=[]))
            if previous is None:
                self.write_event(session,incident,'SCENARIO_STARTED','live_capture',source_id if kind=='FLOOD' else source_id+':1',started or stamp,0 if started else at,'软件事故场景开始记录',{'focus_target_id':'B2' if kind=='FLOOD' else None})
            old=(previous.scene_state.get('flood' if kind=='FLOOD' else 'leak') or {}) if previous else {}
            if current.get('riskLevel')!=old.get('riskLevel'):
                self.write_event(session,incident,'RISK_LEVEL_CHANGED','live_capture',f'risk:{at:g}:{current.get("riskLevel")}',stamp,at,
                    f'风险进入 {current.get("riskLevel")}',{'risk_score':current.get('riskScore'),'risk_level':current.get('riskLevel')})
            if kind=='FLOOD':
                for threshold,event_type,title in [(20,'ANOMALY_DETECTED','内涝异常达到监测阈值'),(40,'ANOMALY_CONFIRMED','内涝风险达到确认阈值')]:
                    if current.get('riskScore',0)>=threshold:self.write_event(session,incident,event_type,'live_capture','first-flood-detection' if threshold==20 else 'first-flood-confirmation',stamp,at,title,{'risk_score':current.get('riskScore')})
                emergency=data.get('emergency')
                if emergency:
                    self._execution_events(session,incident,emergency,emergency['id'],emergency['started_at'])
                    incident.status='STABILIZING' if emergency.get('phase')=='STABILIZING' else 'RESPONDING'
                else:incident.status='CONFIRMED' if incident.confirmed_at else 'DETECTED' if incident.detected_at else 'OPEN'
                incident.peak_water_level=max(incident.peak_water_level or 0,current.get('waterLevel',0))
            else:
                self._leak_events(session,incident,current)
                if current.get('detectedAt') and incident.detected_at is None:incident.detected_at=date(current['detectedAt'])
                if current.get('confirmedAt') and incident.confirmed_at is None:incident.confirmed_at=date(current['confirmedAt'])
                stage=current.get('currentStage')
                incident.status='STABILIZING' if stage=='STABILIZING' else 'RESPONDING' if current.get('execution') else 'CONFIRMED' if incident.confirmed_at else 'DETECTED' if incident.detected_at else 'OPEN'
                incident.peak_detection_score=max(incident.peak_detection_score or 0,current.get('detectionScore',0))
                execution=current.get('execution')
                if execution:
                    self.write_event(session,incident,'EXECUTION_STARTED','leak_isolation',execution.get('comparisonId',execution['id']),execution.get('timestamp'),at,'软件隔离开始',execution)
                    self.write_event(session,incident,'PLAN_SELECTED','leak_isolation',execution.get('comparisonId',execution['id']),execution.get('timestamp'),at,'人工确认隔离方案',execution)
            old_devices={d['id']:d for d in previous.scene_state.get('devices',[])} if previous else {}
            for device in data.get('devices',[]):
                old_device=old_devices.get(device['id'],{})
                if device.get('fault') not in (None,'normal') and device.get('fault')!=old_device.get('fault'):
                    self.write_event(session,incident,'DEVICE_FAULT','live_capture',f'{device["id"]}:{at}:{device.get("fault")}',stamp,at,f'{device["id"]} 故障状态',{'focus_target_id':device['id'],'fault':device.get('fault')},'warning')
                elif device.get('status')=='warning' and old_device.get('status')!='warning':
                    self.write_event(session,incident,'DEVICE_WARNING','live_capture',f'{device["id"]}:{at}',stamp,at,f'{device["id"]} 设备告警',{'focus_target_id':device['id']},'warning')
            old_valves={v['id']:v for v in previous.scene_state.get('valves',[])} if previous else {}
            for valve in data.get('valves',[]):
                if valve.get('status')=='closed' and old_valves.get(valve['id'],{}).get('status')=='open':
                    execution=current.get('execution') if kind=='PIPELINE_LEAK' else None
                    previous_execution=((previous.scene_state.get('leak') or {}).get('execution') or {}) if previous else {}
                    applied_now=bool(execution and execution.get('id')!=previous_execution.get('id') and valve['id'] in execution.get('valves',[]))
                    source_id=(f'isolation:{execution["id"]}:{valve["id"]}' if applied_now else
                        f'valve:{valve["id"]}:{data.get("sessionId")}:{data.get("revision")}:{at:g}')
                    self.write_event(session,incident,'VALVE_CLOSED','live_capture',source_id,stamp,at,
                        f'{valve["id"]} 已关闭',{'focus_target_id':valve['id'],
                            'execution_id':execution.get('id') if applied_now else None})
            incident.peak_risk=max(incident.peak_risk or 0,current.get('riskScore',0))

            if incident.response_started_at:self.create_work_order(session,CreateWorkOrder(incident_id=incident.id,title=incident.title+'应急处置'),automatic=True)
            self._emergency_history(session,incident,update_status=False)
            if incident.status=='STABILIZING' and not any(event['event_type']=='RISK_STABILIZED' for event in self._pending_and_saved_events(session,incident.id)):
                self.write_event(session,incident,'RISK_STABILIZED','live_capture','first-stable',stamp,at,'风险进入稳定阶段，事件尚未关闭')
            if kind=='FLOOD':
                for prediction in session.scalars(select(RiskPredictionRecord).where(RiskPredictionRecord.scenario_id==incident.scenario_id)):
                    self.write_event(session,incident,'FORECAST_GENERATED','risk_prediction',prediction.id,prediction.generated_at,prediction.origin_time,
                        f'+{prediction.horizon_minutes} 分钟预测已保存',{'prediction_id':prediction.id,'horizon_minutes':prediction.horizon_minutes})
            session.commit()
            return incident.id

    def timeline(self, session, incident_id):
        return {'items':self.replays.timeline(session,incident_id)}

    def detail(self, session, incident_id):
        incident=self.get_incident(session,incident_id)
        result=row_dict(incident)
        if incident.incident_type=='FLOOD':
            result['comparisons']=[{**row_dict(r),'results':r.results_json} for r in session.scalars(select(EmergencyComparison).where(EmergencyComparison.scenario_id==incident.scenario_id).order_by(EmergencyComparison.compared_at))]
            result['executions']=[{**row_dict(r),'execution':r.state_json} for r in session.scalars(select(EmergencyExecution).where(EmergencyExecution.scenario_id==incident.scenario_id).order_by(EmergencyExecution.started_at))]
        else:
            rows=list(session.scalars(select(PipelineLeakIsolation).where(PipelineLeakIsolation.scenario_id==incident.scenario_id).order_by(PipelineLeakIsolation.created_at)))
            result['comparisons']=[{'id':r.id,'compared_at':iso(r.created_at),'state_hash':r.state_hash,'results':r.comparison_json} for r in rows]
            result['executions']=[{'id':r.execution_json.get('id',r.id),'comparison_id':r.id,'execution':r.execution_json} for r in rows if r.execution_json]
        result['work_orders']=[row_dict(r) for r in session.scalars(select(WorkOrder).where(WorkOrder.incident_id==incident_id).order_by(WorkOrder.created_at))]
        return result

    @staticmethod
    def _point_metrics(point):
        if point is None:return None
        scene=point['scene_state'];f=scene.get('flood') or {};leak=scene.get('leak') or {}
        return {'timestamp':point['timestamp'],'simulation_time':point['simulation_time'],'risk_score':point['risk_score'],
            'water_level':f.get('waterLevel'),'rainfall':f.get('rainfall'),'pump_capacity':f.get('effectivePumpCapacity'),
            'leak_flow':leak.get('estimatedLeakFlow'),'pressure':leak.get('downstreamPressure'),'flow':leak.get('pipelineFlow'),
            'service_status':leak.get('serviceStatus'),'interrupted_buildings':leak.get('interruptedBuildings'),
            'affected_buildings':leak.get('affectedBuildings'),'estimated_service_loss':leak.get('estimatedServiceLoss')}

    def metrics(self, session, incident_id):
        incident=self.get_incident(session,incident_id)
        points=self.replays.snapshots(session,incident)
        def values(branch,key):
            if branch=='flood' and incident.incident_type!='FLOOD' or branch=='leak' and incident.incident_type!='PIPELINE_LEAK':return []
            return [(p.get('scene_state',{}).get(branch) or {}).get(key) for p in points if (p.get('scene_state',{}).get(branch) or {}).get(key) is not None]
        def maximum(items):return max(items) if items else None
        def minimum(items):return min(items) if items else None
        p03=[d.get('efficiency') for p in points for d in (p['scene_state'].get('devices') or []) if d.get('id')=='P03' and d.get('efficiency') is not None]
        affected=[len(v) for v in values('leak','affectedBuildings')]+values('leak','affectedBuildingCount')
        peaks={'peak_risk':maximum([p['risk_score'] for p in points if p['risk_score'] is not None]),
            'peak_water_level':maximum(values('flood','waterLevel')),'max_water_area':maximum(values('flood','waterArea')),
            'max_rainfall':maximum(values('flood','rainfall')),'min_p03_efficiency':minimum(p03),
            'min_pressure':minimum(values('leak','downstreamPressure')),'max_flow':maximum(values('leak','pipelineFlow')),
            'max_leak_flow':maximum(values('leak','estimatedLeakFlow')),'max_detection_score':maximum(values('leak','detectionScore')),'max_affected_buildings':maximum(affected)}
        last_time=incident.closed_at or (points[-1]['timestamp'] if points else None)
        response={'time_to_detect_seconds':elapsed_difference(incident.detected_at,incident.started_at),
            'time_to_confirm_seconds':elapsed_difference(incident.confirmed_at,incident.started_at),
            'time_to_response_seconds':elapsed_difference(incident.response_started_at,incident.detected_at),
            'time_to_stabilize_seconds':elapsed_difference(incident.stabilized_at,incident.started_at),
            'total_incident_duration_seconds':elapsed_difference(last_time,incident.started_at),
            'basis':'原始 UTC 墙钟时间；响应时长=首次执行时间-检测时间，持续时长截至关闭或最后真实采样。'}
        before=None
        if incident.response_started_at:
            eligible=[p for p in points if date(p['timestamp'])<=date(incident.response_started_at)]
            before=eligible[-1] if eligible else None
        after=points[-1] if points else None
        predictions=[]
        if incident.incident_type=='FLOOD':
            for row in session.scalars(select(RiskPredictionRecord).where(RiskPredictionRecord.scenario_id==incident.scenario_id,
                    RiskPredictionRecord.evaluation_status=='evaluated').order_by(RiskPredictionRecord.origin_time,RiskPredictionRecord.horizon_minutes)):
                if row.actual_water is None or row.actual_risk is None:continue
                item=row_dict(row)
                # Recompute from saved actual and prediction, rather than trusting a precomputed error column.
                item['water_error']=row.actual_water-row.predicted_water if row.predicted_water is not None else None
                item['risk_error']=row.actual_risk-row.predicted_risk if row.predicted_risk is not None else None
                item['physical_water_error']=row.actual_water-row.physical_water
                item['physical_risk_error']=row.actual_risk-row.physical_risk
                predictions.append(item)
        def mae(key):
            numbers=[abs(item[key]) for item in predictions if item.get(key) is not None]
            return sum(numbers)/len(numbers) if numbers else None
        prediction_review={'label':'本事件预测误差','samples':len(predictions),'water_mae':mae('water_error'),
            'risk_mae':mae('risk_error'),'physical_water_mae':mae('physical_water_error'),'physical_risk_mae':mae('physical_risk_error'),
            'items':predictions,'message':'仅统计本事件已到期且保存了实际观测的预测；含后续人工干预影响，不代表 M6 独立测试集指标。' if predictions else '样本不足：没有保存完整实际观测的到期预测。' if incident.incident_type=='FLOOD' else '当前 ML 预测模型仅适用于内涝场景。'}
        return {'incident_id':incident_id,'incident_type':incident.incident_type,'snapshot_count':len(points),
            'response_metrics':response,'peak_metrics':peaks,
            'response_effect':{'before':self._point_metrics(before),'after':self._point_metrics(after),
                'environment_note':'降雨计划与应急排水共同影响风险和水位，不能将全部变化归因于方案。' if incident.incident_type=='FLOOD' else '泄漏受控不等于供水恢复；关闭档案不改变阀门和受影响建筑的实际状态。'},
            'prediction_review':prediction_review,'missing_fields':sorted({v for p in points for v in p['missing_fields']})}

    def create_work_order(self, session, body, automatic=False):
        data=body_dict(body)
        incident=self.get_incident(session,data['incident_id'])
        existing=session.scalar(select(WorkOrder).where(WorkOrder.incident_id==incident.id,WorkOrder.category==data.get('category','EMERGENCY')))
        if existing:return row_dict(existing)
        # Autoflush may be disabled by the production session; account for an order created earlier in this transaction.
        pending=next((r for r in session.new if isinstance(r,WorkOrder) and r.incident_id==incident.id and r.category==data.get('category','EMERGENCY')),None)
        if pending:return row_dict(pending)
        if incident.status=='CLOSED' and automatic:return None
        now=datetime.now(UTC);id=str(uuid4())
        row=WorkOrder(id=id,work_order_code=f'WO-{now:%Y%m%d}-{id.replace("-", "").upper()}',incident_id=incident.id,
            title=data['title'],description=data.get('description',''),category=data.get('category','EMERGENCY'),priority=data.get('priority','HIGH'),
            status='PENDING',assignee=data.get('assignee'),created_at=now,created_by=data.get('created_by','demo-user'))
        session.add(row)
        self.write_event(session,incident,'WORK_ORDER_CREATED','work_order',id,now,None,'处置工单已创建',{'work_order_id':id,'automatic':automatic})
        session.flush()
        return row_dict(row)

    def update_work_order(self, session, order_id, body):
        row=session.get(WorkOrder,order_id)
        if row is None:raise HTTPException(404,'工单不存在')
        data=body_dict(body);status=data['status']
        if status==row.status:return row_dict(row)
        transitions={'PENDING':{'ASSIGNED','CANCELLED'},'ASSIGNED':{'IN_PROGRESS','CANCELLED'},'IN_PROGRESS':{'COMPLETED','CANCELLED'},'COMPLETED':set(),'CANCELLED':set()}
        if status not in transitions[row.status]:raise HTTPException(409,f'不允许 {row.status} → {status}')
        assignee=(data.get('assignee') or row.assignee or '').strip()
        if status=='ASSIGNED' and not assignee:raise HTTPException(422,'接受工单需要填写负责班组')
        result=(data.get('result') or '').strip()
        if status=='COMPLETED' and not result:raise HTTPException(422,'完成工单需要填写处理结果')
        now=datetime.now(UTC);row.status=status
        if assignee:row.assignee=assignee
        if status=='ASSIGNED':row.accepted_at=now
        if status=='COMPLETED':row.completed_at=now;row.result=result
        if status=='CANCELLED' and result:row.result=result
        incident=self.get_incident(session,row.incident_id)
        kind='WORK_ORDER_COMPLETED' if status=='COMPLETED' else 'WORK_ORDER_'+status
        self.write_event(session,incident,kind,'work_order',row.id,now,None,'工单状态 '+status,{'work_order_id':row.id,'status':status,'assignee':row.assignee,'result':row.result})
        session.flush()
        return row_dict(row)

    def close_record(self, session, incident_id, body, timestamp=None, simulation_time=None):
        incident=self.get_incident(session,incident_id)
        data=body_dict(body)
        if incident.status=='CLOSED':return self.detail(session,incident_id)
        if not data.get('confirmed'):raise HTTPException(422,'关闭软件仿真事件需要人工确认')
        if incident.status!='STABILIZING':raise HTTPException(409,'仅 STABILIZING 事故可以正式关闭')
        if not str(data.get('result','')).strip():raise HTTPException(422,'请填写关闭结果')
        stamp=date(timestamp) or datetime.now(UTC)
        incident.status='CLOSED';incident.closed_at=stamp;incident.updated_at=stamp
        incident.close_result={'result':data['result'],'operator':data.get('operator','demo-user')}
        self.write_event(session,incident,'INCIDENT_CLOSED','incident',incident.id,stamp,simulation_time,'人工确认关闭软件仿真事件',incident.close_result)
        session.flush()
        return self.detail(session,incident_id)

    def abort_record(self, session, incident_id, reason, timestamp=None, simulation_time=None):
        incident=self.get_incident(session,incident_id)
        if incident.status in TERMINAL:return row_dict(incident)
        stamp=date(timestamp) or datetime.now(UTC)
        incident.status='ABORTED';incident.updated_at=stamp;incident.source_status='interrupted'
        self.write_event(session,incident,'INCIDENT_ABORTED','incident',incident.id,stamp,simulation_time,'场景重置或中断，未经正式关闭',{'reason':reason})
        session.flush()
        return row_dict(incident)

    def generate_report(self, session, incident_id):
        incident=self.get_incident(session,incident_id)
        metrics=self.metrics(session,incident_id);p=metrics['peak_metrics'];r=metrics['response_metrics'];effect=metrics['response_effect'];pred=metrics['prediction_review']
        detail=self.detail(session,incident_id)
        def fmt(value,unit=''):return f'{value:.3f}{unit}' if isinstance(value,(int,float)) else '未记录'
        def number_list(items):return '、'.join(str(x) for x in items) if items else '未记录'
        if incident.incident_type=='FLOOD':
            summary=f'本次暴雨内涝事件位于 {incident.area_id}，保存 {metrics["snapshot_count"]} 个真实采样点；峰值风险 {fmt(p["peak_risk"])}，峰值水位 {fmt(p["peak_water_level"]," cm")}，最大积水面积 {fmt(p["max_water_area"]," m²")}。'
            cause='软件场景采用已记录的降雨、设备效率和排水能力演化。该记录描述仿真过程，不证明真实工程原因。最大雨量 '+fmt(p['max_rainfall'],' mm/h')+'；P03 最低效率 '+fmt(p['min_p03_efficiency'],'%')+'。'
            plans=[x.get('plan_code') or x.get('execution',{}).get('plan_code') for x in detail['executions']]
            response='记录的处置方案：'+number_list([x for x in plans if x])+'。'+effect['environment_note']
            impact='最大积水面积 '+fmt(p['max_water_area'],' m²')+'。关闭档案不代表积水、泵和入口已恢复正常。'
            lessons=['建议评估排水泵预防性维护与现场额定排水能力。'] if p['min_p03_efficiency'] is not None and p['min_p03_efficiency']<90 else ['建议补充设备效率和现场排水能力观测，以支持后续复盘。']
            if r['time_to_response_seconds'] is not None and r['time_to_response_seconds']>60:lessons.append('建议评估备用泵启动确认流程，缩短响应等待。')
        else:
            summary=f'本次地下供水管网事件定位区域 {incident.area_id}；最低记录压力 {fmt(p["min_pressure"]," MPa")}，最大记录流量 {fmt(p["max_flow"]," m³/h")}，最高检测匹配分数 {fmt(p["max_detection_score"])}，峰值风险 {fmt(p["peak_risk"])}。'
            cause='观测到压力与流量异常，定位依据观测与示范拓扑的软件匹配；分数不是经过校准的概率，不能推断真实城市定位精度。'
            valves=[v for x in detail['executions'] for v in x.get('execution',{}).get('valves',[])]
            response='记录的隔离阀门：'+number_list(sorted(set(valves)))+'。'+effect['environment_note']
            after=effect['after'] or {};interrupted=after.get('interrupted_buildings')
            impact='最大受影响建筑数 '+fmt(p['max_affected_buildings'])+'；最后记录供水状态 '+str(after.get('service_status') or '未记录')+'。'
            if interrupted is not None:impact+='仍受停水影响：'+number_list([b.get('buildingName') or b.get('buildingId') or b.get('id') for b in interrupted])+'。'
            else:impact+='旧历史未保存逐栋停水状态，不能以最后事件摘要补造较早时刻。'
            lessons=['建议评估关键节点压力和流量监测密度。']
            if p['max_affected_buildings'] is not None and p['max_affected_buildings']>=2:lessons.append('建议评估阀门分区，减少隔离导致的供水中断范围。')
        before=effect['before'];after=effect['after']
        if before and after:
            response+=f' 首次执行前最后观测风险 {fmt(before["risk_score"])}，最后观测风险 {fmt(after["risk_score"])}。'
            if incident.incident_type=='FLOOD':response+=f' 水位 {fmt(before["water_level"]," cm")} → {fmt(after["water_level"]," cm")}；有效泵能力 {fmt(before["pump_capacity"]," m³/s")} → {fmt(after["pump_capacity"]," m³/s")}。'
            else:response+=f' 泄漏流量 {fmt(before["leak_flow"]," m³/h")} → {fmt(after["leak_flow"]," m³/h")}。'
        else:response+='执行前后可配对观测不足，不计算处置效果差值。'
        prediction=f'本事件预测误差：{pred["samples"]} 个完整到期样本，水位 MAE {fmt(pred["water_mae"]," cm")}，风险 MAE {fmt(pred["risk_mae"])}。'+pred['message']
        summary+=' 状态 '+incident.status+'；检测用时 '+fmt(r['time_to_detect_seconds'],' s')+'，响应等待 '+fmt(r['time_to_response_seconds'],' s')+'，达到稳定 '+fmt(r['time_to_stabilize_seconds'],' s')+'（原始墙钟时间）。'
        if metrics['missing_fields']:lessons.append('部分旧快照字段未记录；建议持续保存完整动态状态，历史缺口不补造。')
        row=session.scalar(select(ReviewReport).where(ReviewReport.incident_id==incident_id))
        if row is None:row=ReviewReport(id=str(uuid4()),incident_id=incident_id);session.add(row)
        for key,value in {'generated_at':datetime.now(UTC),'summary':summary,'cause_analysis':cause,'response_analysis':response,
                'prediction_analysis':prediction,'impact_analysis':impact,'lessons':lessons,'status':'GENERATED','metrics':metrics}.items():setattr(row,key,value)
        session.flush()
        return row_dict(row)


    def reconcile_derived_events(self, session):
        """Explicit maintenance of M9 aliases only; preserve source rows and alias evidence.

        Call after sync_sources. Never runs during read APIs or normal capture.
        """
        session.flush()
        removed=set();enriched=0
        def merge_alias(target, alias):
            nonlocal enriched
            if target.id==alias.id or alias.id in removed:return
            evidence={key:row_dict(alias)[key] for key in ('id','event_type','source','source_id','event_time','simulation_time','title','description','payload','created_at')}
            evidence['payload']={k:v for k,v in (evidence['payload'] or {}).items() if k!='merged_source_records'}
            existing=list((target.payload or {}).get('merged_source_records',[]))
            if not any(item['id']==alias.id for item in existing):existing.append(evidence)
            target.payload={**(target.payload or {}),'merged_source_records':existing}
            if target.simulation_time is None and alias.simulation_time is not None:
                target.simulation_time=alias.simulation_time;enriched+=1
            session.delete(alias);removed.add(alias.id)
        for incident in session.scalars(select(Incident)):
            events=list(session.scalars(select(IncidentTimelineEvent).where(IncidentTimelineEvent.incident_id==incident.id)))
            actual_stable=[event for event in events if event.event_type=='RISK_STABILIZED' and event.source in ('leak_event','emergency_execution')]
            if actual_stable:
                snapshots=list(session.scalars(select(IncidentSnapshot).where(IncidentSnapshot.incident_id==incident.id).order_by(IncidentSnapshot.simulation_time,IncidentSnapshot.timestamp,IncidentSnapshot.id)))
                for alias in events:
                    if alias.event_type!='RISK_STABILIZED' or alias.source!='live_capture' or alias.source_id!='first-stable':continue
                    for target in actual_stable:
                        same_boundary=alias.simulation_time is not None and alias.simulation_time==target.simulation_time
                        if not same_boundary and target.simulation_time is not None:
                            for previous,current in zip(snapshots,snapshots[1:]):
                                if current.simulation_time!=alias.simulation_time or date(current.timestamp)!=date(alias.event_time):continue
                                branch='emergency' if incident.incident_type=='FLOOD' else 'leak'
                                field='phase' if incident.incident_type=='FLOOD' else 'currentStage'
                                before=previous.scene_state.get(branch) or {};after=current.scene_state.get(branch) or {}
                                transition=before.get(field)!='STABILIZING' and after.get(field)=='STABILIZING'
                                execution_matches=branch!='emergency' or after.get('id')==(target.payload or {}).get('execution_id')
                                if transition and execution_matches and previous.simulation_time<=target.simulation_time<=current.simulation_time:
                                    same_boundary=True;break
                        if same_boundary:merge_alias(target,alias);break
                # A real later return to STABILIZING remains a separate source event.
            if incident.incident_type!='PIPELINE_LEAK':continue
            source=session.get(PipelineLeakEvent,incident.source_event_id)
            state=source.state_json if source else {}
            source_execution=(state or {}).get('execution') or {}
            closed_events=[event for event in (state or {}).get('events',[]) if event.get('stage')=='ISOLATING']
            snapshots=list(session.scalars(select(IncidentSnapshot).where(IncidentSnapshot.incident_id==incident.id).order_by(IncidentSnapshot.simulation_time,IncidentSnapshot.timestamp,IncidentSnapshot.id)))
            for isolation in session.scalars(select(PipelineLeakIsolation).where(PipelineLeakIsolation.scenario_id==incident.scenario_id)):
                execution=isolation.execution_json or {}
                execution_id=execution.get('id')
                if not execution_id:continue
                for valve in execution.get('valves',[]):
                    canonical_id=identifier(incident.id,'VALVE_CLOSED',f'isolation:{execution_id}:{valve}')
                    target=session.get(IncidentTimelineEvent,canonical_id)
                    if target is None:continue
                    for alias in events:
                        if alias.event_type!='VALVE_CLOSED' or alias.id==target.id or alias.id in removed:continue
                        old_isolation=alias.source=='leak_isolation' and alias.source_id==isolation.id+':'+valve
                        old_source_event=alias.source=='leak_event' and source_execution.get('id')==execution_id and any(
                            alias.source_id==f'{incident.source_event_id}:{event.get("sequence")}' for event in closed_events)
                        # A live alias is the same action only when saved adjacent frames prove a new execution.
                        # Clock proximity or matching pressure alone is not sufficient evidence.
                        old_capture=False
                        if alias.source=='live_capture' and (alias.payload or {}).get('focus_target_id')==valve:
                            # Exact original event coordinates are direct evidence, not a time-window guess.
                            old_capture=source_execution.get('id')==execution_id and any(
                                event.get('simulationTime')==alias.simulation_time and date(event.get('timestamp'))==date(alias.event_time)
                                for event in closed_events)
                            for previous,current in zip(snapshots,snapshots[1:]):
                                if current.simulation_time!=alias.simulation_time or date(current.timestamp)!=date(alias.event_time):continue
                                before=((previous.scene_state.get('leak') or {}).get('execution') or {}).get('id')
                                after=((current.scene_state.get('leak') or {}).get('execution') or {}).get('id')
                                valves_before={item['id']:item.get('status') for item in previous.scene_state.get('valves') or []}
                                valves_after={item['id']:item.get('status') for item in current.scene_state.get('valves') or []}
                                if before!=execution_id and after==execution_id and valves_before.get(valve)=='open' and valves_after.get(valve)=='closed':
                                    old_capture=True;break
                        if old_isolation or old_source_event or old_capture:merge_alias(target,alias)
        session.flush()
        return {'derived_aliases_merged':len(removed),'exact_times_enriched':enriched,
                'source_tables_modified':False}
