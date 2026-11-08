import pandas as pd
import requests
import time

scenarios = pd.read_csv('evaluation/evaluation_test_scenarios.csv')
url = "http://127.0.0.1:8000/ask"
results = []

for index, row in scenarios.iterrows():
    print(f"Testing {row['scenario_id']}...")
    start_time = time.time()
    try:
        response = requests.post(url, json={"query": row['query']}, timeout=60)
        latency = time.time() - start_time
        data = response.json()
        actual_response = data.get("data", "")
        intent = data.get("intent", "")
        status = data.get("status", "")
    except Exception as e:
        latency = time.time() - start_time
        actual_response = str(e)
        intent = "error"
        status = "error"
    
    results.append({
        "scenario_id": row['scenario_id'],
        "category": row['category'],
        "query": row['query'],
        "intent": intent,
        "status": status,
        "actual_response": actual_response,
        "response_time_seconds": round(latency, 2),
        "observation": "" 
    })

pd.DataFrame(results).to_csv('evaluation/evaluation_results.csv', index=False)
print("Selesai. Cek evaluation/evaluation_results.csv")