
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
        
        # Handle duplicates by averaging them (if needed) or dropping duplicates
        df = df.groupby('Datetime', as_index=False).agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum',
            '20_EMA': 'mean',
            '50_EMA': 'mean',
            '200_EMA': 'mean',
        })
        
        df.set_index('Datetime', inplace=True)
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'])
        return df

    def calculate_vwap(self):
        self.df['VWAP'] = (self.df['Volume'] * (self.df['High'] + self.df['Low'] + self.df['Close']) / 3).cumsum() / self.df['Volume'].cumsum()

    def volume_profile_analysis(self):
        self.df['Price_Mid'] = (self.df['High'] + self.df['Low']) / 2
        price_bins = np.linspace(self.df['Low'].min(), self.df['High'].max(), 1000)
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
            'Fib_0.0%': high,
            'Fib_23.6%': high - 0.236 * diff,
            'Fib_38.2%': high - 0.382 * diff,
            'Fib_50.0%': high - 0.5 * diff,
            'Fib_61.8%': high - 0.618 * diff,
            'Fib_100.0%': low
        }
        for key, value in fib_levels.items():
            self.df[key] = value

    def detect_ald(self):
        self.df['Hour'] = self.df.index.hour
        self.df['Session'] = self.df['Hour'].apply(
            lambda h: 'Asia' if 0 <= h < 8 else ('London' if 8 <= h < 13 else 'New York')
        )

        # Compute Asia High & Low without duplicate errors
        asia_session = self.df[self.df['Session'] == 'Asia']
        self.df['Asia_High'] = asia_session['High'].cummax().reindex(self.df.index, method='ffill')
        self.df['Asia_Low'] = asia_session['Low'].cummin().reindex(self.df.index, method='ffill')
        
        self.df['Breakout_Above_Asia'] = self.df['High'] > self.df['Asia_High'].shift(1)
        self.df['Breakout_Below_Asia'] = self.df['Low'] < self.df['Asia_Low'].shift(1)

    def generate_signals(self):
        conditions = [
            (self.df['Breakout_Above_Asia']) & (self.df['VWAP'] > self.df['Close']) & (self.df['LVN'] == 1),
            (self.df['Breakout_Below_Asia']) & (self.df['VWAP'] < self.df['Close']) & (self.df['HVN'] == 1)
        ]
        choices = ['Short', 'Long']
        self.df['ALD_Signal'] = np.select(conditions, choices, default='No Trade')

    def backtest(self):
        entries = []
        for idx, row in self.df.iterrows():
            if row['ALD_Signal'] in ['Long', 'Short']:
                sl = row['Low'] - 20 if row['ALD_Signal'] == 'Long' else row['High'] + 20
                tp = row['Close'] + (row['Close'] - sl) * 2 if row['ALD_Signal'] == 'Long' else row['Close'] - (sl - row['Close']) * 2
                risk = self.account_size * self.risk_pct
                position_size = risk / abs(row['Close'] - sl)
                entries.append({
                    'Datetime': idx,
                    'Signal': row['ALD_Signal'],
                    'Entry': row['Close'],
                    'SL': sl,
                    'TP': tp,
                    'Size': round(position_size, 2),
                    'RR': 2.0
                })
        return pd.DataFrame(entries)

    def run(self):
        self.calculate_vwap()
        self.volume_profile_analysis()
        self.add_fibonacci_levels()
        self.detect_ald()
        self.generate_signals()
        return self.backtest()
