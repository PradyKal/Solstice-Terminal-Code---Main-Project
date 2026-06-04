"""SOLSTICE rigor layer: deflated/probabilistic Sharpe, multiple-testing correction.
Ref: Bailey & Lopez de Prado (2014), 'The Deflated Sharpe Ratio'.
"""
from __future__ import annotations
import numpy as np
from scipy import stats


def probabilistic_sharpe_ratio(returns, benchmark_sr=0.0, periods_per_year=252/5):
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n < 5 or r.std() == 0:
        return 0.0
    sr = r.mean() / r.std()
    bench_per = benchmark_sr / np.sqrt(periods_per_year)
    skew = stats.skew(r); kurt = stats.kurtosis(r, fisher=False)
    num = (sr - bench_per) * np.sqrt(n - 1)
    den = np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    return float(stats.norm.cdf(num / den)) if den > 0 else 0.0


def deflated_sharpe_ratio(returns, n_trials, periods_per_year=252/5):
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n < 5 or r.std() == 0 or n_trials < 1:
        return 0.0
    sr_per = r.mean() / r.std()
    var_sr = (1.0/(n-1)) * (1 - stats.skew(r)*sr_per + (stats.kurtosis(r, fisher=False)-1)/4 * sr_per**2)
    sigma_sr = np.sqrt(max(var_sr, 1e-12))
    euler = 0.5772156649
    e_max = (1-euler)*stats.norm.ppf(1-1.0/n_trials) + euler*stats.norm.ppf(1-1.0/(n_trials*np.e))
    bench = sigma_sr * e_max
    num = (sr_per - bench) * np.sqrt(n - 1)
    skew = stats.skew(r); kurt = stats.kurtosis(r, fisher=False)
    den = np.sqrt(1 - skew*sr_per + (kurt-1)/4 * sr_per**2)
    return float(stats.norm.cdf(num/den)) if den > 0 else 0.0


def min_track_record_length(returns, target_sr=1.0, periods_per_year=252/5, conf=0.95):
    r = np.asarray(returns, dtype=float)
    if len(r) < 5 or r.std() == 0:
        return float('inf')
    sr = r.mean()/r.std()
    skew = stats.skew(r); kurt = stats.kurtosis(r, fisher=False)
    z = stats.norm.ppf(conf)
    target_per = target_sr/np.sqrt(periods_per_year)
    denom = (sr - target_per)**2
    if denom <= 0:
        return float('inf')
    return float(1 + (1 - skew*sr + (kurt-1)/4*sr**2) * (z/np.sqrt(denom))**2)
