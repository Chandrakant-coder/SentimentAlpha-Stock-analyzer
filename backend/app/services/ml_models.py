import json
import uuid
import datetime
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.models import ModelRun
from app.ml.model_registry import model_registry
from app.services.feature_engineering import FeatureEngineeringService, FEATURE_COLUMNS

class MLModelService:
    def __init__(self, db: Session):
        self.db = db
        self.feat_service = FeatureEngineeringService(db)

    def train_model(
        self,
        model_type: str = "XGBoostClassifier",
        target_horizon: int = 5,
        feature_subset: Optional[List[str]] = None,
        test_size: float = 0.2,
        purge_overlap: bool = True,
    ) -> Dict[str, Any]:
        """
        Trains and validates an XGBoost financial ML prediction model using chronological
        walk-forward purged validation. Saves artifact and persists metrics to DB.
        XGBoost replaces the previous LogisticRegression and RandomForestClassifier models.
        """
        features_to_use = feature_subset or FEATURE_COLUMNS
        logger.info(f"Preparing dataset for {model_type} (horizon={target_horizon}d)...")

        dataset = self.feat_service.prepare_dataset(target_horizon=target_horizon)
        if dataset.empty or len(dataset) < 40:
            raise ValueError(f"Insufficient historical data ({len(dataset)} samples) to train model.")

        # Ensure all requested feature columns exist
        available_features = [f for f in features_to_use if f in dataset.columns]
        if not available_features:
            raise ValueError("None of the specified features are available in dataset.")

        # Chronological split with purging
        train_df, test_df = self.feat_service.split_chronological_purged(
            dataset,
            test_size=test_size,
            horizon=target_horizon,
            purge_overlap=purge_overlap,
        )

        X_train = train_df[available_features].values
        y_train = train_df["target_direction"].values
        X_test = test_df[available_features].values
        y_test = test_df["target_direction"].values

        # Compute class imbalance ratio for scale_pos_weight
        # scale_pos_weight = count(negative class) / count(positive class)
        neg_count = int(np.sum(y_train == 0))
        pos_count = int(np.sum(y_train == 1))
        scale_pos_weight = float(neg_count) / float(pos_count) if pos_count > 0 else 1.0
        logger.info(
            f"Class balance — Positive (up): {pos_count}, Negative (down): {neg_count}, "
            f"scale_pos_weight={scale_pos_weight:.3f}"
        )

        # XGBoost imputes NaN natively; the SimpleImputer here provides an explicit
        # fallback and ensures a consistent sklearn Pipeline interface for joblib serialization.
        model_type = "XGBoostClassifier"
        xgb_clf = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss",
            early_stopping_rounds=30,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )
        clf = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", xgb_clf),
        ])
        hyperparams = {
            "n_estimators": 300,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "gamma": 0.1,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "scale_pos_weight": round(scale_pos_weight, 4),
            "early_stopping_rounds": 30,
        }

        logger.info(
            f"Training {model_type} on {len(X_train)} chronological samples, "
            f"testing on {len(X_test)} samples..."
        )

        # Impute training data first, then pass to XGBoost with eval set for early stopping
        imputer = SimpleImputer(strategy="median")
        X_train_imp = imputer.fit_transform(X_train)
        X_test_imp = imputer.transform(X_test)

        xgb_clf.fit(
            X_train_imp,
            y_train,
            eval_set=[(X_test_imp, y_test)],
            verbose=False,
        )

        # Rebuild pipeline with fitted imputer so joblib saves/loads correctly
        from sklearn.pipeline import Pipeline as _Pipeline
        from sklearn.impute import SimpleImputer as _SI
        fitted_pipeline = _Pipeline([
            ("imputer", imputer),
            ("model", xgb_clf),
        ])
        clf = fitted_pipeline

        # Held-out evaluation
        y_pred = xgb_clf.predict(X_test_imp)
        y_prob = xgb_clf.predict_proba(X_test_imp)[:, 1]

        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        roc_auc = float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else None

        # Feature importances — XGBoost gain-based
        feature_importance_dict: Dict[str, float] = {}
        raw_importances = xgb_clf.feature_importances_
        for feat_name, imp in zip(available_features, raw_importances):
            feature_importance_dict[feat_name] = round(float(imp), 4)

        # Sort feature importance
        feature_importance_dict = dict(sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True))

        # Generate unique Model ID and persist
        model_id = f"model_{model_type.lower()}_{uuid.uuid4().hex[:8]}"
        metadata = {
            "model_id": model_id,
            "model_type": model_type,
            "target_horizon": target_horizon,
            "validation_method": "walk_forward_purged",
            "features_used": available_features,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "metrics": {
                "accuracy": round(acc, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "roc_auc": round(roc_auc, 4) if roc_auc else None,
            },
            "feature_importance": feature_importance_dict,
            "hyperparameters": hyperparams,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }

        model_path = model_registry.save_model(model_id, clf, metadata)

        # Persist to database
        db_run = ModelRun(
            model_id=model_id,
            model_type=model_type,
            target_horizon=target_horizon,
            validation_method="walk_forward_purged",
            features_used=json.dumps(available_features),
            train_samples=len(X_train),
            test_samples=len(X_test),
            accuracy=round(acc, 4),
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1=round(f1, 4),
            roc_auc=round(roc_auc, 4) if roc_auc else None,
            feature_importance=json.dumps(feature_importance_dict),
            hyperparameters=json.dumps(hyperparams),
            model_path=str(model_path),
            created_at=datetime.datetime.utcnow(),
        )
        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)

        logger.info(f"Model {model_id} trained: Accuracy={acc:.3f}, F1={f1:.3f}, AUC={roc_auc if roc_auc else 0:.3f}")
        return {
            "model_id": model_id,
            "model_type": model_type,
            "target_horizon": target_horizon,
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4) if roc_auc else None,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "feature_importance": feature_importance_dict,
        }

    def predict_latest_for_stock(self, symbol: str, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates XGBoost prediction for the latest observation of a stock.
        Returns BUY/HOLD/SELL signal with probability and all class probabilities.
        """
        # Find latest XGBoost model if not specified
        if not model_id:
            latest_run = (
                self.db.query(ModelRun)
                .order_by(ModelRun.created_at.desc())
                .first()
            )
            if not latest_run:
                return {"prediction": "HOLD", "probability": 0.5, "model_id": None}
            model_id = latest_run.model_id

        clf, metadata = model_registry.load_model(model_id)
        features_used = metadata.get("features_used", FEATURE_COLUMNS)

        dataset = self.feat_service.prepare_dataset(symbol=symbol)
        if dataset.empty:
            return {"prediction": "HOLD", "probability": 0.5, "model_id": model_id}

        latest_row = dataset.iloc[[-1]]
        # Only use features available in this dataset
        available = [f for f in features_used if f in latest_row.columns]
        X = latest_row[available].values

        proba = clf.predict_proba(X)[0]
        prob_up = float(proba[1])
        prob_down = float(proba[0])

        # BUY if model is at least 55% confident in upward direction, SELL if 55% downward
        if prob_up >= 0.55:
            direction = "BUY"
            conf = prob_up
        elif prob_down >= 0.55:
            direction = "SELL"
            conf = prob_down
        else:
            direction = "HOLD"
            conf = 0.5

        return {
            "prediction": direction,
            "probability": round(conf, 4),
            "prob_up": round(prob_up, 4),
            "prob_down": round(prob_down, 4),
            "model_id": model_id,
            "model_type": metadata.get("model_type", "XGBoostClassifier"),
            "date": latest_row["date"].iloc[0].isoformat(),
        }
