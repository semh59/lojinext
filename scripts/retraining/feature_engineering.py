import pandas as pd


def engineer_features(df):
    """
    Route analysis'ten türetilmiş yeni feature'lar ekle
    """
    print("🛠️ Engineering features...")

    # 1. Composite features:
    df["highway_dominance"] = df["motorway_ratio"] + df["primary_ratio"]

    # 2. Absolute distance per type
    df["urban_dist_km"] = df["residential_ratio"] * df["mesafe_km"]
    df["motorway_dist_km"] = df["motorway_ratio"] * df["mesafe_km"]

    # 3. Interaction features:
    df["highway_with_load"] = df["motorway_ratio"] * df["ton"]
    df["city_with_load"] = df["residential_ratio"] * df["ton"]

    # 4. Elevation weighted by road type (Climb factor)
    df["ascent_per_km"] = df["ascent_m"] / df["mesafe_km"]
    df["highway_ascent"] = df["ascent_m"] * df["motorway_ratio"]
    df["city_ascent"] = df["ascent_m"] * df["residential_ratio"]

    # 5. Efficiency score:
    df["route_efficiency"] = df["highway_dominance"] - (df["residential_ratio"] * 2)

    print("✅ New features added:")
    new_cols = [
        "highway_dominance",
        "urban_dist_km",
        "motorway_dist_km",
        "highway_with_load",
        "city_with_load",
        "ascent_per_km",
        "highway_ascent",
        "city_ascent",
        "route_efficiency",
    ]
    for col in new_cols:
        print(f"  - {col}")

    return df


if __name__ == "__main__":
    import os

    if os.path.exists("training_data_with_routes.csv"):
        df = pd.read_csv("training_data_with_routes.csv")
        df = engineer_features(df)
        df.to_csv("featured_training_data.csv", index=False)
        print("✅ Featured data saved to featured_training_data.csv")
    else:
        print("❌ CSV not found. Run prepare_training_data.py first.")
