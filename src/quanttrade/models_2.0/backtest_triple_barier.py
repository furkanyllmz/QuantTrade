"""
QUANT-TRADE — LONG-ONLY BACKTEST (TRIPLE-BARRIER EXIT)
Zero Lookahead — Horizon Shift — True Neutralization — NO SHORT
STOP-LOSS: KAPALI (sadece 20 günlük gerçek getiriler, cap uygulanıyor)
"""

import warnings
warnings.filterwarnings("ignore")

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
from catboost import CatBoostClassifier
import matplotlib.pyplot as plt
import glob

from train_model import SectorStandardScaler, FeatureNeutralizer

# ============================================================
# CONFIG
# ============================================================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_alpha_20d"

SYMBOL_COL = "symbol"
DATE_COL = "date"
SECTOR_COL = "sector"

HORIZON = 20
TARGET_COL = f"future_return_{HORIZON}d"
MARKET_FUT_COL = f"market_future_return_{HORIZON}d"

TOP_K = 5
MIN_TURNOVER_TL = 5_000_000
RET_CAP = 0.50

# STOP_LOSS artık kullanılmıyor, sadece ileride lazım olursa diye bırakıyorum
STOP_LOSS = -0.03
ROUNDTRIP_COST = 0.001

REGIME_COL = "macro_bist100_distance_ma200"
HARD_BEAR_THRESHOLD = -0.02

PRICE_COL = "price_close"
VOLUME_COL = "price_volume"


# ============================================================
# UTILS
# ============================================================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"Dosya bulunamadı: {pattern}")
    return max(files, key=os.path.getmtime)


# ============================================================
# HORIZON SHIFT
# ============================================================

def build_horizon_shifted(df, horizon):
    df = df.copy()
    df["model_date"] = df[DATE_COL]
    df["return_date"] = df[DATE_COL] + pd.Timedelta(days=horizon)

    fut = df[[SYMBOL_COL, DATE_COL, TARGET_COL]]
    fut = fut.rename(columns={DATE_COL: "return_date", TARGET_COL: "future_ret_h"})

    m = df.merge(fut, on=["symbol", "return_date"], how="left")
    m = m.dropna(subset=["future_ret_h"])
    return m.reset_index(drop=True)


# ============================================================
# MAIN BACKTEST — LONG ONLY, NO STOP-LOSS
# ============================================================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    # --- Load model ---
    model_path = get_latest(os.path.join(RESULTS_DIR, f"catboost_alpha{HORIZON}d_*.cbm"))
    neutral_path = get_latest(os.path.join(RESULTS_DIR, f"neutralizer_alpha{HORIZON}d_*.pkl"))

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(neutral_path)
    sector_scaler: SectorStandardScaler = meta["sector_scaler"]
    neutralizer: FeatureNeutralizer = meta["neutralizer"]
    feature_names = meta["features"]
    factors_train = meta["factors"]
    sector_train = meta["sector"]

    # --- Load test data ---
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    test = df[df["dataset_split"] == "test"].reset_index(drop=True)

    test = build_horizon_shifted(test, HORIZON)

    # liquidity filter
    test["turnover"] = test[PRICE_COL] * test[VOLUME_COL]
    test = test[test["turnover"] >= MIN_TURNOVER_TL].reset_index(drop=True)

    # preprocess
    X = test[feature_names].replace([np.inf, -np.inf], np.nan).fillna(test[feature_names].median())
    sector_test = test[SECTOR_COL].astype(str)

    factors_test = pd.DataFrame(
        np.zeros((len(test), factors_train.shape[1])),
        columns=factors_train.columns
    )

    Xs = sector_scaler.transform(X, sector_test)
    Xn = neutralizer.transform(Xs, factors_test, sector_test)

    test["score"] = model.predict_proba(Xn)[:, 1]

    dates = sorted(test["model_date"].unique())

    daily_log = []
    trade_log = []

    print(f">> BACKTEST BAŞLIYOR — {len(dates)} gün (LONG-ONLY, NO STOP-LOSS)")

    for dt in dates:
        day = test[test["model_date"] == dt].copy()
        if len(day) == 0:
            continue

        # LONG-ONLY: sadece top-K long seç
        day = day.sort_values("score", ascending=False).head(TOP_K)

        # inverse-vol weight
        if "price_vol_20d" in day:
            vol = day["price_vol_20d"].clip(lower=1e-6).values
        else:
            vol = np.ones(len(day))

        w = 1.0 / vol
        w = w / w.sum()

        # --- LONG RETURN (NO SHORT, NO STOP-LOSS) ---
        fut_raw = day["future_ret_h"].values        # gerçek 20g getiriler
        fut_cap = np.clip(fut_raw, -RET_CAP, RET_CAP)  # sadece cap

        # STOP-LOSS KAPALI: doğrudan cap'lenmiş future return'u kullan
        fut_eff = fut_cap

        # regime filter
        regime_val = day[REGIME_COL].iloc[0]
        risk = 1.0
        if regime_val <= HARD_BEAR_THRESHOLD:
            # sert ayı → hiç trade alma
            continue
        elif regime_val < 0:
            # hafif ayı → yarım risk
            risk = 0.5

        gross = float(np.sum(w * fut_eff)) * risk
        net = gross - ROUNDTRIP_COST * risk

        mkt_ret = float(day[MARKET_FUT_COL].mean())
        alpha = net - np.clip(mkt_ret, -RET_CAP, RET_CAP)

        daily_log.append({
            "date": dt,
            "strategy_ret": net,
            "market_ret": mkt_ret,
            "alpha_ret": alpha,
            "risk": risk,
            "hit_rate": float(np.sum(w * (fut_eff > 0)))
        })

        exit_date = dt + timedelta(days=HORIZON)
        for (_, row), weight, fr_raw, fr_eff in zip(day.iterrows(), w, fut_raw, fut_eff):
            trade_log.append({
                "entry": dt,
                "exit_est": exit_date,
                "symbol": row[SYMBOL_COL],
                "weight": float(weight),
                "future_raw": float(fr_raw),
                "future_eff": float(fr_eff)
            })

    # ---------- RESULTS ----------
    bt = pd.DataFrame(daily_log).sort_values("date").reset_index(drop=True)

    # smooth daily compounding
    bt["equity"] = ((1 + bt["strategy_ret"]) ** (1 / HORIZON)).cumprod()
    bt["market_equity"] = ((1 + bt["market_ret"]) ** (1 / HORIZON)).cumprod()
    bt["alpha_equity"] = ((1 + bt["alpha_ret"]) ** (1 / HORIZON)).cumprod()

    # ---------- METRICS ----------
    def metrics(bt):
        r = bt["strategy_ret"].values  # 20 günlük blok getiriler

        mu = r.mean()
        sigma = r.std() + 1e-12

        sharpe_20 = mu / sigma
        sharpe_ann = np.sqrt(252 / HORIZON) * sharpe_20
        annual_ret = (1 + mu) ** (252 / HORIZON) - 1

        eq = bt["equity"].values
        roll = np.maximum.accumulate(eq)
        dd = (eq - roll) / roll
        max_dd = dd.min()

        return {
            "blocks": len(r),
            "Sharpe_20d": sharpe_20,
            "Sharpe_annual": sharpe_ann,
            "Annual_return": annual_ret,
            "MaxDD": max_dd,
            "Mean20d": mu,
            "Std20d": sigma,
            "HitRate": (r > 0).mean()
        }

    m = metrics(bt)

    print("\n===== LONG-ONLY PERFORMANCE (NO STOP-LOSS) =====")
    for k, v in m.items():
        print(f"{k}: {v}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    bt.to_csv(f"{BACKTEST_DIR}/bt_longonly_nosl_{ts}.csv", index=False)
    pd.DataFrame(trade_log).to_csv(f"{BACKTEST_DIR}/trades_longonly_nosl_{ts}.csv", index=False)
    pd.DataFrame([m]).to_csv(f"{BACKTEST_DIR}/metrics_longonly_nosl_{ts}.csv", index=False)

    plt.figure(figsize=(10, 5))
    plt.plot(bt["date"], bt["equity"], label="Strategy")
    plt.plot(bt["date"], bt["market_equity"], label="Market")
    plt.plot(bt["date"], bt["alpha_equity"], label="Alpha")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{BACKTEST_DIR}/equity_longonly_nosl_{ts}.png")
    plt.close()

    print("\n>> LONG-ONLY BACKTEST (NO STOP-LOSS) COMPLETED ✔️")


if __name__ == "__main__":
    main()
