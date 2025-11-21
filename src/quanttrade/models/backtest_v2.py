"""
QUANT-TRADE — SLIDING WINDOW ALPHA BACKTEST (M1 ONLY)
+ Inverse Volatility Weighting
+ 5% Stop-Loss
+ Market Regime Filter (bist100 MA200)
"""

import warnings
warnings.filterwarnings("ignore")

import os
import glob
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from catboost import CatBoostClassifier

from train_model_20d import SectorStandardScaler, FeatureNeutralizer

# ==========================
# CONFIG
# ==========================

DATA_PATH = "master_df.csv"

RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_alpha_20d"

SYMBOL_COL = "symbol"
DATE_COL = "date"

HORIZON = 20
FUT_RET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_RET_COL = f"market_future_return_{HORIZON}d"

TOP_K = 5
MIN_TURNOVER_TL = 5_000_000
RET_CAP = 0.5
STOP_LOSS = -0.05                 # -5% stop loss
REGIME_FILTER_COL = "macro_bist100_distance_ma200"  # MA200 üzerinde mi? (>0 = üzerinde)
ROUNDTRIP_COST = 0.001            # %0.1 total roundtrip
PRICE_COL = "price_close"
VOLUME_COL = "price_volume"


# ==========================
# UTILS
# ==========================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Aranan dosya yok: {pattern}")
    return max(files, key=os.path.getmtime)


# ==========================
# BACKTEST
# ==========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    # ------------------- M1 MODEL ---------------------
    model_path = get_latest(os.path.join(RESULTS_DIR, f"catboost_alpha{HORIZON}d_*.cbm"))
    neutralizer_path = get_latest(os.path.join(RESULTS_DIR, f"neutralizer_alpha{HORIZON}d_*.pkl"))

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(neutralizer_path)
    sector_scaler: SectorStandardScaler = meta["sector_scaler"]
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names: List[str] = meta["features"]

    # ------------------- DATA -------------------------
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    df = df[df["dataset_split"] == "test"].reset_index(drop=True)
    df = df.dropna(subset=[FUT_RET_COL, MARKET_FUT_RET_COL]).reset_index(drop=True)

    df["turnover_tl"] = df[PRICE_COL] * df[VOLUME_COL]
    df = df[df["turnover_tl"] >= MIN_TURNOVER_TL].reset_index(drop=True)

    # Preprocessing
    X = df[feature_names].copy().fillna(df[feature_names].median())
    sector = df["sector"].astype(str)

    X_s = sector_scaler.transform(X, sector)
    X_n = neutralizer.transform(X_s, pd.DataFrame(index=df.index), sector)

    # ------------------- M1 SCORE ---------------------
    df["score_m1"] = model.predict_proba(X_n)[:, 1]

    # Günlük Döngü
    dates = sorted(df[DATE_COL].unique())
    records = []

    print(f">> Sliding Window başlıyor ({len(dates)} gün)...")

    for dt in dates:
        day = df[df[DATE_COL] == dt]

        # 1) TOP_K adayları (pure M1)
        day = day.sort_values("score_m1", ascending=False).head(TOP_K)

        if len(day) < TOP_K:
            continue

        # 2) INVERSE VOLATILITY WEIGHTING
        # vol feature yoksa: 20 günlük vol (price_vol_20d)
        if "price_vol_20d" not in day.columns:
            print("⚠ price_vol_20d yok → equal weight kullanıyorum.")
            vol = np.ones(len(day))
        else:
            vol = day["price_vol_20d"].clip(lower=1e-6).values

        w = 1 / vol
        w = w / w.sum()

        # 3) STOP LOSS uygulaması
        fwd = day[FUT_RET_COL].clip(-RET_CAP, RET_CAP).values
        fwd = np.maximum(fwd, STOP_LOSS)   # -5% stop loss uygula

        # 4) MARKET REGIME FILTER (MA200)
        if REGIME_FILTER_COL in day.columns:
            # Eğer MA200 altında ise risk azalt
            if day[REGIME_FILTER_COL].iloc[0] < 0:
                w = w * 0.50
                w = w / w.sum()
        else:
            print("⚠ MA200 filtresi yok. Devre dışı.")

        # 5) NET RETURN
        gross_ret = np.sum(w * fwd)
        net_ret = gross_ret - ROUNDTRIP_COST

        # 6) MARKET RETURN
        mkt_ret = day[MARKET_FUT_RET_COL].clip(-RET_CAP, RET_CAP).mean()

        alpha_ret = net_ret - mkt_ret

        records.append({
            "rebalance_date": dt,
            "strategy_net_ret": net_ret,
            "market_ret": mkt_ret,
            "alpha_ret": alpha_ret,
            "weighted_hit_rate": float(np.sum(w * (fwd > 0)))
        })

    bt = pd.DataFrame(records)

    bt["strategy_equity"] = (1 + bt["strategy_net_ret"]).cumprod()
    bt["market_equity"] = (1 + bt["market_ret"]).cumprod()
    bt["alpha_equity"] = (1 + bt["alpha_ret"]).cumprod()

    # METRICS
    mean_strat = bt["strategy_net_ret"].mean()
    sharpe = mean_strat / (bt["strategy_net_ret"].std() + 1e-9)

    print("\n===== SLIDING WINDOW BACKTEST (M1 ONLY — WEIGHTED+STOPLOSS+REGIME) =====")
    print(f"Trade günleri: {len(bt)}")
    print(f"Ortalama net getiri: {mean_strat:.4f}")
    print(f"Sharpe: {sharpe:.2f}")
    print(f"Alpha>0 oranı: {(bt['alpha_ret'] > 0).mean():.2f}")

    # SAVE
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = f"{BACKTEST_DIR}/sliding_weighted_{ts}.csv"
    out_png = f"{BACKTEST_DIR}/sliding_weighted_{ts}.png"

    bt.to_csv(out_csv, index=False)

    plt.figure(figsize=(10,5))
    plt.plot(bt["rebalance_date"], bt["strategy_equity"], label="Strategy")
    plt.plot(bt["rebalance_date"], bt["market_equity"], label="Market")
    plt.plot(bt["rebalance_date"], bt["alpha_equity"], label="Alpha")
    plt.yscale("log")
    plt.legend()
    plt.title("SLIDING BACKTEST — WEIGHTED + STOPLOSS + REGIME FILTER")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()


if __name__ == "__main__":
    main()
