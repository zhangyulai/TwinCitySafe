"""All demonstrator constants; MPa, m3/h, simulated seconds."""
DEMO_PIPELINE="WS-003"
DEMO_SEVERITY=.75
WARMUP_SECONDS=30
RAMP_SECONDS=180
LEAK_COEFFICIENT=60.0
DETECTION_THRESHOLDS=(.35,.55,.75)
DETECTION_WEIGHTS={"pressure_deviation":.30,"flow_deviation":.25,"pressure_trend":.10,"flow_trend":.10,"imbalance":.25}
RISK_WEIGHTS={"leak_flow":.50,"pressure_loss":.20,"affected_buildings":.10,"service_disruption":.15,"growth":.05}
