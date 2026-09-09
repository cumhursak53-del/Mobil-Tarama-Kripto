# Strategy Fidelity Matrix

PDF otorite: `Yatırım ve Analiz/` | SMC otorite: LuxAlgo | İndikatör: TradingView

Durum: `done` = kodda uygulandı | `partial` = kısmen | `todo` = planlandı

| Kasa | PDF / Otorite | Mevcut kural | Durum | Dosya | Test |
|------|---------------|--------------|-------|-------|------|
| Kasa_RejimOsilator | indikatörler.pdf | 4H trend + hacim 3. oy, ağırlıklı oylama | done | strategies/rejim_osilator.py | tests/fidelity/test_golden_kasas.py |
| Kasa_PatlamaSelale | trentler.pdf | Retest, displacement ATR, kırılan seviye SL | done | engine/momentum_scan.py | tests/fidelity/test_golden_kasas.py |
| Kasa_TrendCizgisi | trentler.pdf | ≥3 dokunuş, invalidation | done | strategies/trend.py | tests/fidelity/test_golden_kasas.py |
| Kasa_PulbackRetest | alım satım yeri.pdf | Break→hold→retest state machine | done | strategies/trend.py | tests/fidelity/test_golden_kasas.py |
| Kasa_DUK | trentler.pdf | Apex, hacim düşüşü formation | done | strategies/trend.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Tuzak | alım satım yeri.pdf | Fitil/gövde oranı | done | strategies/trend.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Dominance | dominance PDF | btc_chg, total2, eth_btc filtresi | done | strategies/trend.py | tests/fidelity/test_golden_kasas.py |
| Kasa_SMA9_14 | HO.pdf | 4H trend filtresi | done | strategies/ma.py | tests/fidelity/test_golden_kasas.py |
| Kasa_EMA_Fib | HO.pdf + fibonacci.pdf | Fib 0.618 confluence | done | strategies/ma.py | tests/fidelity/test_golden_kasas.py |
| Kasa_DinamikMA | HO.pdf | Swing %38-61.8 depth | done | strategies/ma.py | tests/fidelity/test_golden_kasas.py |
| Kasa_PiyasaEvresi | PA.pdf | Wyckoff spring/upthrust hacim imzası | done | strategies/pa.py | tests/fidelity/test_golden_kasas.py |
| Kasa_MumOnay | PA.pdf | Pin bar, inside bar | done | strategies/pa.py | tests/fidelity/test_golden_kasas.py |
| Kasa_YapiKirilim | PA.pdf | Displacement + structure_event | done | strategies/pa.py | tests/fidelity/test_golden_kasas.py |
| Kasa_RSI_Uyumsuzluk | indikatörler.pdf | 3+ pivot, hidden divergence | done | structure/divergence.py | tests/fidelity/test_golden_kasas.py |
| Kasa_RSI_Bolge | indikatörler.pdf | Range stage only | done | strategies/oscillators.py | tests/fidelity/test_golden_kasas.py |
| Kasa_MACD | indikatörler.pdf | Zero-line, 4H align | done | strategies/oscillators.py | tests/fidelity/test_golden_kasas.py |
| Kasa_BB_Squeeze | indikatörler.pdf | TTM (BB inside KC) | done | strategies/oscillators.py | tests/fidelity/test_golden_kasas.py |
| Kasa_CCI | indikatörler.pdf | ±100 zone | done | strategies/oscillators.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Stoch | indikatörler.pdf | 4H trend gate | done | strategies/oscillators.py | tests/fidelity/test_golden_kasas.py |
| Kasa_StochRSI | indikatörler.pdf | 4H trend gate | done | strategies/oscillators.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Ichimoku | indikatörler.pdf | Chikou (no lookahead) + TK cross trigger TF | done | strategies/oscillators.py | tests/test_indicators_reference.py |
| Kasa_Hacim | indikatörler.pdf | OBV divergence | done | strategies/oscillators.py | tests/fidelity/test_golden_kasas.py |
| Kasa_OBO_TOBO | formasyonlar.pdf | Omuz simetrisi | done | structure/patterns.py | tests/fidelity/test_golden_kasas.py |
| Kasa_IkiliDipTepe | formasyonlar.pdf | Rejection wick 2. dip/tepe | done | structure/patterns.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Ucgen | formasyonlar.pdf | Asc/desc/symmetric ayrımı | done | strategies/patterns.py | tests/fidelity/test_golden_kasas.py |
| Kasa_BayrakFlama | formasyonlar.pdf | ATR pole, 50% rule | done | structure/patterns.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Dortgen | formasyonlar.pdf | 4 touches min | done | structure/patterns.py | tests/fidelity/test_golden_kasas.py |
| Kasa_FincanCanak | formasyonlar.pdf | Handle fazı, hacim dry-up | done | strategies/patterns.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Takoz | formasyonlar.pdf | Volume spike, measured move TP | done | strategies/patterns.py | tests/fidelity/test_golden_kasas.py |
| Kasa_Fib618 | fibonacci.pdf | OTE 0.618-0.786, TP 1.272/1.618 | done | strategies/fib.py | tests/fidelity/test_golden_kasas.py |
| Kasa_SMC | LuxAlgo | SMT, OB+BOS+FVG, CE/OTE limit, likidite TP | done | strategies/smc.py | tests/fidelity/test_smc_smt.py |
| Kasa_Lab_* | recipe | smc_grade, liquidity, walk-forward | done | engine/strategy_recipe.py | tests/fidelity/test_walk_forward_gate.py |

## Ortak altyapı checklist

| Öğe | Durum | Dosya |
|-----|-------|-------|
| Multi-TP / partial / trailing | done | engine/types.py, portfolio.py |
| best_signal scan mode | done | engine/paper.py |
| SYMBOL_LOCK_MODE | done | engine/portfolio.py, config.py |
| Dominance tam veri | done | engine/data.py |
| TTM squeeze + OBV | done | indicators/core.py |
| BOS/retest state machine | done | structure/core.py |
| Formasyon geometri modülü | done | structure/patterns.py |
| LuxAlgo SMC gaps | done | structure/smc.py, smc_scan.py |
| Walk-forward 70/30 | done | engine/walk_forward.py |
| Max drawdown kapısı | done | engine/fidelity_gate.py, lab_backtest.py |
| Paper WR kabul kapısı | done | engine/fidelity_gate.py, lab_state.py |
| Kapalı mum doğrulama | done | tests/test_closed_bar.py |

## Faz 5 kabul kriterleri

| Kriter | Durum |
|--------|-------|
| 31 kasa smoke/golden test | done — tests/fidelity/test_golden_kasas.py |
| Walk-forward PF ≥ 1.2 | done — engine/fidelity_gate.py |
| Max DD ≤ 25% | done — FIDELITY_MAX_DD |
| 90 gün backtest kapısı | done — check_kasa_backtest_acceptance |
| Paper WR ≥ backtest − 10pp | done — check_paper_acceptance |
