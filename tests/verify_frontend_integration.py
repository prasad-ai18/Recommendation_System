import requests
import sys

def main():
    base = 'http://127.0.0.1:8000'
    checks = [
        ('/', 200, 'RecSys AI'),
        ('/static/css/styles.css', 200, 'Antigravity Visual Design System'),
        ('/static/js/app.js', 200, 'RecSys AI — Personalized Recommendation Intelligence Platform'),
        ('/api/health', 200, 'healthy'),
        ('/api/users', 200, 'sample_users'),
        ('/api/genres', 200, 'genres'),
        ('/api/recommend/1?k=5&model_type=hybrid', 200, 'recommendations'),
        ('/api/recommend/1?k=5&model_type=item_collaborative', 200, 'recommendations'),
        ('/api/recommend/1?k=5&model_type=matrix_factorization_svd', 200, 'recommendations'),
        ('/api/recommend/1?k=5&model_type=popularity', 200, 'recommendations'),
        ('/api/movies?page=1&page_size=5', 200, 'movies'),
        ('/api/users/1/profile', 200, 'ratings_count'),
        ('/api/metrics', 200, 'winner_model'),
    ]

    all_passed = True
    for path, expected_status, expected_text in checks:
        url = base + path
        try:
            res = requests.get(url, timeout=5)
            ok = (res.status_code == expected_status) and (expected_text in res.text)
            print(f'[{ "PASS" if ok else "FAIL" }] {path} -> {res.status_code}')
            if not ok:
                all_passed = False
                print(f'   Expected {expected_status} and "{expected_text}", got {res.status_code}')
        except Exception as e:
            print(f'[FAIL] {path} -> Exception: {e}')
            all_passed = False

    # Test POST /api/feedback
    try:
        res = requests.post(base + '/api/feedback', json={'user_id': 1, 'movie_id': 260, 'interaction_type': 'like', 'rating': 5.0})
        ok = res.status_code == 200 and res.json().get('status') == 'success'
        print(f'[{ "PASS" if ok else "FAIL" }] POST /api/feedback -> {res.status_code}')
        if not ok:
            all_passed = False
    except Exception as e:
        print(f'[FAIL] POST /api/feedback -> {e}')
        all_passed = False

    print('\nTotal Verification Summary:', 'ALL ENDPOINTS AND ASSETS PASSED' if all_passed else 'SOME CHECKS FAILED')
    if not all_passed:
        sys.exit(1)

if __name__ == '__main__':
    main()
