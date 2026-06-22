import os

import joblib
import pandas as pd
from sklearn.model_selection import cross_val_score
from xgboost import XGBRegressor


def train_vehicle_models(df):
    """
    Her araç için ayrı model eğit
    """
    if not os.path.exists("app/core/ml/models"):
        os.makedirs("app/core/ml/models", exist_ok=True)

    # Feature listesi
    features = [
        "mesafe_km",
        "ton",
        "ascent_m",
        "descent_m",
        "motorway_ratio",
        "primary_ratio",
        "residential_ratio",
        "unclassified_ratio",
        "highway_dominance",
        "highway_with_load",
        "city_with_load",
        "highway_ascent",
        "city_ascent",
        "route_efficiency",
    ]

    target = "gercek_tuketim"

    # Ensure target is valid (L/100km normalized usually, but user asked for gercek_tuketim)
    # We should train on absolute consumption or L/100km?
    # Usually XGBoost performs better on L/100km.
    df["target_l_100"] = (df["gercek_tuketim"] / df["mesafe_km"]) * 100
    target = "target_l_100"

    # Filter out outliers (e.g. consumption > 80 or < 10)
    df = df[(df[target] > 10) & (df[target] < 100)]

    # Araç bazında grupla
    vehicles = df["arac_id"].unique()

    results = []

    for vehicle_id in vehicles:
        print(f"\n🚛 Araç {vehicle_id} eğitiliyor...")

        vehicle_df = df[df["arac_id"] == vehicle_id]

        # Minimum veri kontrolü (Usually 5-10 for small datasets in this project)
        if len(vehicle_df) < 5:
            print(f"  ⚠️ Yetersiz veri ({len(vehicle_df)} sefer). Atlanıyor.")
            continue

        X = vehicle_df[features]
        y = vehicle_df[target]

        # Fit logic
        model = XGBRegressor(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )

        model.fit(X, y)

        # CV Score
        cv_scores = cross_val_score(model, X, y, cv=min(len(X), 5), scoring="r2")

        # Importance
        importance = dict(zip(features, model.feature_importances_))

        # Kaydet
        model_path = f"app/core/ml/models/vehicle_{vehicle_id}_v3.pkl"
        joblib.dump(model, model_path)

        result = {
            "vehicle_id": vehicle_id,
            "samples": len(vehicle_df),
            "cv_r2_mean": cv_scores.mean(),
            "top_features": sorted(
                importance.items(), key=lambda x: x[1], reverse=True
            )[:3],
            "model_path": model_path,
        }
        results.append(result)

        print(f"  ✅ R² (CV): {cv_scores.mean():.3f}")
        print(
            f"  📊 Top Features: {', '.join([f'{f} ({i:.2f})' for f, i in result['top_features']])}"
        )

    return results


if __name__ == "__main__":
    if os.path.exists("featured_training_data.csv"):
        df = pd.read_csv("featured_training_data.csv")
        results = train_vehicle_models(df)
        # Save results for comparison script
        pd.DataFrame(results).to_csv("training_results_v3.csv", index=False)
    else:
        print("❌ Featured data not found.")
