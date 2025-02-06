import asyncio
import aiohttp
import logging
import json
import random
import time
from eth_account import Account
from eth_account.messages import encode_defunct

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="LayerEdge Farming |Adfmidn [%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Utility Functions
async def delay(seconds):
    await asyncio.sleep(seconds)

async def save_to_file(filename, data):
    try:
        with open(filename, 'a', encoding='utf-8') as file:
            file.write(f"{data}\n")
        logger.info(f"Data saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save data to {filename}: {e}")

async def read_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        logger.warning(f"{filename} not found.")
        return []

def create_wallet():
    account = Account.create()
    return account.address, account.key.hex()

async def request_with_retry(method, url, session, retries=3, **kwargs):
    for attempt in range(retries):
        try:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            if attempt == retries - 1:
                logger.error(f"Request failed after {retries} retries: {e}")
                return None
            await asyncio.sleep(2)
    return None

# LayerEdgeConnection Class
class LayerEdgeConnection:
    def __init__(self, private_key=None, ref_code="knYyWnsE"):
        self.ref_code = ref_code
        self.private_key = private_key or Account.create().key.hex()
        self.wallet_address = Account.from_key(self.private_key).address

    async def make_request(self, method, url, session, retries=3, **kwargs):
        return await request_with_retry(method, url, session, retries, **kwargs)

    async def connect_node(self, session):
        timestamp = int(time.time())
        message = f"Node activation request for {self.wallet_address} at {timestamp}"
        encoded_message = encode_defunct(text=message)
        signature = Account.sign_message(encoded_message, self.private_key)
        payload = {"sign": signature.signature.hex(), "timestamp": timestamp}
        url = f"https://referralapi.layeredge.io/api/light-node/node-action/{self.wallet_address}/start"
        response = await self.make_request("POST", url, session, json=payload)
        if response and response.get("message") == "node action executed successfully":
            logger.info("Node connected successfully")
            return True
        logger.error("Failed to connect node")
        return False

    async def stop_node(self, session):
        timestamp = int(time.time())
        message = f"Node deactivation request for {self.wallet_address} at {timestamp}"
        encoded_message = encode_defunct(text=message)
        signature = Account.sign_message(encoded_message, self.private_key)
        payload = {"sign": signature.signature.hex(), "timestamp": timestamp}
        url = f"https://referralapi.layeredge.io/api/light-node/node-action/{self.wallet_address}/stop"
        response = await self.make_request("POST", url, session, json=payload)
        if response:
            logger.info("Node stopped successfully")
            return True
        logger.error("Failed to stop node")
        return False

    async def check_node_points(self, session):
        url = f"https://referralapi.layeredge.io/api/referral/wallet-details/{self.wallet_address}"
        response = await self.make_request("GET", url, session)
        if response:
            points = response.get("data", {}).get("nodePoints", 0)
            logger.info(f"Total Points: {points}")
            return points
        logger.error("Failed to retrieve node points")
        return 0

# Main Script
async def main():
    try:
        sleeptime = int(input("Masukkan waktu tunggu (detik): "))
        while True:
            wallets = await read_file("wallets.json")
            total_wallets = len(wallets)
            logger.info(f"Total address: {total_wallets}")
            if not wallets:
                logger.warning("No wallets found in wallets.json. Continuing to idle.")
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                if wallets:
                    for wallet_data in wallets:
                        try:
                            address, private_key = wallet_data.split(":")
                            connection = LayerEdgeConnection(private_key=private_key)
                            logger.info(f"Processing wallet {address}")
                            tasks.append(asyncio.create_task(connection.connect_node(session)))
                            tasks.append(asyncio.create_task(connection.check_node_points(session)))
                            tasks.append(asyncio.create_task(connection.stop_node(session)))
                        except ValueError:
                            logger.error(f"Invalid wallet data format: {wallet_data}")
                            continue

                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            logger.error(f"Task encountered an error: {result}")
                else:
                    logger.info("No tasks to execute.")
            
            logger.info("All tasks completed. Program will remain idle.")
            for i in range(sleeptime, 0, -1):
                print(f"Menunggu... {i} detik tersisa", end='\r')
                await asyncio.sleep(1)
            print()
    except KeyboardInterrupt:
        logger.info("Terminated by user.")
        return
    except Exception as e:
        logger.error(f"An error occurred in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())
