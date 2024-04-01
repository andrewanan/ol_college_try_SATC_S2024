import shift
from time import sleep
from datetime import datetime, timedelta
import datetime as dt
from threading import Thread
from statsmodels.tsa.arima.model import ARIMA
import numpy as np
import math

historical_data = []
check_freq = 1
order_size = 5

def cancel_orders(trader, ticker):
    for order in trader.get_waiting_list():
        if (order.symbol == ticker):
            trader.submit_cancellation(order)
            sleep(1)

def arima_prediction(trader, ticker, endtime):
     while (trader.get_last_trade_time() < endtime):
        midprice = trader.get_sample_prices(ticker, mid_prices=True)

        historical_data.append(midprice)

        if len(historical_data) > 30:
            historical_data = historical_data[-30:]
            prices_series = np.log(historical_data)

        try:
            model = ARIMA(prices_series, order = (5,2,3))
            model_fit = model.fit(disp=0)
            forecast = model_fit.forecast(steps = 1)[0]

        except (ValueError):
            forecast = forecast[-1]
        return forecast


    
def close_positions(trader, ticker, batch_size=40):
    print(f"Running close positions function for {ticker}")

    item = trader.get_portfolio_item(ticker)

    long_shares = item.get_long_shares()
    if long_shares > 0:
        print(f"Closing long position because {ticker} long shares = {long_shares}")
        batches = math.ceil(long_shares / batch_size)  
        for _ in range(batches):
            order_size = min(batch_size, long_shares) 
            order = shift.Order(shift.Order.Type.MARKET_SELL, ticker, order_size // 100)
            trader.submit_order(order)
            long_shares -= order_size 
            sleep(1) 

    short_shares = item.get_short_shares()
    if short_shares > 0:
        print(f"Closing short position because {ticker} short shares = {short_shares}")
        batches = math.ceil(short_shares / batch_size) 
        for _ in range(batches):
            order_size = min(batch_size, short_shares)
            order = shift.Order(shift.Order.Type.MARKET_BUY, ticker, order_size // 100)
            trader.submit_order(order)
            short_shares -= order_size
            sleep(1)  

def order_size():
    print("placeholder")

def strategy(trader: shift.Trader, ticker: str, endtime):
    print(f"Running strategy for {ticker}!")
    forecast = arima_prediction(trader, ticker, endtime)
    
        




def main(trader):
    check_frequency = 60
    current = trader.get_last_trade_time()
   
    start_time = current
    end_time = start_time + timedelta(minutes=10)

    while trader.get_last_trade_time() < start_time:
        print("still waiting for market open")
        sleep(check_frequency)

    # we track our overall initial profits/losses value to see how our strategy affects it
    initial_pl = trader.get_portfolio_summary().get_total_realized_pl()
    threads = []

    tickers = trader.get_stock_list()
    
    print("START")

    for ticker in tickers:
        # initializes threads containing the strategy for each ticker
        threads.append(
            Thread(target=strategy, args=(trader, ticker, end_time)))

    for thread in threads:
        thread.start()
        sleep(1)

    # wait until endtime is reached
    while trader.get_last_trade_time() < end_time:
        sleep(check_frequency)

    # wait for all threads to finish
    for thread in threads:
        # NOTE: this method can stall your program indefinitely if your strategy does not terminate naturally
        # setting the timeout argument for join() can prevent this
        thread.join()

    # make sure all remaining orders have been cancelled and all positions have been closed
    for ticker in tickers:
        cancel_orders(trader, ticker)
        close_positions(trader, ticker)

    print("END")
    print(f"final bp: {trader.get_portfolio_summary().get_total_bp()}")
    print(
        f"final profits/losses: {trader.get_portfolio_summary().get_total_realized_pl() - initial_pl}")


