import pandas as pd
import numpy as np
import datetime
from app.services.feature_engineering import FeatureEngineeringService

def test_chronological_purging(db):
    feat_service = FeatureEngineeringService(db)

    # Synthetic dataframe with 100 days
    dates = [datetime.datetime(2026, 1, 1) + datetime.timedelta(days=i) for i in range(100)]
    df = pd.DataFrame({
        "date": dates,
        "symbol": ["RELIANCE"] * 100,
        "feature_1": np.random.randn(100),
        "target_direction": np.random.choice([0, 1], size=100),
    })

    horizon = 5
    test_size = 0.2
    train_df, test_df = feat_service.split_chronological_purged(
        df, test_size=test_size, horizon=horizon, purge_overlap=True
    )

    # Total test rows = 20
    assert len(test_df) == 20
    # Train rows = 80 - 5 purged = 75
    assert len(train_df) == 75

    # Check temporal separation: last train date must be strictly earlier than first test date minus horizon
    last_train_date = train_df["date"].max()
    first_test_date = test_df["date"].min()
    assert (first_test_date - last_train_date).days > horizon
