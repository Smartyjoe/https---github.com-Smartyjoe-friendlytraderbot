
# Gemini Prompts for Telegram Trading Bot

This file contains a collection of prompts for use with a generative AI assistant to help develop a Telegram chatbot for real-time trading signals with PocketOption.

## 1. Project Setup and Structure

### Prompt

"I am building a Python-based Telegram bot that connects to the PocketOption API using `pocketoptionapi_async` to generate and send real-time trading signals. Can you suggest a good project structure for this? I'll need modules for the Telegram bot UI, the PocketOption API connection, the trading signal generation logic, and configuration management."

---

## 2. Connecting to PocketOption API

### Prompt

"I'm using the `pocketoptionapi_async` library to connect to PocketOption. Can you provide a Python code snippet that establishes a connection using environment variables for the username and password, and then subscribes to real-time asset prices for 'EUR/USD'?"

---

## 3. Telegram Bot Integration

### Prompt

"I'm using the `python-telegram-bot` library. Please provide the basic boilerplate code for a Telegram bot that has a `/start` command to welcome the user and a `/subscribe` command that will later be used to subscribe to trading signals."

---

## 4. Real-time Market Data Handling

### Prompt

"I have a stream of real-time market data (candles or ticks) coming from the `pocketoptionapi_async` websocket. I need to process this data to calculate technical indicators like RSI (Relative Strength Index) and EMA (Exponential Moving Average). Can you show me how to create a class that takes in this real-time data and manages the state of these indicators?"

---

## 5. Trading Signal Generation

### Prompt

"Based on a stream of candles, I want to generate trading signals. A 'BUY' signal is generated when the 14-period RSI crosses above 30, and a 'SELL' signal is generated when the RSI crosses below 70. Additionally, I want to use a 50-period EMA as a trend filter; only generate 'BUY' signals when the price is above the EMA, and 'SELL' signals when the price is below the EMA. Can you write a Python function that takes the current RSI value, the current price, and the current EMA value, and returns 'BUY', 'SELL', or 'HOLD'?"

---

## 6. Main Application Loop (Putting it all together)

### Prompt

"I need to create the main asynchronous loop for my application. This loop should:
1. Initialize the `pocketoptionapi_async` client and connect.
2. Initialize and start the `python-telegram-bot`.
3. Start listening to the real-time market data from PocketOption.
4. For each new candle/tick, update the technical indicators.
5. Check for trading signals using the logic I've defined.
6. If a new signal is generated, send it to a subscribed user via the Telegram bot.

Please provide a Python script structure for this main `asyncio` loop."

---

## 7. Error Handling and Logging

### Prompt

"What are some best practices for error handling and logging in my async Python trading bot? I'm concerned about potential issues like:
- The PocketOption API connection dropping.
- The Telegram API being unavailable.
- Errors in my signal calculation logic.

Please provide some code examples for robust logging and a simple reconnection strategy for the websocket."

---

## 8. Testing

### Prompt

"How can I effectively write unit tests for my trading signal generation logic? Can you provide an example using `pytest` and `pytest-asyncio` to test the signal generation function? I want to be able to mock the input data (RSI, price, EMA) to test different scenarios."
