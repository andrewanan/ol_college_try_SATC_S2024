import shift
from time import sleep
from datetime import datetime, timedelta
import datetime as dt
from threading import Thread, Lock
from statsmodels.tsa.arima.model import ARIMA
import numpy as np
import math


# NOTE: for documentation on the different classes and methods used to interact with the SHIFT system, 
# see: https://github.com/hanlonlab/shift-python/wiki

class tradeCounter:
    def __init__ (self):
        self.count = 0
        self.lock = Lock()

    def increment(self):
        with self.lock:
            self.count += 1
    
    def get_count(self):
        with self.lock:
            return self.count

def cancel_orders(trader, ticker):
    # cancel all the remaining orders
    for order in trader.get_waiting_list():
        if (order.symbol == ticker):
            trader.submit_cancellation(order)
            sleep(1)  # the order cancellation needs a little time to go through



def close_positions(trader, ticker):
    # NOTE: The following orders may not go through if:
    # 1. You do not have enough buying power to close your short postions. Your strategy should be formulated to ensure this does not happen.
    # 2. There is not enough liquidity in the market to close your entire position at once. You can avoid this either by formulating your
    #    strategy to maintain a small position, or by modifying this function to close ur positions in batches of smaller orders.

    # close all positions for given ticker
    print(f"running close positions function for {ticker}")

    item = trader.get_portfolio_item(ticker)

    # close any long positions
    long_shares = item.get_long_shares()
    if long_shares > 0:
        print(f"market selling because {ticker} long shares = {long_shares}")
        order = shift.Order(shift.Order.Type.MARKET_SELL,
                            ticker, int(long_shares/100))  # we divide by 100 because orders are placed for lots of 100 shares
        trader.submit_order(order)
        sleep(1)  # we sleep to give time for the order to process

    # close any short positions
    short_shares = item.get_short_shares()
    if short_shares > 0:
        print(f"market buying because {ticker} short shares = {short_shares}")
        order = shift.Order(shift.Order.Type.MARKET_BUY,
                            ticker, int(short_shares/100))
        trader.submit_order(order)
        sleep(1)


def strategy(trader: shift.Trader, ticker: str, endtime, trade_counter : tradeCounter):
    
    print(f"Running strategy for {ticker}")

    # strategy parameters
    historical_prices = []
    stock_spread = []
    check_freq = 5
    order_size = 3  # NOTE: this is 5 lots which is 500 shares.
    while (trader.get_last_trade_time() < endtime):
        bp = trader.get_best_price(ticker)
        best_bid = bp.get_bid_price()
        best_ask = bp.get_ask_price()
        bid_amt = bp.get_bid_size()
        ask_amt = bp.get_ask_size()
        midprice = (best_bid + best_ask) /2 
        spread = best_bid - best_ask
# get_sample_prices() <- replace with this
        stock_spread.append(spread)
        historical_prices.append(midprice)

        if len(historical_prices) > 30:
            historical_prices = historical_prices[-30:]
            prices_series = np.log(historical_prices)

            model = ARIMA(prices_series, order = (5,2,3))
            model_fit = model.fit()
            
            forecast = model_fit.forecast(steps=1)[0]

            if forecast > 0:
                order = shift.Order(shift.Order.Type.MARKET_BUY, ticker, order_size)
                trader.submit_order(order)
                print(f"Buying {ticker} x {order_size}")
                trade_counter.increment()

            elif forecast < 0:
                order = shift.Order(shift.Order.Type.MARKET_SELL, ticker, order_size)
                trader.submit_order(order)
                print(f"Selling {ticker} x {order_size}")
        sleep(check_freq)
        if len(stock_spread) > 30:
            stock_spread = stock_spread[-30:]
    
    sleep(check_freq)
    #print(f"Price History: {historical_prices}")
    #print(f"Bid Ask Spread: {stock_spread}")
    



    # cancel unfilled orders and close positions for this ticker
    cancel_orders(trader, ticker)
    close_positions(trader, ticker)
    print(f"Total P&L for {ticker}: {trader.get_portfolio_item(ticker).get_realized_pl()}")

   #print(f"total profits/losses for {ticker}: {trader.get_portfolio_item(ticker).get_realized_pl()}))


def main(trader):
    # keeps track of times for the simulation
    check_frequency = 60
    current = trader.get_last_trade_time()
    # start_time = datetime.combine(current, dt.time(9, 30, 0))
    # end_time = datetime.combine(current, dt.time(15, 50, 0))
    start_time = current
    end_time = start_time + timedelta(minutes=3)
#390 mins in a trading day try 150 for 200 trades.
    while trader.get_last_trade_time() < start_time:
        print("still waiting for market open")
        sleep(check_frequency)

    # we track our overall initial profits/losses value to see how our strategy affects it
    initial_pl = trader.get_portfolio_summary().get_total_realized_pl()
    threads = []

    # in this example, we simultaneously and independantly run our trading alogirthm on two tickers
    tickers = trader.get_stock_list()
    
    print("START")

    trade_counter = tradeCounter()

    for ticker in tickers:
        # initializes threads containing the strategy for each ticker
        threads.append(
            Thread(target=strategy, args=(trader, ticker, end_time, trade_counter)))

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
        thread.join(timeout=30)

    

    # make sure all remaining orders have been cancelled and all positions have been closed
    for ticker in tickers:
        cancel_orders(trader, ticker)
        close_positions(trader, ticker)

    print("END")
    print(f"final bp: {trader.get_portfolio_summary().get_total_bp()}")
    print(f"final profits/losses: {trader.get_portfolio_summary().get_total_realized_pl() - initial_pl}")
    print(f"orders: {trade_counter.get_count()}")



if __name__ == '__main__':
    with shift.Trader("ol_college_try") as trader:
        trader.connect("initiator.cfg", "vmdZPOG2")
        sleep(1)
        trader.sub_all_order_book()
        sleep(1)

        main(trader)
