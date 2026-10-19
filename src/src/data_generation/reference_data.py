"""NovaTrust Bank reference-data generator.
All data is synthetic and for the BankOps Intelligence learning project.
"""
from pathlib import Path
import pandas as pd

def build_reference_data(output_dir):
    services = [
        ("S001","Interbank Transfer","Payments","Critical",True),
        ("S002","Intrabank Transfer","Payments","Critical",True),
        ("S003","Authentication","Access","Critical",True),
        ("S004","OTP","Access","High",True),
        ("S005","Bill Payment","Payments","High",True),
        ("S006","Airtime and Data","Payments","Medium",True),
        ("S007","Account Services","Accounts","High",True),
    ]
    components = [
        ("C001","Payment Service","Application","Critical"),
        ("C002","Core Banking System","Internal System","Critical"),
        ("C003","External Payment Provider","External Provider","Critical"),
        ("C004","OTP Provider","External Provider","High"),
        ("C005","Authentication Service","Application","Critical"),
        ("C006","Operational Database","Database","Critical"),
        ("C007","API Gateway","Integration","Critical"),
        ("C008","Bill Payment Provider","External Provider","High"),
        ("C009","Airtime Provider","External Provider","Medium"),
        ("C010","Account Service API","Application","High"),
    ]
    dependencies = [
        ("D001","S001","C001","Direct","Critical"),("D002","S001","C002","Direct","Critical"),
        ("D003","S001","C003","External","Critical"),("D004","S001","C007","Direct","Critical"),
        ("D005","S002","C001","Direct","Critical"),("D006","S002","C002","Direct","Critical"),
        ("D007","S002","C007","Direct","High"),("D008","S003","C005","Direct","Critical"),
        ("D009","S003","C006","Data","Critical"),("D010","S003","C004","External","High"),
        ("D011","S004","C004","External","Critical"),("D012","S004","C005","Direct","High"),
        ("D013","S005","C001","Direct","High"),("D014","S005","C008","External","Critical"),
        ("D015","S005","C007","Direct","High"),("D016","S006","C001","Direct","Medium"),
        ("D017","S006","C009","External","High"),("D018","S007","C010","Direct","Critical"),
        ("D019","S007","C002","Direct","Critical"),("D020","S007","C006","Data","Critical"),
    ]
    output=Path(output_dir); output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(services,columns=["service_id","service_name","category","criticality","active"]).to_csv(output/"services.csv",index=False)
    pd.DataFrame(components,columns=["component_id","component_name","component_type","criticality"]).to_csv(output/"components.csv",index=False)
    pd.DataFrame(dependencies,columns=["dependency_id","service_id","component_id","dependency_type","criticality"]).to_csv(output/"service_dependencies.csv",index=False)

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    build_reference_data(root/"data"/"raw")
    print("NovaTrust Bank reference data created successfully.")
