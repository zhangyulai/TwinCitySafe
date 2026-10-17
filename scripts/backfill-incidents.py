#!/usr/bin/env python3
"""Idempotently index existing M5–M8 history without reconstructing missing observations."""
from pathlib import Path
import sys
import json
import argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.core.database import SessionLocal
from app.services.incident_service import IncidentService

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reconcile-derived',action='store_true',help='Explicitly merge proven duplicate M9 timeline aliases; original M5–M8 tables are untouched.')
    args=parser.parse_args()
    with SessionLocal() as session:
        service=IncidentService(SessionLocal)
        result=service.sync_sources(session)
        if args.reconcile_derived:result['reconciliation']=service.reconcile_derived_events(session)
        session.commit()
    print(json.dumps(result,ensure_ascii=False))
