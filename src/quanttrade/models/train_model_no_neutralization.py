"""
QUANT-TRADE — ALPHA 20D (NO NEUTRALIZATION VERSION)
Model trendi ve makroyu olduğu gibi öğrenir.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import os
import joblib
from datetime import datetime
import matplotlib.pyplot as plt

from dataclasses import dataclass
from typing import Optional

from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, roc_curve
from sklearn.model_selection import BaseCrossValidator

from catboost import CatBoostClassifier, Pool


# ============================
# CONFIG
# ============================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d_no_neutral"
os.makedirs(RESULTS_DIR, exist_ok=True)

SYMBOL_COL = "symbol"
DATE_COL = "date"
SECTOR_COL = "sector"

HORIZON = 20
FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"
ALPHA_COL = f"alpha_{HORIZON}d"


# ============================
# PURGED TIME SERIES SPLIT
# ============================

@dataclass
class PurgedTimeSeriesSplit(BaseCrossValidator):
    n_splits: int
    purge_window: int
    embargo_pct: float

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

    def split(self, X, y=None, groups=None):
        n = len(X)
        idx = np.arange(n)

        fold_sizes = np.full(self.n_splits, n // self.n_splits)
        fold_sizes[: n % self.n_splits] += 1

        start = 0
        for fold_size in fold_sizes:
            test_start = start
            test_end = start + fold_size
            start = test_end

            train_mask = np.ones(n, dtype=bool)

            purge_start = max(0, test_start - self.purge_window)
            train_mask[purge_start:test_end] = False

            embargo = int(n * self.embargo_pct)
            emb_start = test_end
            emb_end = min(n, test_end + embargo)
            train_mask[emb_start:emb_end] = False

            yield idx[train_mask], idx[test_start:test_end]


# ============================
# SECTOR Z-SCORE SCALER
# ============================

class SectorStandardScaler:
    def __init__(self):
        self.stats = {}

    def fit(self, X, sector):
        for sec in sector.unique():
            mask = sector == sec
            Xsec = X[mask]
            self.stats[sec] = {
                "mean": Xsec.mean(),
                "std": Xsec.std(ddof=0).replace(0, 1.0)
            }

    def transform(self, X, sector):
        Xout = X.copy()
        for sec, stats in self.stats.items():
            mask = sector == sec
            if not mask.any():
                continue
            Xout.loc[mask] = (X.loc[mask] - stats["mean"]) / stats["std"]
        return Xout


# ============================
# ALPHA TARGET
# ============================

def build_alpha(df):
    df[ALPHA_COL] = df[FUT_RET_COL] - df[MARKET_FUT_RET_COL]
    df = df.dropna(subset=[ALPHA_COL]).reset_index(drop=True)

    q20 = df[ALPHA_COL].quantile(0.20)
    q80 = df[ALPHA_COL].quantile(0.80)

    df["y_alpha"] = np.where(
        df[ALPHA_COL] >= q80, 1,
        np.where(df[ALPHA_COL] <= q20, 0, np.nan)
    )

    df = df.dropna(subset=["y_alpha"]).reset_index(drop=True)
    df["y_alpha"] = df["y_alpha"].astype(int)

    return df


# ============================
# FEATURE SELECTION
# ============================

def select_features(df):
    drop_cols = {
        SYMBOL_COL, DATE_COL, SECTOR_COL,
        FUT_RET_COL, MARKET_FUT_RET_COL,
        ALPHA_COL, "y_alpha"
    }

    drop_cols |= {c for c in df.columns if "future_" in c}
    drop_cols |= {c for c in df.columns if c.startswith("y_")}
    drop_cols |= {"price_open", "price_high", "price_low", "price_adj_close"}

    features = [c for c in df.columns if c not in drop_cols]
    X = df[features].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    return X, features


# ============================
# TRAIN PIPELINE
# ============================

def run_pipeline():

    print(">> Loading data...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    print(">> Building alpha...")
    df = build_alpha(df)

    df_tv = df[df["dataset_split"].isin(["train", "valid"])].reset_index(drop=True)

    X, feature_names = select_features(df_tv)
    y = df_tv["y_alpha"]

    sector = df_tv[SECTOR_COL].astype(str)

    print(">> Sector-based scaling...")
    scaler = SectorStandardScaler()
    scaler.fit(X, sector)
    Xs = scaler.transform(X, sector)

    X_mat = Xs.values
    y_vec = y.values

    print(">> Training model...")
    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=6,
        iterations=700,
        learning_rate=0.05,
        verbose=False
    )
    model.fit(Pool(Xs, y_vec))

    print(">> Saving model...")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = f"{RESULTS_DIR}/catboost_alpha20d_noneutral_{ts}.cbm"
    model.save_model(model_path)

    joblib.dump(
        {"scaler": scaler, "features": feature_names},
        f"{RESULTS_DIR}/meta_noneutral_{ts}.pkl"
    )

    print(">> DONE ✔")


if __name__ == "__main__":
    run_pipeline()
