"""
Standalone script to train domain recommender (no Django).
Run from backend dir: python train_domain_recommender_standalone.py
Saves model to assessments/model_domain_recommender.joblib for submit-ml API.
"""
import random
from pathlib import Path

NUM_FEATURES = 3
NUM_SAMPLES = 2000
RANDOM_SEED = 42


def main():
    try:
        from sklearn.ensemble import RandomForestClassifier
        import joblib
    except ImportError as e:
        print("Install first: pip install scikit-learn joblib")
        raise SystemExit(1) from e

    random.seed(RANDOM_SEED)
    X = []
    y = []
    for _ in range(NUM_SAMPLES):
        pcts = [random.uniform(0, 100) for _ in range(NUM_FEATURES)]
        best_idx = 0
        best_val = pcts[0]
        for i in range(1, NUM_FEATURES):
            if pcts[i] > best_val:
                best_val = pcts[i]
                best_idx = i
        X.append(pcts)
        y.append(best_idx)

    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=RANDOM_SEED)
    model.fit(X, y)

    backend_dir = Path(__file__).resolve().parent
    path = backend_dir / "assessments" / "model_domain_recommender.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    print(f"Model saved to {path}")


if __name__ == "__main__":
    main()
