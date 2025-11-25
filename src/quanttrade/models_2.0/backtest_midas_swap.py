"""
REALISTIC MIDAS-STYLE BACKTEST (T+1, SWAP, SLIPPAGE)

- Universe: master_df.csv (dataset_split == "test")
- Model: CatBoost alpha_20d + SectorStandardScaler
- Strategy:
    * Max 5 positions
    * Stop-loss: -5% (gap + intraday low)
    * Horizon: 20 days (TIME_EXIT, T+1 open)
    * SWAP: günde max 2 slot
        - Portföyün en kötü skorlu hisseleri
        - Modelin en iyi skorlu hisseleri
        - Skor farkı >= 0.05 (5 puan)
    * Execution: T+1 OPEN (Midas'ta ertesi gün piyasa emri gibi)
    * Slippage:
        - BUY: +1% (OPEN * 1.01)
        - SELL: -0.5% (OPEN * 0.995)
    * Commission: 0.2% (alım + satım dahil her işlemde)
"""

import os
import glob
from typing import List, Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from catboost import CatBoostClassifier

from train_model import SectorStandardScaler

# ============================
# CONFIG
# ============================

DATA_PATH   = "master_df.csv"
RESULTS_DIR = "model_results_alpha_20d"
BACKTEST_DIR = "backtest_results_midas_swap"

HORIZON_DAYS   = 20
STOP_LOSS_PCT  = -0.05       # -5%
MAX_POSITIONS  = 5

SWAP_LIMIT     = 2           # günde max 2 swap
SWAP_GAP       = 0.05        # skor farkı eşiği (best_score - worst_score)

INITIAL_CAPITAL = 100_000
COMMISSION      = 0.002      # binde 2

SLIPPAGE_BUY  = 0.01         # +%1
SLIPPAGE_SELL = 0.005        # -%0.5

TOP_K = 5               # modelin baktığı en iyi K aday (portföyde olmayanlardan SWAP için)

PRICE_COL  = "price_close"
OPEN_COL   = "price_open"
LOW_COL    = "price_low"
HIGH_COL   = "price_high"
DATE_COL   = "date"
SYMBOL_COL = "symbol"
SECTOR_COL = "sector"


# ============================
# HELPERS
# ============================

def get_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_model_and_meta():
    model_path = get_latest(os.path.join(RESULTS_DIR, "catboost_alpha20d_*.cbm"))
    meta_path  = get_latest(os.path.join(RESULTS_DIR, "neutralizer_alpha20d_*.pkl"))

    if model_path is None or meta_path is None:
        raise FileNotFoundError("Model veya meta dosyaları bulunamadı.")

    model = CatBoostClassifier()
    model.load_model(model_path)

    meta = joblib.load(meta_path)
    return model, meta


def compute_stop_loss(entry_price: float, row: pd.Series):
    """
    Gerçekçi SL:
    - stop_level = entry * (1 + STOP_LOSS_PCT)
    - Eğer OPEN <= stop_level → gap-stop → OPEN'dan çık
    - Yoksa LOW <= stop_level → tam stop_level'den çık
    - Diğer durumda stop tetiklenmez
    """
    stop_level = entry_price * (1.0 + STOP_LOSS_PCT)
    today_open = row[OPEN_COL]
    today_low  = row[LOW_COL]

    if today_low <= stop_level:
        if today_open <= stop_level:
            exit_raw = today_open
        else:
            exit_raw = stop_level
        return True, exit_raw, "STOP_LOSS"

    return False, None, None


# ============================
# MAIN BACKTEST
# ============================

def main():
    os.makedirs(BACKTEST_DIR, exist_ok=True)

    print(">> Loading model & data...")
    model, meta = load_model_and_meta()
    scaler: SectorStandardScaler = meta["sector_scaler"]
    features = meta["features"]

    df = pd.read_csv(DATA_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])

    # Feature matrix
    X = df[features].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(df[features].median())
    sector = df[SECTOR_COL].astype(str)

    Xs = scaler.transform(X, sector)
    df["score"] = model.predict_proba(Xs)[:, 1]

    # Sadece test dönemi
    test = df[df["dataset_split"] == "test"].copy()
    test = test.sort_values(DATE_COL).reset_index(drop=True)

    grouped = test.groupby(DATE_COL)
    dates = sorted(test[DATE_COL].unique())

    # ============================
    # STATE
    # ============================

    cash = INITIAL_CAPITAL

    # Aktif pozisyonlar:
    # { "symbol", "entry_date", "entry_price", "shares", "days_held" }
    portfolio: List[Dict] = []

    # Bekleyen emirler (T+1 işlenecek):
    # SELL: {"type": "SELL", "symbol", "target_date", "reason"}
    # BUY:  {"type": "BUY", "symbol", "target_date", "capital", "reason"}
    pending_orders: List[Dict] = []

    equity_curve = []
    trade_log = []

    print(f">> Running backtest over {len(dates)} days...")

    for i, dt in enumerate(dates):
        day = grouped.get_group(dt).set_index(SYMBOL_COL)

        # ============================
        # 1) BEKLEYEN EMİRLERİ T+1 OPEN'DA İŞLE
        # ============================

        new_pending = []
        for order in pending_orders:
            if order["target_date"] != dt:
                new_pending.append(order)
                continue

            sym = order["symbol"]
            if sym not in day.index:
                # Hisse bugün işlem görmüyorsa emir beklemeye devam etsin
                new_pending.append(order)
                continue

            open_raw = day.loc[sym, OPEN_COL]

            if order["type"] == "SELL":
                # Pozisyonu bul
                pos_idx = None
                for idx_p, p in enumerate(portfolio):
                    if p["symbol"] == sym:
                        pos_idx = idx_p
                        break
                if pos_idx is None:
                    # Zaten stop olmuş vs. olabilir, görmezden gel
                    continue

                pos = portfolio[pos_idx]
                entry_price = pos["entry_price"]
                shares = pos["shares"]

                exit_gross = open_raw * (1.0 - SLIPPAGE_SELL)
                revenue = shares * exit_gross
                net_revenue = revenue * (1.0 - COMMISSION)
                cash += net_revenue

                ret = exit_gross / entry_price - 1.0

                trade_log.append({
                    "entry_date": pos["entry_date"],
                    "exit_date": dt,
                    "symbol": sym,
                    "entry_price": entry_price,
                    "exit_price": exit_gross,
                    "shares": shares,
                    "return": ret,
                    "reason": order.get("reason", "PLANNED_EXIT"),
                    "days_held": pos["days_held"]
                })

                portfolio.pop(pos_idx)

            elif order["type"] == "BUY":
                capital = order["capital"]

                entry_gross = open_raw * (1.0 + SLIPPAGE_BUY)
                shares = int(capital / entry_gross)
                if shares <= 0:
                    continue

                cost = shares * entry_gross
                net_cost = cost * (1.0 + COMMISSION)

                if net_cost > cash:
                    continue

                cash -= net_cost

                portfolio.append({
                    "symbol": sym,
                    "entry_date": dt,
                    "entry_price": entry_gross,
                    "shares": shares,
                    "days_held": 0
                })

                trade_log.append({
                    "entry_date": dt,
                    "exit_date": None,
                    "symbol": sym,
                    "entry_price": entry_gross,
                    "exit_price": None,
                    "shares": shares,
                    "return": None,
                    "reason": order.get("reason", "ENTRY"),
                    "days_held": 0
                })

        pending_orders = new_pending

        # ============================
        # 2) STOP-LOSS (BUGÜNÜN OHLC'YE GÖRE)
        # ============================

        for idx_p in range(len(portfolio) - 1, -1, -1):
            pos = portfolio[idx_p]
            sym = pos["symbol"]

            if sym not in day.index:
                # Veri yoksa sadece gün sayısını artır
                pos["days_held"] += 1
                continue

            row = day.loc[sym]
            entry_price = pos["entry_price"]

            hit, exit_raw, reason = compute_stop_loss(entry_price, row)

            if hit:
                exit_gross = exit_raw * (1.0 - SLIPPAGE_SELL)
                revenue = pos["shares"] * exit_gross
                net_revenue = revenue * (1.0 - COMMISSION)
                cash += net_revenue

                ret = exit_gross / entry_price - 1.0

                trade_log.append({
                    "entry_date": pos["entry_date"],
                    "exit_date": dt,
                    "symbol": sym,
                    "entry_price": entry_price,
                    "exit_price": exit_gross,
                    "shares": pos["shares"],
                    "return": ret,
                    "reason": reason,
                    "days_held": pos["days_held"]
                })

                portfolio.pop(idx_p)
            else:
                pos["days_held"] += 1

        # ============================
        # 3) GÜNLÜK EQUITY (KAPANIŞ FİYATIYLA MTM)
        # ============================

        port_val = 0.0
        for p in portfolio:
            sym = p["symbol"]
            if sym in day.index:
                px = day.loc[sym, PRICE_COL]
            else:
                px = p["entry_price"]
            port_val += p["shares"] * px

        total_equity = cash + port_val
        equity_curve.append({"date": dt, "equity": total_equity})

        # Son gün ise yeni emir planlama
        if i == len(dates) - 1:
            continue

        next_dt = dates[i + 1]

        # ============================
        # 4) YARIN İÇİN EXIT PLANLAMA (TIME_EXIT + SWAP)
        # ============================

        day_sorted = day.sort_values("score", ascending=False)

        # Mevcut pozisyon skorları (bugünkü skor)
        pos_scores = []
        for p in portfolio:
            sym = p["symbol"]
            if sym in day.index:
                sc = float(day.loc[sym, "score"])
            else:
                sc = -999.0
            pos_scores.append((p, sc))

        pos_scores.sort(key=lambda x: x[1])  # en kötü başa

        symbols_in_port = {p["symbol"] for p in portfolio}

        # SWAP adayları: portföyde olmayan en iyi TOP_K
        best_candidates = []
        for sym, row in day_sorted.head(TOP_K).iterrows():
            if sym in symbols_in_port:
                continue
            best_candidates.append((sym, float(row["score"])))

        # EXIT / SWAP planlama
        sell_symbols = set()      # aynı sembole 2 kere SELL yazmamak için
        time_exit_symbols = set()
        swap_sell_symbols = set()

        # TIME EXIT: HORIZON dolanları yarın açılışta sat
        for p in portfolio:
            if p["days_held"] >= HORIZON_DAYS:
                sym = p["symbol"]
                if sym in sell_symbols:
                    continue
                sell_symbols.add(sym)
                time_exit_symbols.add(sym)

        # Pair bazlı SWAP planlama
        # (worst_pos, worst_score) ↔ (best_sym, best_score)
        max_swaps = min(SWAP_LIMIT, len(pos_scores), len(best_candidates))
        swap_pairs = []
        used_worst = set()
        used_best = set()
        
        for k in range(max_swaps):
            if k >= len(pos_scores) or k >= len(best_candidates):
                break
                
            worst_pos, worst_score = pos_scores[k]
            best_sym, best_score = best_candidates[k]

            if best_score - worst_score < SWAP_GAP:
                continue
            if worst_pos["symbol"] in used_worst:
                continue
            if best_sym in used_best:
                continue
            if worst_pos["symbol"] in time_exit_symbols:
                continue  # TIME_EXIT ile zaten çıkacak
                
            used_worst.add(worst_pos["symbol"])
            used_best.add(best_sym)
            swap_pairs.append((worst_pos, best_sym))

        # SWAP için SELL emirleri
        for worst_pos, best_sym in swap_pairs:
            worst_sym = worst_pos["symbol"]
            if worst_sym in sell_symbols:
                continue  # Zaten TIME_EXIT ile işaretlenmiş
            sell_symbols.add(worst_sym)
            swap_sell_symbols.add(worst_sym)

        # Tüm SELL emirlerini yaz
        for sym in sell_symbols:
            pending_orders.append({
                "type": "SELL",
                "symbol": sym,
                "target_date": next_dt,
                "reason": "TIME_EXIT" if sym in time_exit_symbols else "SWAP"
            })

        # SWAP BUY emirleri
        for worst_pos, best_sym in swap_pairs:
            worst_sym = worst_pos["symbol"]
            # Sermaye tahmini: bugünkü kapanış değeri
            if worst_sym in day.index:
                est_capital = worst_pos["shares"] * float(day.loc[worst_sym, PRICE_COL])
            else:
                # Veri yoksa entry fiyatından tahmin et
                est_capital = worst_pos["shares"] * worst_pos["entry_price"]

            pending_orders.append({
                "type": "BUY",
                "symbol": best_sym,
                "target_date": next_dt,
                "capital": est_capital,
                "reason": "SWAP_ENTRY"
            })

        # ============================
        # 5) YENİ ENTRY PLANLAMA (BOŞ SLOT VARSA)
        # ============================

        # Yarının pozisyon sayısı ~ şu anki pozisyon sayısı - time_exit sayısı
        positions_tomorrow = len(portfolio) - len(time_exit_symbols)
        free_slots = max(0, MAX_POSITIONS - positions_tomorrow)

        if free_slots > 0:
            # Şu an portföyde olan + swap ile alınacak sembolleri hariç tut
            symbols_blocked = symbols_in_port.union(
                {pair[1] for pair in swap_pairs}
            )

            # Adaylar: bugünkü en yüksek skorlu hisseler
            extra_candidates = []
            for sym, row in day_sorted.iterrows():
                if sym in symbols_blocked:
                    continue
                extra_candidates.append(sym)
                if len(extra_candidates) >= free_slots:
                    break

            if extra_candidates:
                # Bugünkü nakdi eşit bölüyoruz
                capital_per_trade = cash / free_slots if free_slots > 0 else 0.0

                for sym in extra_candidates:
                    pending_orders.append({
                        "type": "BUY",
                        "symbol": sym,
                        "target_date": next_dt,
                        "capital": capital_per_trade,
                        "reason": "ENTRY"
                    })

    # ============================
    # RAPORLAMA
    # ============================

    bt = pd.DataFrame(equity_curve)
    tr = pd.DataFrame(trade_log)

    if not bt.empty:
        initial = INITIAL_CAPITAL
        final = bt["equity"].iloc[-1]
        total_ret = final / initial - 1.0

        daily_ret = bt["equity"].pct_change().dropna()
        if len(daily_ret) > 1:
            mu = daily_ret.mean()
            sigma = daily_ret.std() + 1e-12
            sharpe_daily = mu / sigma
            sharpe_annual = sharpe_daily * np.sqrt(252)
        else:
            sharpe_annual = np.nan

        cagr = (final / initial) ** (252 / len(bt)) - 1.0

        print("\n===== MIDAS SWAP BACKTEST RESULT =====")
        print(f"Initial: {initial:,.2f} | Final: {final:,.2f}")
        print(f"Total Return: {total_ret:.2%}")
        print(f"CAGR: {cagr:.2%}")
        print(f"Annual Sharpe: {sharpe_annual:.2f}")
        print(f"Total Trades: {len(tr)}")
    else:
        print("Equity curve boş, muhtemelen veri/sinyal yok.")

    out_curve  = os.path.join(BACKTEST_DIR, "midas_swap_equity.csv")
    out_trades = os.path.join(BACKTEST_DIR, "midas_swap_trades.csv")
    out_png    = os.path.join(BACKTEST_DIR, "midas_swap_equity.png")

    bt.to_csv(out_curve, index=False)
    tr.to_csv(out_trades, index=False)

    if not bt.empty:
        plt.figure(figsize=(10, 5))
        plt.plot(bt["date"], bt["equity"], label="Equity")
        plt.title("Midas-Style Swap Backtest Equity")
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_png)
        plt.close()

    print(f"\nSaved equity to: {out_curve}")
    print(f"Saved trades to: {out_trades}")
    if not bt.empty:
        print(f"Saved equity plot to: {out_png}")


if __name__ == "__main__":
    main()
