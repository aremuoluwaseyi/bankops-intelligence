"""Phase 4 Step 2: component-level monitoring for BankOps Intelligence."""
from pathlib import Path
import pandas as pd
import numpy as np

def build_component_monitoring(root):
    root=Path(root); proc=root/"data"/"processed"; raw=root/"data"/"raw"
    metrics=pd.read_csv(proc/"component_metrics_all.csv",parse_dates=["timestamp"])
    health=pd.read_csv(proc/"service_health_all.csv",parse_dates=["timestamp"])
    components=pd.read_csv(raw/"components.csv")
    m=metrics.merge(components[["component_id","component_name","component_type","criticality"]],on="component_id",how="left")
    h=health[["timestamp","component_id","scenario","status","availability_pct","health_check_ms"]]
    view=m.merge(h,on=["timestamp","component_id","scenario"],how="outer",validate="one_to_one")
    normal=m[m.scenario=="NORMAL"].groupby(["component_id","component_name","metric_name","unit"],as_index=False).agg(
        baseline_avg_metric=("metric_value","mean"),
        baseline_p95_metric=("metric_value",lambda x: np.percentile(x,95)))
    view=view.merge(normal[["component_id","metric_name","baseline_avg_metric","baseline_p95_metric"]],
                    on=["component_id","metric_name"],how="left")
    view["metric_vs_baseline_ratio"]=(view.metric_value/view.baseline_avg_metric).round(2)
    return view.sort_values(["timestamp","component_id","scenario"])

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    df=build_component_monitoring(root)
    df.to_csv(root/"data"/"processed"/"component_monitoring_5min.csv",index=False)
    print(f"Created {len(df):,} component monitoring observations.")
