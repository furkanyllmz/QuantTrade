"""
REALISTIC DAILY BACKTEST ENGINE (LONG-ONLY)
Stop-Loss: Realistic (Gap + Intraday Low Check)
Horizon: 20 Days
Execution: T+1
"""

import pandas as pd
import numpy as np
from datetime import timedelta
import joblib
from catboost import CatBoostClassifier
import glob
import os
import matplotlib.pyplot as plt
from train_model import SectorStandardScaler, FeatureNeutralizer

# ========================
# CONFIG
# ========================

DATA_PATH = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_realistic"

HORIZON = 20
TOP_K = 5

RET_CAP = 0.10        # günlük max clamp
STOP_LOSS_PCT = -0.05 # stop-loss seviyesi (5% zarar)

PRICE_COL   = "price_close"
OPEN_COL    = "price_open"
LOW_COL     = "price_low"
HIGH_COL    = "price_high"
SYMBOL_COL  = "symbol"
DATE_COL    = "date"
SECTOR_COL  = "sector"

REGIME_COL = "macro_bist100_distance_ma200"
HARD_BEAR_THRESHOLD = -0.02

# Market benchmark günlük getirisi (master_df'deki kolona göre ayarla)
MARKET_RET_COL = "macro_bist100_roc_1d"


# ========================
# HELPERS
# ========================

def get_latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime)


# ========================
# GÜNLÜK STOP-LOSS KONTROLÜ
# ========================

def compute_realistic_stop(entry_price, sl_pct, next_open, next_low):
    """
    entry_price = pozisyon açıldığı kapanış fiyatı
    sl_pct = ör. -0.05 (stop-loss %5)
    next_open = ertesi gün açılış
    next_low = ertesi gün gün içi en düşük fiyat

    Stop mantığı:
      1) Eğer next_open SL seviyesinin altındaysa → gap-stop → open üzerinden zarar
      2) Eğer next_low SL seviyesini görmüşse → SL seviyesi üzerinden zarar
      3) Aksi halde stop tetiklenmez → None döner
    """

    stop_level = entry_price * (1 + sl_pct)

    # 1) GAP OPEN STOP
    if next_open <= stop_level:
        return next_open / entry_price - 1

    # 2) INTRADAY LOW STOP
    if next_low <= stop_level:
        return stop_level / entry_price - 1

    # 3) STOP TETİKLEMEZ
    return None


# ========================
# LOAD MODEL
# ========================

def load_model_and_meta():
    model_path = get_latest(os.path.join(RESULTS_DIR, f"catboost_alpha20d_*.cbm"))
    neutral_path = get_latest(os.path.join(RESULTS_DIR, f"neutralizer_alpha20d_*.pkl"))

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(neutral_path)
    return model, meta


# ========================
# MAIN BACKTEST
# ========================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    print(">> Loading model...")
    model, meta = load_model_and_meta()
    sector_scaler = meta["sector_scaler"]
    neutralizer = meta["neutralizer"]
    feature_names = meta["features"]
    factors_train = meta["factors"]

    print(">> Loading data...")
    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    # = future return 1d ekle (şimdilik engine’de direkt kullanılmıyor ama dursun)
    df["fut_1d"] = (
        df.groupby(SYMBOL_COL)[PRICE_COL].shift(-1) / df[PRICE_COL] - 1
    )

    # feature matrix
    X = df[feature_names].replace([np.inf, -np.inf], np.nan).fillna(df[feature_names].median())
    sector = df[SECTOR_COL].astype(str)

    # >>> MAKRO FAKTÖRLERİ DOĞRU ŞEKİLDE ÇEK
    factors_test = df[factors_train.columns].copy()
    factors_test = factors_test.fillna(0).replace([np.inf, -np.inf], 0)

    Xs = sector_scaler.transform(X, sector)
    Xn = neutralizer.transform(Xs, factors_test, sector)

    df["score"] = model.predict_proba(Xn)[:, 1]

    # sadece test dönemi
    test = df[df["dataset_split"] == "test"].copy()
    test = test.reset_index(drop=True)

    dates = sorted(test[DATE_COL].unique())
    daily_equity = []
    trade_log = []

    equity = 1.0
    max_equity = 1.0
    drawdowns = []

    print(f">> Starting REALISTIC backtest over {len(dates)} days")

    for dt in dates:
        day = test[test[DATE_COL] == dt].copy()
        if len(day) == 0:
            continue

        # Top-K seçim
        day = day.sort_values("score", ascending=False).head(TOP_K)

        # inverse vol weight
        if "price_vol_20d" in day.columns:
            vol = day["price_vol_20d"].clip(lower=1e-6).values
        else:
            vol = np.ones(len(day))

        w = (1 / vol)
        w = w / w.sum()  # önce normalize

        # MAX WEIGHT CAP → fazla riskli tekil pozisyonları kırp
        MAX_WEIGHT = 0.20   # Tek hisse max %20
        w = np.minimum(w, MAX_WEIGHT)
        # normalize ETMİYORUZ → kalan pay nakitte

        total_ret = 0.0

        for (_, row), weight in zip(day.iterrows(), w):
            sym = row[SYMBOL_COL]
            entry_price = row[PRICE_COL]

            # ertesi gün verisi
            t1 = test[(test[SYMBOL_COL] == sym) &
                      (test[DATE_COL] == dt + timedelta(days=1))]

            if len(t1) == 0:
                continue  # ertesi gün yok → trade yok

            nxt = t1.iloc[0]
            next_open = nxt[OPEN_COL]
            next_low = nxt[LOW_COL]
            next_close = nxt[PRICE_COL]

            # 1) STOP KONTROLÜ
            stop_ret = compute_realistic_stop(
                entry_price,
                STOP_LOSS_PCT,
                next_open,
                next_low
            )

            if stop_ret is not None:
                ret = stop_ret
            else:
                # 2) STOP TETİKLENMEDİ → normal daily PnL (close-to-close)
                ret = next_close / entry_price - 1

            # CAP
            ret = np.clip(ret, -RET_CAP, RET_CAP)

            total_ret += ret * weight

            trade_log.append({
                "entry_date": dt,
                "symbol": sym,
                "weight": weight,
                "entry": entry_price,
                "exit": next_close,
                "stop_hit": stop_ret is not None,
                "return": ret
            })

        # === MARKET GÜNLÜK GETİRİSİ ===
        # Aynı tarihteki BIST100 getirisi; semboller arasında aynı olacağı için mean alıyoruz.
        day_mkt_ret = day[MARKET_RET_COL].mean()
        alpha_ret = total_ret - day_mkt_ret

        # portföy PnL
        equity *= (1 + total_ret)

        max_equity = max(max_equity, equity)
        dd = equity / max_equity - 1
        drawdowns.append(dd)

        daily_equity.append({
            "date": dt,
            "equity": equity,
            "drawdown": dd,
            "pnl": total_ret,
            "market_ret": day_mkt_ret,
            "alpha_ret": alpha_ret
        })

    bt = pd.DataFrame(daily_equity)

    # ===== EQUITY CURVES =====
    bt["strategy_equity"] = (1 + bt["pnl"]).cumprod()
    bt["market_equity"]   = (1 + bt["market_ret"]).cumprod()
    bt["alpha_equity"]    = (1 + bt["alpha_ret"]).cumprod()

    # METRİKLER (strateji üzerinden)
    r = bt["pnl"].values
    mu = r.mean()
    sigma = r.std() + 1e-12
    sharpe_daily = mu / sigma
    sharpe_annual = sharpe_daily * np.sqrt(252)
    annual_return = (bt["strategy_equity"].iloc[-1] ** (252 / len(bt))) - 1
    max_dd = min(drawdowns)

    print("\n===== REALISTIC STOP-LOSS BACKTEST =====")
    print(f"Days: {len(bt)}")
    print(f"Sharpe (annual): {sharpe_annual:.2f}")
    print(f"Annual Return: {annual_return:.2%}")
    print(f"Max Drawdown: {max_dd:.2%}")
    print(f"Mean Daily Return: {mu:.4f}")
    print(f"Std Daily Return: {sigma:.4f}")

    # SAVE
    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")

    bt.to_csv(f"{BACKTEST_DIR}/realistic_bt_{ts}.csv", index=False)
    pd.DataFrame(trade_log).to_csv(f"{BACKTEST_DIR}/realistic_trades_{ts}.csv", index=False)

    plt.figure(figsize=(10,5))
    plt.plot(bt["date"], bt["strategy_equity"], label="Strategy")
    plt.plot(bt["date"], bt["market_equity"],   label="Market")
    plt.plot(bt["date"], bt["alpha_equity"],    label="Alpha")
    plt.title("REALISTIC Stop-Loss Engine Equity (Strategy vs Market vs Alpha)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{BACKTEST_DIR}/realistic_equity_{ts}.png")
    plt.close()

    print("\n>> Completed and saved.")


if __name__ == "__main__":
    main()
