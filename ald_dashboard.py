
import streamlit as st
import pandas as pd
import plotly.express as px
from ald_strategy import ALDBacktester

st.set_page_config(page_title="US30 ALD Strategy Dashboard", layout="wide")

st.title("📈 US30 ALD Strategy Dashboard")
st.sidebar.title("Upload Dataset")

uploaded_file = st.sidebar.file_uploader("Upload your US30 dataset (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # Load and process the data
    st.sidebar.write("✅ File Uploaded Successfully!")
    backtester = ALDBacktester(filepath=uploaded_file)
    trade_results = backtester.run()
    df = backtester.df  # Processed DataFrame with Indicators
    
    st.sidebar.subheader("Account Settings")
    account_size = st.sidebar.number_input("Account Size ($)", min_value=1000, value=10000, step=1000)
    risk_pct = st.sidebar.slider("Risk Percentage per Trade (%)", min_value=0.1, max_value=5.0, value=1.0)
    
    # Update risk settings
    backtester.account_size = account_size
    backtester.risk_pct = risk_pct / 100
    
    # Show Trade Results
    st.header("Trade Results Summary")
    st.write(trade_results)
    
    # Display Signals Chart
    st.header("ALD Signals Chart")
    fig = px.scatter(df, x=df.index, y="Close", color="ALD_Signal", title="Trade Signals Over Time")
    st.plotly_chart(fig, use_container_width=True)
    
    # Display VWAP Chart
    st.header("VWAP & Price Chart")
    fig_vwap = px.line(df, x=df.index, y=["Close", "VWAP"], title="VWAP vs. Close Price")
    st.plotly_chart(fig_vwap, use_container_width=True)
    
    # Download Results
    st.sidebar.subheader("Download Results")
    if st.sidebar.button("Download Trade Results"):
        trade_results.to_csv("Trade_Results.csv", index=False)
        st.sidebar.write("✅ Trade Results Saved!")
else:
    st.warning("Please upload a valid dataset to proceed.")
