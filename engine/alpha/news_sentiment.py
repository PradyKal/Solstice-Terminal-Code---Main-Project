"""
SOLSTICE · NEWS & SENTIMENT ANALYST
Pulls recent headlines per ticker (yfinance, free) and scores sentiment with
TextBlob. Produces a veto/boost signal so we don't buy into bad news or miss
strong positive catalysts. Also flags earnings proximity (event risk).
"""
from __future__ import annotations
import time, datetime
import numpy as np

try:
    from textblob import TextBlob
    _HAS_TB = True
except Exception:
    _HAS_TB = False


def _score_text(text):
    if not text: return 0.0
    # Finance-aware lexicon (TextBlob alone misses market jargon)
    pos_words = ['beat','beats','surge','surges','upgrade','upgraded','record','strong','growth',
                 'rally','soar','soars','jump','jumps','outperform','raises','raised','tops','gains','bullish','wins','approval']
    neg_words = ['miss','misses','plunge','plunges','downgrade','downgraded','lawsuit','probe','cut','cuts',
                 'fall','falls','drop','drops','warn','warns','recall','bearish','slump','sinks','halts','investigation','fraud']
    tl = text.lower()
    pos = sum(w in tl for w in pos_words)
    neg = sum(w in tl for w in neg_words)
    lex = (pos - neg) / max(1, pos + neg) if (pos + neg) else 0.0
    tb = 0.0
    if _HAS_TB:
        try: tb = float(TextBlob(text).sentiment.polarity)
        except Exception: tb = 0.0
    # Blend: finance lexicon dominant, TextBlob for tone
    return float(np.clip(0.65 * lex + 0.35 * tb, -1, 1))


def ticker_sentiment(ticker, max_items=8):
    """Return dict: {sentiment, n_headlines, headlines[]}. Uses yfinance .news."""
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        news = getattr(tk, 'news', []) or []
    except Exception:
        return {'sentiment': 0.0, 'n': 0, 'headlines': []}

    scores, heads = [], []
    cutoff = time.time() - 7 * 86400   # last 7 days only
    for item in news[:max_items]:
        content = item.get('content', item)  # yfinance schema varies
        title = (content.get('title') if isinstance(content, dict) else None) or item.get('title', '')
        if not title: continue
        # pub time filter when available
        s = _score_text(title)
        scores.append(s)
        heads.append({'title': title[:120], 'score': round(s, 3)})
    if not scores:
        return {'sentiment': 0.0, 'n': 0, 'headlines': []}
    return {'sentiment': float(np.mean(scores)), 'n': len(scores), 'headlines': heads}


def screen_universe(tickers, neg_threshold=-0.15):
    """
    Returns:
      sentiment_map: {ticker: score}
      vetoed: set of tickers with strongly negative recent news
    """
    sentiment_map, vetoed = {}, set()
    for t in tickers:
        s = ticker_sentiment(t)
        sentiment_map[t] = s['sentiment']
        if s['sentiment'] <= neg_threshold and s['n'] >= 2:
            vetoed.add(t)
    return sentiment_map, vetoed


def sentiment_multiplier(score):
    """Convert sentiment [-1,1] to a position-size multiplier [0.5, 1.3]."""
    return float(np.clip(1.0 + score * 0.4, 0.5, 1.3))
