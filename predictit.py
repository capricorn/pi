import time
import json
import asyncio
import threading
import sys
import itertools
from math import floor
from random import randint

import requests

# Need to check delta between last orderbook and current one to see if an update is necessary
# Might also just use 304 if-modified, if that's possible; or hash the last response

class Market():
    def __init__(self, market):
        self.name = market['name']
        self.contracts = {}

        for contract in market['contracts']:
            self.contracts[str(contract['id'])] = {
                'name': contract['shortName']
            }

# Look into utilizing refresh token
# Shouldn't require a market to create it
# Phase out
class PredictItAPI():
    TRADE_TYPE_BUY = 1
    TRADE_TYPE_SELL = 3

    def __init__(self, market_id, token=''):
        self.token = token
        self.market_id = market_id
        self.lock = threading.Lock()

    # Eventually replace the constructor with this
    # And maybe have the auth method just take a username and password
    @staticmethod
    def create(username, password):
        p = PredictItAPI(0)
        p.token = PredictItAPI.get_auth_token(username, password)
        return p

    @staticmethod
    def get_auth_token(username, password):
        data = {
            'email': username,
            'password': password,
            'grant_type': 'password',
            'rememberMe': 'false'
        }
        resp = requests.get('https://www.predictit.org/api/Account/token', data=data)
        return resp.json()['access_token']

    # Obtain a websocket connection token, necessary for later connections
    def negotiate_ws(self):
        params = {
            'clientProtocol': 1.5,
            'bearer': self.token,
            'connectionData': json.dumps([{
                'name': 'markethub'
            }]),
            '_': floor(time.time())
        }

        resp = requests.get('https://www.predictit.org/signalr/negotiate', params=params)
        return resp.json()

    # Should be async
    def _trade(self, contract_id, price, vol, trade_type):
        data = {
            'quantity': vol,
            'pricePerShare': price, # Should be in cents, not dollars
            'contractId': contract_id,
            'tradeType': trade_type
        }

        headers = {
            'Authorization': f'Bearer {self.token}'
        }

        return requests.post('https://www.predictit.org/api/Trade/SubmitTrade', 
                data=data, headers=headers).json()

    def sell(self, contract_id, price, vol):
        return self._trade(contract_id, price, vol, PredictItAPI.TRADE_TYPE_SELL)

    def buy(self, contract_id, price, vol):
        return self._trade(contract_id, price, vol, PredictItAPI.TRADE_TYPE_BUY)

    def cancel(self, offer_id):
        headers = {
            'Authorization': f'Bearer {self.token}'
        }

        resp = requests.post(f'https://www.predictit.org/api/Trade/CancelOffer/{offer_id}', headers=headers)
        return resp.status_code == 200

    def get_contract_portfolio(self, contract_id):
        headers = {
            'Authorization': f'Bearer {self.token}'
        }

        return requests.get('https://www.predictit.org/api/Profile/contract/16575/Shares', headers=headers).json()

    def get_profile_detail(self):
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        resp = requests.get('https://www.predictit.org/api/Profile/Detail', headers=headers)
        return resp.json()

    def authenticate(self, auth_file):
        with open(auth_file, 'r') as f:
            user, passwd = tuple(f.read().split())
            
            self.token = PredictItAPI.get_auth_token(user, passwd)

    def get_market(self):
        resp = requests.get(f'https://www.predictit.org/api/marketdata/markets/{self.market_id}')
        return json.loads(resp.text)

    def get_market_contract_ids(self):
        return list(map(lambda c: str(c['id']), self.get_market()['contracts']))

    def get_contract_orderbook(self, contract_id):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36',
            'Host': 'www.predictit.org',
            'Authorization': f'Bearer {self.token}'
        }

        resp = requests.get(f'https://www.predictit.org/api/Trade/{contract_id}/OrderBook', headers=headers)
        return json.loads(resp.text)

    def load_db(self):
        with self.lock:
            try:
                with open(f'{self.market_id}.json', 'r') as f:
                    data = f.read()

                    if data == '':
                        return {}
                    else:
                        return json.loads(data)
            except FileNotFoundError:
                return {}

    def log_orderbook(self, contract_id, orderbook, ts):
        # open contract orderbook, locate contract, append orders.
        bids = []
        asks = []

        for bid in orderbook['yesOrders']:
            bids.append((bid['pricePerShare'], bid['quantity']))

        for ask in orderbook['noOrders']:
            asks.append((ask['pricePerShare'], ask['quantity']))

        db = self.load_db()
        if db == {} or contract_id not in db:
            db[contract_id] = {}

        db[contract_id][ts] = {
            'ask': [],
            'bid': []
        }

        '''
        last_ob_time = list(db[contract_id].keys())[-1:][0]
        if db[contract_id][last_ob_time] == db[contract_id][ts]:
            return
        '''

        db[contract_id][ts]['ask'].extend(asks)
        db[contract_id][ts]['bid'].extend(bids)

        with self.lock:
            with open(f'{self.market_id}.json', 'w') as f:
                f.write(json.dumps(db))

# Return some sort of Orderbook object instead.
#async def get_ob(api, contract_id):
def get_ob(api, contract_id):
    # Does this method need to be async since it's called in an async method?
    print(f'Start time: {time.time()}')
    return api.get_contract_orderbook(contract_id)

def write_ob(contract_id):
    #print(f'Start time: {time.time()}')
    start_time = str(floor(time.time()))
    api.log_orderbook(contract_id, api.get_contract_orderbook(contract_id), start_time)
    print(f'Logged {contract_id}')

def get_bids(orderbook):
    return list(map(lambda k: (k['pricePerShare'], k['quantity']), orderbook['yesOrders']))

def get_asks(orderbook):
    return list(map(lambda k: (k['costPerShareYes'], k['quantity']), orderbook['noOrders']))
