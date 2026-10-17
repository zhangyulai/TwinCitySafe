import asyncio,json
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
import httpx
from sqlalchemy import select
from simulator.engine import SimulationEngine
from app.main import app
from app.schemas.flood import FloodScenarioRequest
from app.services.flood_service import FloodService
from app.services.flood_storage_service import FloodStorageService
from app.services.risk_prediction_service import RiskPredictionService
from app.models.risk_prediction import RiskPredictionRecord
from algorithm.risk_prediction.dataset import scenario_rows,scenario_split,create_scenario
from algorithm.risk_prediction.features import FEATURE_NAMES,build_features
from algorithm.risk_prediction.config import MODEL_DIR
from algorithm.risk_prediction.simulation import SimulationCopy
from algorithm.risk_prediction.inference import RiskModels,agreement

def engine():
    e=SimulationEngine();FloodService(e).start(FloodScenarioRequest(),True);e.set_speed(10)
    for _ in range(35):e.tick()
    return e

def test_dataset_reproducible_and_finite():
    a=scenario_rows((4,42,6));b=scenario_rows((4,42,6));c=scenario_rows((4,43,6))
    for x,y in zip(a,b):np.testing.assert_array_equal(x,y);assert np.isfinite(x).all()
    assert a[0].shape==(6,30) and a[1].shape==(6,6)
    assert not np.array_equal(a[0],c[0])

def test_group_split_has_no_overlap_or_missing_scenarios():
    groups=scenario_split(250);sets=[set(x) for x in groups.values()]
    assert len(set.union(*sets))==250
    assert not sets[0]&sets[1] and not sets[0]&sets[2] and not sets[1]&sets[2]
    assert list(map(len,sets))==[170,40,40]
    assert groups==scenario_split(250)

def test_targets_match_independent_cloned_rollout():
    x,y=scenario_rows((3,123,4));original=create_scenario(123,3)
    original.step(5);original.step(5)
    np.testing.assert_allclose(build_features(original),x[1])
    copy=SimulationCopy(original);actual=[]
    for i in range(360):
        copy.step(5)
        if i+1 in (120,240,360):actual.append((copy._state.flood.water_level,copy._state.flood.risk_score))
    np.testing.assert_allclose(y[1],[v[k] for k in (0,1) for v in actual],rtol=1e-6)
    assert original._state.flood.elapsed_simulation_seconds==10

def test_shared_feature_dimension_all_scenario_families():
    assert len(FEATURE_NAMES)==len(set(FEATURE_NAMES))==30
    for family in range(10):
        model=create_scenario(500+family,family);row=build_features(model)
        assert row.shape==(30,) and np.isfinite(row).all()
        assert row[FEATURE_NAMES.index('p03_status')] in (0,1,2,3)
    assert not any(k in FEATURE_NAMES for k in ('scenario_id','timestamp','uuid','device_name'))

def test_real_models_load_and_predict_valid_horizons():
    models=RiskModels();assert models.available and len(models.models)==6
    for family in (0,4,5,7):
        result=models.predict(build_features(create_scenario(42,family)))
        assert [p['minute'] for p in result]==[10,20,30]
        assert all(np.isfinite([p['waterLevel'],p['riskScore']]).all() and p['waterLevel']>=0 and 0<=p['riskScore']<=100 for p in result)

def test_native_shap_additivity_and_explicit_approximate_fallback():
    models=RiskModels();row=build_features(engine());ex=models.explain(row)
    assert ex['method']=='native_tree_shap'
    assert ex['baseValue']+sum(p['contribution'] for p in ex['topFeatures'])+ex['otherContribution']==pytest.approx(ex['rawPrediction'],abs=.001)
    fallback=models.explain(row,force_fallback=True)
    assert fallback['method']=='importance_deviation' and fallback['baseValue'] is None
    assert fallback['topFeatures']

def test_model_missing_version_mismatch_and_checksum(tmp_path):
    assert not RiskModels(tmp_path).available
    meta=json.loads((MODEL_DIR/'metadata.json').read_text());meta['feature_version']='wrong'
    (tmp_path/'metadata.json').write_text(json.dumps(meta))
    assert 'version' in RiskModels(tmp_path).error
    meta['feature_version']='m6-v1';(tmp_path/'metadata.json').write_text(json.dumps(meta));(tmp_path/'water_10m.json').write_text('{}')
    assert 'checksum' in RiskModels(tmp_path).error

@pytest.mark.parametrize('water,risk,expected',[(.1,1,'high'),(2,1,'medium'),(1,8,'medium'),(5,15,'medium'),(5.1,1,'low'),(1,15.1,'low')])
def test_model_agreement_thresholds(water,risk,expected):assert agreement(water,risk)==expected

def test_prediction_cache_copy_no_side_effects_and_control_invalidation(isolated_storage):
    async def exercise():
        e=engine();s=RiskPredictionService(e,isolated_storage);before=e.snapshot().model_dump();internals=deepcopy(e.devices.__dict__)
        first=await s.prediction();again=await s.prediction()
        assert again['cacheHit'] and first['id']==again['id']
        again['mlForecast'][0]['waterLevel']=-1
        assert (await s.prediction())['mlForecast'][0]['waterLevel']>=0
        await s.explanation();assert e.snapshot().model_dump()==before and e.devices.__dict__==internals
        e.set_device_state('P01','running');changed=await s.prediction();assert changed['id']!=first['id']
        FloodService(e).reset();idle=await s.prediction();assert not idle['physicalForecast'] and not idle['mlForecast']
    asyncio.run(exercise())

def test_missing_model_preserves_physical_forecast(isolated_storage,tmp_path):
    async def exercise():
        s=RiskPredictionService(engine(),isolated_storage,tmp_path);p=await s.prediction()
        assert not p['modelStatus']['available'] and not p['mlForecast'] and len(p['physicalForecast'])==3
        assert not (await s.explanation())['available']
    asyncio.run(exercise())

def test_prediction_backtest_matches_real_future_and_persists(isolated_storage):
    async def exercise():
        e=engine();s=RiskPredictionService(e,isolated_storage)
        await FloodStorageService(e,isolated_storage).sample()
        s.evaluation.observe(e.snapshot());p=await s.prediction();s.evaluation.register(p,e._state.session_id);await s.flush()
        for _ in range(60):s.evaluation.observe(e.tick())
        summary=s.evaluation.summary(e._state.flood.scenario_id)
        assert summary['samples']==1 and summary['pending']==2
        actual=e._state.flood.water_level
        expected=actual-p['mlForecast'][0]['waterLevel']
        assert summary['waterMae']==pytest.approx(abs(expected),abs=.0001)
        assert summary['physicalWaterMae']<.12
        await s.flush()
        with isolated_storage() as db:
            rows=list(db.scalars(select(RiskPredictionRecord)));assert len(rows)==3
            row=next(r for r in rows if r.horizon_minutes==10)
            assert row.evaluation_status=='evaluated' and row.water_error==pytest.approx(expected)
        FloodService(e).reset();s.evaluation.observe(e.snapshot());await s.flush()
        with isolated_storage() as db:assert len([r for r in db.scalars(select(RiskPredictionRecord)) if r.evaluation_status=='interrupted'])==2
    asyncio.run(exercise())

def test_risk_api_invalid_horizon_and_missing_model(isolated_storage,tmp_path):
    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                assert (await c.get('/api/v1/risk/model/status')).json()['available']
                assert not (await c.get('/api/v1/risk/prediction')).json()['mlForecast']
                await c.post('/api/v1/simulation/flood/demo-start')
                r=(await c.get('/api/v1/risk/prediction?horizons=10,30')).json();assert [p['minute'] for p in r['mlForecast']]==[10,30]
                assert (await c.get('/api/v1/risk/prediction?horizons=5')).status_code==422
                assert (await c.get('/api/v1/risk/prediction/explanation?minutes=20')).json()['available']
                assert (await c.get('/api/v1/risk/prediction/explanation?minutes=5')).status_code==422
                await app.state.realtime.risk.shutdown()
                app.state.realtime.risk=RiskPredictionService(app.state.realtime.engine,isolated_storage,tmp_path)
                r=(await c.get('/api/v1/risk/prediction')).json();assert len(r['physicalForecast'])==3 and not r['modelStatus']['available']
    asyncio.run(exercise())


def test_nonfinite_native_output_degrades_before_clamping(isolated_storage):
    class InvalidModel:
        def inplace_predict(self,row):return np.array([float('nan')])
    async def exercise():
        e=engine();s=RiskPredictionService(e,isolated_storage)
        s.models.models['water_10m']=InvalidModel()
        with pytest.raises(ValueError,match='Non-finite'):s.models.predict(build_features(e))
        result=await s.prediction()
        assert not result['modelStatus']['available'] and not result['mlForecast']
        assert len(result['physicalForecast'])==3
    asyncio.run(exercise())
