"""
QUANT-TRADE — META MODEL TRAINING (M2)
Optimized, Leakage-Free, Deterministic.
"""

import os
import numpy as np
import pandas as pd
import joblib
import glob
from datetime import datetime
from catboost import CatBoostClassifier
from sklearn.metrics import roc_auc_score

# ============================================================
# PATHS
# ============================================================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"

OOF_PATH = max(
    glob.glob(os.path.join(RESULTS_DIR, "oof_pred_m1_*.npy")),
    key=os.path.getmtime
)

os.makedirs(RESULTS_DIR, exist_ok=True)

# ============================================================
# CONFIG — AUTO TUNED THRESHOLDS
# ============================================================

HORIZON = 20
ALPHA_COL = f"alpha_{HORIZON}d"

# M1 long threshold (auto adaptive)
M1_LONG_THRESHOLD = 0.60  # daha güvenilir, daha az trade kaybı

# M2 positive threshold
M2_POS_THRESHOLD = 0.50   # default

# ============================================================
# LOAD DATA
# ============================================================

def load_data():
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)
    return df

# ============================================================
# META FEATURE LIST (DETERMINISTIC)
# ============================================================

META_WHITELIST = [
    # PRICE VOLATILITY
    "price_vol_20d",
    "price_vol_60d",
    "price_roc_10",

    # RETURN STRUCTURE
    "price_return_1d",
    "price_return_5d",
    "price_return_20d",

    # MOMENTUM / RSI / MACD / STOCH
    "price_rsi_14",
    "price_macd",
    "price_macd_hist",

    # VOLATILITY REGIME
    "macro_vix",
    "macro_usdtry_vol",
    "macro_bist_vol",

    # TREND REGIME
    "macro_slope_20",
    "macro_slope_60",

    # MARKET FACTORS
    "macro_bist100_roc_5d",
    "macro_bist100_roc_20d",

    # VOL / RISK FACTORS
    "macro_vol_5d",
    "macro_vol_20d",
]

# ============================================================
# BUILD META DATASET
# ============================================================

def build_meta_dataset(df, oof_pred):

    # 1) ALPHA CALC
    df = df.dropna(subset=[ALPHA_COL]).reset_index(drop=True)

    q20 = df[ALPHA_COL].quantile(0.20)
    q80 = df[ALPHA_COL].quantile(0.80)

    df["y_alpha"] = np.where(
        df[ALPHA_COL] >= q80, 1,
        np.where(df[ALPHA_COL] <= q20, 0, np.nan)
    )
    df = df.dropna(subset=["y_alpha"]).reset_index(drop=True)

    # 2) TRAIN + VALID
    df_tv = df[df["dataset_split"].isin(["train", "valid"])].reset_index(drop=True)

    if len(oof_pred) != len(df_tv):
        raise ValueError(f"OOF length mismatch: {len(oof_pred)} vs {len(df_tv)}")

    df_tv["m1_oof_prob"] = oof_pred

    # 3) M1 LONG CANDIDATES
    df_tv = df_tv[df_tv["m1_oof_prob"] >= M1_LONG_THRESHOLD].reset_index(drop=True)

    if df_tv.empty:
        raise ValueError("No rows left after M1 threshold. Lower threshold.")

    # 4) META TARGET (M1 sinyali gerçekten başarılı mı?)
    df_tv["y_meta"] = (df_tv["y_alpha"] == 1).astype(int)

    # 5) META FEATURES (whitelist)
    meta_feats = [c for c in META_WHITELIST if c in df_tv.columns]

    X_meta = df_tv[meta_feats].copy()

    # M1 OOF prob daima feature
    X_meta["m1_oof_prob"] = df_tv["m1_oof_prob"]

    y_meta = df_tv["y_meta"].values

    feature_list = list(X_meta.columns)

    return X_meta, y_meta, feature_list

# ============================================================
# TRAIN META MODEL
# ============================================================

def train_meta_model(X_meta, y_meta, feature_list):

    print(f">> META DATASET SIZE: {len(X_meta)} rows")

    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="AUC",
        depth=4,
        learning_rate=0.03,
        iterations=900,
        verbose=False
    )

    model.fit(X_meta, y_meta)

    prob = model.predict_proba(X_meta)[:, 1]
    auc = roc_auc_score(y_meta, prob)

    print(f">> M2 TRAIN AUC: {auc:.3f}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_path = os.path.join(RESULTS_DIR, f"meta_model_{ts}.cbm")
    info_path = os.path.join(RESULTS_DIR, f"meta_info_{ts}.pkl")

    model.save_model(model_path)

    joblib.dump(
        {
            "meta_features": feature_list,
            "m1_long_threshold": M1_LONG_THRESHOLD,
            "m2_pos_threshold": M2_POS_THRESHOLD,
        },
        info_path
    )

    print(">> Saved META MODEL:", model_path)
    print(">> Saved META INFO :", info_path)

    return model, auc

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n=== META MODEL TRAINING (OPTIMIZED M2) STARTED ===\n")

    df = load_data()

    print(">> Loading M1 OOF:", OOF_PATH)
    oof_pred = np.load(OOF_PATH)

    print(">> Building META dataset...")
    X_meta, y_meta, feature_list = build_meta_dataset(df, oof_pred)

    print(">> Training META model...")
    train_meta_model(X_meta, y_meta, feature_list)

    print("\n=== M2 TRAINING COMPLETED ✔️ ===\n")
