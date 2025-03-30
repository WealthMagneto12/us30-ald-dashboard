# === Institutional Indicator Specifications ===
# EMA 20: Short-term Momentum | Bright Cyan #00FFFF
# EMA 40: Medium-term Directional Bias | Bright Orange #FFA500
# SMA 50: Structural Support/Resistance | Bright Yellow
# ATR 14: Volatility & Risk Management | Bright Magenta
# RSI (14, MA 10): Momentum & Divergence | Bright Green #66FF00
# Fibonacci Levels: 38.2%, 61.8%, 78.6% | Bright White
# Volume: Market Participation Confirmation | Bright Purple

import pandas as pd
import numpy as np

class ALDBacktester:
    def __init__(self, filepath):
        self.df = self.load_clean_data(filepath)
        self.account_size = 10000
        self.risk_pct = 0.01

    def load_clean_data(self, filepath):
        df = pd.read_excel(filepath)
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        df = df.groupby('Datetime', as_index=False).agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum',
        })
        df.set_index('Datetime', inplace=True)
        df['20_EMA'] = df['Close'].ewm(span=20).mean()
        df['40_EMA'] = df['Close'].ewm(span=40).mean()
        df['50_SMA'] = df['Close'].rolling(window=50).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
        df['RSI'] = self.calculate_rsi(df['Close'], 14)
        df = df.dropna()
        return df

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(window=period).mean()
        avg_loss = pd.Series(loss).rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_vwap(self):
        self.df['VWAP'] = (self.df['Volume'] * (self.df['High'] + self.df['Low'] + self.df['Close']) / 3).cumsum() / self.df['Volume'].cumsum()

    def volume_profile_analysis(self):
        self.df['Price_Mid'] = (self.df['High'] + self.df['Low']) / 2
        price_bins = np.linspace(self.df['Low'].min(), self.df['High'].max(), 1000)
        price_bins = np.unique(price_bins)  # Fix for non-monotonic bins
        grouped = pd.cut(self.df['Price_Mid'], bins=price_bins, labels=False)
        volume_distribution = self.df.groupby(grouped)['Volume'].sum().reset_index()
        volume_distribution.columns = ['Price_Level', 'Total_Volume']
        volume_distribution['Price'] = price_bins[volume_distribution['Price_Level']]
        hvn = volume_distribution.sort_values('Total_Volume', ascending=False).head(5)['Price'].tolist()
        lvn = volume_distribution.sort_values('Total_Volume', ascending=True).head(5)['Price'].tolist()
        self.df['HVN'] = self.df['Price_Mid'].apply(lambda x: 1 if x in hvn else 0)
        self.df['LVN'] = self.df['Price_Mid'].apply(lambda x: 1 if x in lvn else 0)

    def add_fibonacci_levels(self):
        high = self.df['High'].max()
        low = self.df['Low'].min()
        diff = high - low
        fib_levels = {
            'Fib_38.2%': high - 0.382 * diff,
            'Fib_61.8%': high - 0.618 * diff,
            'Fib_78.6%': high - 0.786 * diff
        }
        for key, value in fib_levels.items():
            self.df[key] = value

    def detect_ald(self):
        self.df['Hour'] = self.df.index.hour
        self.df['Session'] = self.df['Hour'].apply(
            lambda h: 'Asia' if 0 <= h < 8 else ('London' if 8 <= h < 13 else 'New York')
        )
        asia_session = self.df[self.df['Session'] == 'Asia']
        self.df['Asia_High'] = asia_session['High'].cummax().reindex(self.df.index, method='ffill')
        self.df['Asia_Low'] = asia_session['Low'].cummin().reindex(self.df.index, method='ffill')
        self.df['Breakout_Above_Asia'] = self.df['High'] > self.df['Asia_High'].shift(1)
        self.df['Breakout_Below_Asia'] = self.df['Low'] < self.df['Asia_Low'].shift(1)

    def generate_signals(self):
        conditions = [
            (self.df['Breakout_Above_Asia']) & 
            (self.df['VWAP'] > self.df['Close']) & 
            (self.df['LVN'] == 1) & 
            (self.df['RSI'] > 70) & 
            (self.df['Close'] < self.df['40_EMA']),

            (self.df['Breakout_Below_Asia']) & 
            (self.df['VWAP'] < self.df['Close']) & 
            (self.df['HVN'] == 1) & 
            (self.df['RSI'] < 30) & 
            (self.df['Close'] > self.df['40_EMA'])
        ]
        choices = ['Short', 'Long']
        self.df['ALD_Signal'] = np.select(conditions, choices, default='No Trade')

    def backtest(self):
        entries = []
        equity = self.account_size
        for idx, row in self.df.iterrows():
            if row['ALD_Signal'] in ['Long', 'Short']:
                atr = row['ATR']
                sl = row['Close'] - atr * 1.5 if row['ALD_Signal'] == 'Long' else row['Close'] + atr * 1.5
                tp = row['Close'] + atr * 3 if row['ALD_Signal'] == 'Long' else row['Close'] - atr * 3
                risk = self.account_size * self.risk_pct
                position_size = risk / abs(row['Close'] - sl)

                hit_tp = row['High'] >= tp if row['ALD_Signal'] == 'Long' else row['Low'] <= tp
                hit_sl = row['Low'] <= sl if row['ALD_Signal'] == 'Long' else row['High'] >= sl

                if hit_tp:
                    pnl = (tp - row['Close']) * position_size if row['ALD_Signal'] == 'Long' else (row['Close'] - tp) * position_size
                    outcome = 'TP Hit'
                elif hit_sl:
                    pnl = (sl - row['Close']) * position_size if row['ALD_Signal'] == 'Long' else (row['Close'] - sl) * position_size
                    outcome = 'SL Hit'
                else:
                    pnl = 0
                    outcome = 'No Hit'

                equity += pnl
                entries.append({
                    'Datetime': idx,
                    'Signal': row['ALD_Signal'],
                    'Entry': row['Close'],
                    'SL': round(sl, 2),
                    'TP': round(tp, 2),
                    'Size': round(position_size, 2),
                    'RR': 3.0,
                    'Outcome': outcome,
                    'PnL': round(pnl, 2),
                    'Equity': round(equity, 2)
                })
        return pd.DataFrame(entries)

    def run(self):
        self.calculate_vwap()
        self.volume_profile_analysis()
        self.add_fibonacci_levels()
        self.detect_ald()
        self.generate_signals()
        return self.backtest()