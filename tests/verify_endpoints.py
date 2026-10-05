"""End-to-end verification script for evaluation and FastAPI endpoints."""

import requests
import json

base = "http://127.0.0.1:8000"

print("==============================================")
print("1. HEALTH ENDPOINT CHECK (/health)")
print("==============================================")
h = requests.get(f"{base}/health").json()
print(json.dumps(h, indent=2))

print("\n==============================================")
print("2. REAL EVALUATION METRICS CHECK (/metrics)")
print("==============================================")
m = requests.get(f"{base}/metrics").json()
print("Protocol:", m["evaluation_protocol"])
print("Evaluated Users:", m["evaluated_users_count"])
print("Winner Model:", m["winner_model"])
print("\nModel Comparison Table:")
header = f"{'Model':<28} | {'P@5':<7} | {'P@10':<7} | {'R@10':<7} | {'NDCG@10':<8} | {'HR@10':<7} | {'Coverage':<8}"
print(header)
print("-" * len(header))
for mod_id, data in m["models"].items():
    met = data["metrics"]
    p5 = met.get("precision@5", 0)
    p10 = met.get("precision@10", 0)
    r10 = met.get("recall@10", 0)
    ndcg10 = met.get("ndcg@10", 0)
    hr10 = met.get("hit_rate@10", 0) * 100
    cov = met.get("catalog_coverage", 0) * 100
    print(f"{data['model_name']:<28} | {p5:<7.4f} | {p10:<7.4f} | {r10:<7.4f} | {ndcg10:<8.4f} | {hr10:<6.1f}% | {cov:<7.2f}%")

print("\nLifts vs Popularity Baseline:")
for mod_id, lifts in m["lifts_vs_popularity_baseline"].items():
    p10_l = lifts.get("precision@10", 0)
    hr10_l = lifts.get("hit_rate@10", 0)
    cov_l = lifts.get("catalog_coverage", 0)
    print(f" - {mod_id}: P@10 Lift: {p10_l:+.1f}%, HR@10 Lift: {hr10_l:+.1f}%, Coverage Lift: {cov_l:+.1f}%")

print("\n==============================================")
print("3. RECOMMENDATIONS ENDPOINT (/recommend/{user_id})")
print("==============================================")
rec = requests.get(f"{base}/recommend/1?k=4&model_type=hybrid").json()
print(f"User: {rec['user_id']} | Model: {rec['model_name']} | Latency: {rec['latency_ms']} ms")
for item in rec["recommendations"]:
    print(f" - {item['title']} ({item['year']}) | Score: {item['predicted_score']} | Signal: {item['recommendation_signal']}")

print("\n==============================================")
print("4. MOVIES CATALOG ENDPOINT (/movies)")
print("==============================================")
movies = requests.get(f"{base}/movies?query=star%20wars&page=1&page_size=3").json()
print(f"Found: {movies['total_count']} matching movies")
for mov in movies["movies"]:
    print(f" - [{mov['movie_id']}] {mov['title']} | Avg: {mov['rating_mean']} ({mov['rating_count']} ratings) | Bayesian: {mov['bayesian_score']}")

print("\n==============================================")
print("5. FEEDBACK ENDPOINT (POST /feedback)")
print("==============================================")
fb_payload = {"user_id": 1, "movie_id": 260, "interaction_type": "rating", "rating": 5.0}
fb = requests.post(f"{base}/feedback", json=fb_payload).json()
print(json.dumps(fb, indent=2))

print("\n==============================================")
print("6. VALIDATION & ERROR HANDLING CHECK")
print("==============================================")
err400 = requests.get(f"{base}/recommend/1?model_type=invalid_model")
print(f"Invalid Model -> Status: {err400.status_code} | Response: {err400.json()['detail']}")

err422 = requests.get(f"{base}/recommend/-5")
print(f"Negative User ID -> Status: {err422.status_code} | Error caught by Pydantic validation")
