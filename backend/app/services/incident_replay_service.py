"""Read saved observations only. No simulator, extrapolation, or current asset state."""
from datetime import datetime, UTC
from statistics import median
from time import perf_counter
import json
from sqlalchemy import select
from fastapi import HTTPException
from app.models.incident import Incident, IncidentSnapshot, IncidentTimelineEvent
from app.models.flood import FloodSnapshot
from app.models.leak import PipelineLeakSnapshot
from simulator.flood_config import PARKING_EFFECTIVE_AREA_M2


def iso(value):
    if value is None: return None
    if isinstance(value, str): return value
    return value.replace(tzinfo=value.tzinfo or UTC).isoformat()


def row_dict(row):
    return {column.name: iso(value) if isinstance(value := getattr(row, column.name), datetime) else value
            for column in row.__table__.columns}


def risk_level(value):
    return 'extreme' if value >= 80 else 'high' if value >= 60 else 'elevated' if value >= 40 else 'general' if value >= 20 else 'low'


class IncidentReplayService:
    @staticmethod
    def require(session, incident_id):
        incident = session.get(Incident, incident_id)
        if incident is None: raise HTTPException(404, '事故档案不存在')
        return incident

    @staticmethod
    def timeline(session, incident_id):
        IncidentReplayService.require(session, incident_id)
        rows = list(session.scalars(select(IncidentTimelineEvent).where(IncidentTimelineEvent.incident_id == incident_id)))
        rows.sort(key=lambda r: (r.simulation_time if r.simulation_time is not None else float('inf'), iso(r.event_time), r.id))
        return [row_dict(row) for row in rows]

    def snapshots(self, session, incident):
        if isinstance(incident, str): incident = self.require(session, incident)
        full = list(session.scalars(select(IncidentSnapshot).where(IncidentSnapshot.incident_id == incident.id)))
        exact_times = {row.simulation_time for row in full}
        points = [{k: v for k, v in row_dict(row).items() if k not in ('incident_id', 'state_hash')} for row in full]
        if incident.incident_type == 'FLOOD':
            rows = session.scalars(select(FloodSnapshot).where(FloodSnapshot.scenario_id == incident.scenario_id))
            for r in rows:
                if r.simulation_time in exact_times: continue
                points.append(dict(id=f'flood:{r.id}', timestamp=iso(r.timestamp), simulation_time=r.simulation_time,
                    risk_score=r.risk_score, risk_level=risk_level(r.risk_score), source_snapshot_id=f'flood:{r.id}',
                    scene_state={'weather': {'rainfall': r.rainfall}, 'flood': {'scenarioId': incident.scenario_id,
                        'elapsedSimulationSeconds': r.simulation_time, 'rainfall': r.rainfall, 'waterLevel': r.water_level,
                        'waterArea': r.water_area, 'surfaceInflow': r.inflow, 'outflow': r.outflow,
                        'effectivePumpCapacity': r.pump_capacity, 'riskScore': r.risk_score,
                        'riskLevel': risk_level(r.risk_score), 'stage': r.stage}},
                    missing_fields=['environment','devices','pipelines','valves','emergency','flood.entranceClosed',
                        'flood.peopleCount','flood.vehicleCount','weather.windSpeed']))
        else:
            rows = session.scalars(select(PipelineLeakSnapshot).where(PipelineLeakSnapshot.scenario_id == incident.scenario_id))
            for r in rows:
                if r.simulation_time in exact_times: continue
                points.append(dict(id=f'leak:{r.id}', timestamp=iso(r.timestamp), simulation_time=r.simulation_time,
                    risk_score=r.risk_score, risk_level=risk_level(r.risk_score), source_snapshot_id=f'leak:{r.id}',
                    scene_state={'leak': {'scenarioId': incident.scenario_id, 'elapsedSimulationSeconds': r.simulation_time,
                        'downstreamPressure': r.pressure, 'pipelineFlow': r.flow, 'leakSeverity': r.leak_severity,
                        'detectionScore': r.detection_score, 'riskScore': r.risk_score, 'riskLevel': risk_level(r.risk_score),
                        'suspectedSegments': r.top_suspects, 'affectedBuildingCount': r.affected_count}},
                    missing_fields=['weather','environment','devices','pipelines','valves','leak.upstreamPressure',
                        'leak.estimatedLeakFlow','leak.affectedBuildings','leak.interruptedBuildings','leak.serviceStatus',
                        'leak.currentStage','leak.confirmedAt','leak.execution']))
        return sorted(points, key=lambda point: (point['simulation_time'], point['timestamp'], point['id']))

    @staticmethod
    def key_moments(points, timeline, incident_id):
        moments = [dict(event) for event in timeline if event['event_type'] not in ('FORECAST_GENERATED','DEVICE_WARNING')]
        for key, path, title in [('PEAK_RISK', None, '峰值风险'), ('PEAK_WATER', 'waterLevel', '峰值水位')]:
            eligible = [(p, p.get('risk_score') if path is None else p.get('scene_state',{}).get('flood',{}).get(path)) for p in points]
            eligible = [(p,v) for p,v in eligible if v is not None]
            if not eligible: continue
            point, value = max(eligible, key=lambda item: item[1])
            moments.append({'id': f'{key}:{point["id"]}', 'incident_id': incident_id, 'event_time': point['timestamp'],
                'simulation_time': point['simulation_time'], 'event_type': key, 'event_level':'warning', 'title': title,
                'description': f'{title} {value:.3f}', 'source':'snapshot_rule', 'source_id':point['id'],
                'payload': {'value':value}, 'created_at':point['timestamp']})
        return sorted(moments, key=lambda e: (e['simulation_time'] if e['simulation_time'] is not None else float('inf'), e['event_time'], e['id']))

    def replay(self, session, incident_id, from_time=None, to_time=None, step_seconds=5):
        started = perf_counter()
        incident = self.require(session, incident_id)
        if step_seconds <= 0 or step_seconds > 3600: raise HTTPException(422, 'step_seconds 必须在 (0, 3600]')
        if from_time is not None and from_time < 0 or to_time is not None and to_time < 0:
            raise HTTPException(422, '回放时间必须非负')
        if from_time is not None and to_time is not None and from_time > to_time:
            raise HTTPException(422, 'from_time 不能晚于 to_time')
        all_points = self.snapshots(session, incident)
        timeline = self.timeline(session, incident_id)
        start = from_time if from_time is not None else all_points[0]['simulation_time'] if all_points else 0
        end = to_time if to_time is not None else all_points[-1]['simulation_time'] if all_points else start
        selected = [p for p in all_points if start <= p['simulation_time'] <= end]
        intervals = [b['simulation_time']-a['simulation_time'] for a,b in zip(all_points, all_points[1:]) if b['simulation_time']>a['simulation_time']]
        threshold = max(15., (median(intervals) * 3 if intervals else 15.))
        gaps = [{'from_time': a['simulation_time'], 'to_time':b['simulation_time'],
            'duration_seconds':b['simulation_time']-a['simulation_time'], 'message':'该时段历史采样缺失，禁止补造历史'}
            for a,b in zip(selected,selected[1:]) if b['simulation_time']-a['simulation_time'] > threshold
            and (datetime.fromisoformat(b['timestamp'])-datetime.fromisoformat(a['timestamp'])).total_seconds() > 15
            and a['scene_state'].get('running') is not False]
        # Keep observed discrete boundaries independently of event sampling and requested step.
        def discrete(point):
            state=point['scene_state'];f=state.get('flood') or {};leak=state.get('leak') or {};execution=state.get('emergency') or {}
            return json.dumps({'running':state.get('running'),
                'devices':[(d.get('id'),d.get('status'),d.get('fault')) for d in state.get('devices') or []],
                'valves':[(v.get('id'),v.get('status')) for v in state.get('valves') or []],
                'pipelines':[(p.get('id'),p.get('status')) for p in state.get('pipelines') or []],
                'flood':[f.get('entranceClosed'),f.get('stage')],
                'leak':[leak.get('currentStage'),leak.get('leakStatus'),leak.get('serviceStatus'),
                    [p.get('pipeline_id') for p in leak.get('suspectedSegments') or []]],
                'execution':[execution.get('id'),execution.get('status'),execution.get('phase'),
                    [(step.get('index'),step.get('status')) for step in execution.get('steps') or []]]},sort_keys=True)
        boundary_ids=set()
        for a,b in zip(selected,selected[1:]):
            if discrete(a)!=discrete(b):boundary_ids.update([a['id'],b['id']])
        event_times = {event['simulation_time'] for event in timeline if event['simulation_time'] is not None and event['event_type']!='FORECAST_GENERATED'}
        reduced = []
        for point in selected:
            if not reduced or point['simulation_time'] - reduced[-1]['simulation_time'] >= step_seconds or point['simulation_time'] in event_times or point['id'] in boundary_ids:
                reduced.append(point)
        if selected and (not reduced or reduced[-1]['id'] != selected[-1]['id']): reduced.append(selected[-1])
        dropped_boundaries = 0
        if len(reduced) > 2000:
            important = {0, len(reduced)-1} | {i for i,p in enumerate(reduced) if p['id'] in boundary_ids or p['simulation_time'] in event_times}
            if len(important)>2000:
                dropped_boundaries=len(important)-2000
                ordered=sorted(important)
                indexes={ordered[round(i*(len(ordered)-1)/1999)] for i in range(2000)}
            else:
                candidates=[i for i in range(len(reduced)) if i not in important]
                remaining=2000-len(important)
                indexes=important | {candidates[round(i*(len(candidates)-1)/max(1,remaining-1))] for i in range(remaining)}
            reduced=[point for i,point in enumerate(reduced) if i in indexes]
        moments = self.key_moments(selected, [e for e in timeline if e['simulation_time'] is None or start <= e['simulation_time'] <= end], incident_id)
        return {'metadata': {'incident_id': incident_id, 'incident_type':incident.incident_type,
            'from_time':start, 'to_time':end, 'step_seconds':step_seconds, 'gaps':gaps,
            'gap_threshold_seconds':threshold, 'dropped_event_boundaries':dropped_boundaries, 'missing_fields':sorted({v for point in selected for v in point['missing_fields']}),
            'snapshot_count':len(reduced), 'source_snapshot_count':len(selected), 'latency_ms':round((perf_counter()-started)*1000,3),
            'rendering_basis':{'park_effective_area_m2':PARKING_EFFECTIVE_AREA_M2, 'source':'M5 static B2 model area, not a historical observation'}},
            'timeline': timeline, 'snapshots':reduced, 'key_moments':moments}
