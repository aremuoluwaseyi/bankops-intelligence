"""Unsupervised Isolation Forest detector. Labels are external to model fitting."""
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
FEATURES=["transaction_volume","failure_rate_pct","p95_response_ms","max_response_ms","max_component_metric_ratio","avg_component_availability_pct","max_health_check_ms","degraded_components","down_components","warn_logs","error_logs","warn_error_logs","technical_evidence_available"]
def build_model():
    return Pipeline([("imputer",SimpleImputer(strategy="median",add_indicator=True)),("scaler",StandardScaler()),("model",IsolationForest(n_estimators=300,contamination=.01,random_state=42,n_jobs=-1))])
