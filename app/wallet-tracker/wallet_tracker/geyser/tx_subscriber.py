import asyncio
import signal
import time
from collections.abc import AsyncGenerator, Sequence

import aioredis
import base58
import orjson as json
from google.protobuf.json_format import (
    Parse,
    _Printer,  # type: ignore
)
from google.protobuf.message import Message
from grpc.aio import AioRpcError
from solbot_common.config import settings
from solbot_common.log import logger
from solbot_db.redis import RedisClient
from solders.pubkey import Pubkey  # type: ignore
from yellowstone_grpc.client import GeyserClient
from yellowstone_grpc.grpc import geyser_pb2
from yellowstone_grpc.types import (
    SubscribeRequest,
    SubscribeRequestFilterTransactions,
    SubscribeRequestPing,
)

from wallet_tracker.constants import NEW_TX_DETAIL_CHANNEL


def should_convert_to_base58(value) -> bool:
    """Check if bytes should be converted to base58."""
    if not isinstance(value, bytes):
        return False
    try:
        # 尝试解码为字符串，如果成功且没有特殊字符，就用字符串
        decoded = value.decode("utf-8")
        # 检查是否包含转义字符或不可打印字符
        return "\\" in decoded or any(ord(c) < 32 or ord(c) > 126 for c in decoded)
    except UnicodeDecodeError:
        # 如果无法解码为字符串，就用 base58
        return True


class Base58Printer(_Printer):
    def __init__(self) -> None:
        super().__init__()
        self.preserve_proto_field_names = True

    def _RenderBytes(self, value):
        """Renders a bytes value as base58 or utf-8 string."""
        if should_convert_to_base58(value):
            return base58.b58encode(value).decode("utf-8")
        return value.decode("utf-8")

    def _FieldToJsonObject(self, field, value):
        """Converts field value according to its type."""
        if field.cpp_type == field.CPPTYPE_BYTES and isinstance(value, bytes):
            if should_convert_to_base58(value):
                return base58.b58encode(value).decode("utf-8")
            return value.decode("utf-8")
        return super()._FieldToJsonObject(field, value)


def proto_to_dict(message: Message) -> dict:
    """Convert protobuf message to dict with bytes fields encoded as base58 or utf-8."""
    printer = Base58Printer()
    return printer._MessageToJsonObject(message)


class TransactionDetailSubscriber:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        redis_client: aioredis.Redis,
        wallets: Sequence[Pubkey],
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.geyser_client = None
        self.wallets = wallets
        self.subscribed_wallets = {str(wallet) for wallet in wallets}
        self.redis = redis_client
        self.is_running = False
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 5  # seconds

        self.request_queue: asyncio.Queue[geyser_pb2.SubscribeRequest] | None = None
        self.responses: AsyncGenerator[geyser_pb2.SubscribeUpdate, None] | None = None
        # 响应处理相关
        self.response_queue = asyncio.Queue(maxsize=1000)
        self.worker_nums = 2
        self.workers: list[asyncio.Task] = []

    async def _connect(self) -> None:
        """Connect to Geyser service with retry mechanism."""
        while self.retry_count < self.max_retries:
            try:
                self.geyser_client = await GeyserClient.connect(self.endpoint, x_token=self.api_key)
                self.retry_count = 0  # Reset retry count on successful connection
                logger.info("Successfully connected to Geyser service")
                return
            except Exception as e:
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    logger.error(
                        f"Failed to connect to Geyser service after {self.max_retries} attempts: {e}"
                    )
                    raise
                logger.warning(
                    f"Connection attempt {self.retry_count} failed, retrying in {self.retry_delay} seconds..."
                )
                await asyncio.sleep(self.retry_delay)

    async def _reconnect_and_subscribe(self) -> None:
        logger.info("Attempting to reconnect...")
        await asyncio.sleep(self.retry_delay)
        await self._connect()

        if self.geyser_client is None:
            raise RuntimeError("Geyser client is not connected")

        # Create subscription request
        subscribe_request = self.__build_subscribe_request()
        json_str = subscribe_request.model_dump_json()
        pb_request = Parse(json_str, geyser_pb2.SubscribeRequest())

        # Subscribe to updates
        logger.info("Subscribing to account updates...")
        (
            self.request_queue,
            self.responses,
        ) = await self.geyser_client.subscribe_with_request(pb_request)

    def __build_subscribe_request(self) -> SubscribeRequest:
        logger.info(f"Subscribing to accounts: {self.subscribed_wallets}")

        params = {}

        if len(self.subscribed_wallets) != 0:
            params["transactions"] = {
                "key": SubscribeRequestFilterTransactions(
                    account_include=list(self.subscribed_wallets),
                    failed=False,
                )
            }
        else:
            params["ping"] = SubscribeRequestPing(id=1)

        subscribe_request = SubscribeRequest(**params)
        return subscribe_request

    async def _process_transaction(self, transaction: dict) -> None:
        """Process and store transaction in Redis."""
        if self.redis is None:
            raise Exception("Redis is not connected")

        try:
            signature = transaction["transaction"]["signature"]
            # 构建成 rpc 返回的结构，方便统一解析交易数据
            data = {
                **transaction["transaction"],
            }
            data["slot"] = int(transaction["slot"])
            data["version"] = 0
            # 只有被确认之后才会有 blockTime, 所以这里设置为当前时间
            data["blockTime"] = int(time.time())

            tx_info_json = json.dumps(data)
            # Store in Redis using LIST structure
            # 将交易信息添加到列表左端（最新的交易在最前面）
            await self.redis.lpush(NEW_TX_DETAIL_CHANNEL, tx_info_json)
            # 保持列表长度在合理范围内（比如最多保留1000条交易记录）
            # await self.redis.ltrim(NEW_TX_DETAIL_CHANNEL, 0, 999)
            logger.info(f"Added transaction '{signature}' to queue")
        except Exception as e:
            logger.exception(f"Error processing transaction: {e}")

    async def _process_response_worker(self):
        """Process responses from the queue."""
        logger.info(f"Starting response worker {id(asyncio.current_task())}")
        while self.is_running:
            try:
                response = await self.response_queue.get()
                try:
                    response_dict = proto_to_dict(response)
                    if "ping" in response_dict:
                        logger.debug(f"Got ping response: {response_dict}")
                    if "filters" in response_dict and "transaction" in response_dict:
                        logger.debug(f"Got transaction response: \n {response_dict}")
                        await self._process_transaction(response_dict["transaction"])
                except Exception as e:
                    logger.error(f"Error processing response: {e}")
                    logger.exception(e)
                finally:
                    self.response_queue.task_done()
            except asyncio.CancelledError:
                logger.info(f"Worker {id(asyncio.current_task())} cancelled")
                break
            except Exception as e:
                logger.exception(f"Worker error: {e}")

    async def _start_workers(self):
        """Start response processing workers."""
        logger.info(f"Starting {self.worker_nums} response workers")
        self.workers = [
            asyncio.create_task(self._process_response_worker()) for _ in range(self.worker_nums)
        ]

    async def _stop_workers(self):
        """Stop response processing workers."""
        logger.info("Stopping response workers")
        # 等待队列处理完成
        if not self.response_queue.empty():
            await self.response_queue.join()

        # 取消所有工作协程
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

    async def start(self) -> None:
        """Start monitoring wallet transactions."""
        logger.info(f"Starting wallet monitor for accounts: {self.wallets}")

        self.is_running = True

        try:
            # 启动工作协程
            await self._start_workers()

            # 初始化连接
            await self._connect()

            if self.geyser_client is None:
                raise Exception("Geyser client is not connected")

            # Create subscription request
            subscribe_request = SubscribeRequest(ping=SubscribeRequestPing(id=1))
            pb_request = Parse(subscribe_request.model_dump_json(), geyser_pb2.SubscribeRequest())

            # Subscribe to updates
            logger.info("Subscribing to account updates...")
            (
                self.request_queue,
                self.responses,
            ) = await self.geyser_client.subscribe_with_request(pb_request)

            async def _f():
                """Process responses from the queue."""
                logger.info(f"Starting response worker {id(asyncio.current_task())}")

                while self.is_running:
                    try:
                        async for response in self.responses:
                            if not self.is_running:
                                break
                            await self.response_queue.put(response)
                    except AioRpcError as e:
                        logger.error(f"Rpc Error: {e._details}")
                        logger.error(f"Rpc Error: {e}")
                        await self._reconnect_and_subscribe()
                    except Exception as e:
                        logger.exception(e)
                        await self._reconnect_and_subscribe()

            monitor_task = asyncio.create_task(_f())
            # 添加任务完成回调以处理可能的异常
            monitor_task.add_done_callback(lambda t: t.exception() if t.exception() else None)
        except asyncio.CancelledError:
            logger.info("Monitor cancelled, shutting down...")
        except Exception as e:
            logger.error(f"Fatal error in wallet monitor: {e}")
            raise

    async def stop(self) -> None:
        """Stop the wallet monitor gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping wallet monitor...")
        self.is_running = False

        # 等待所有工作协程完成
        await self._stop_workers()

        # 关闭 geyser client
        if self.geyser_client:
            try:
                await self.geyser_client.close()
                self.geyser_client = None
            except Exception as e:
                logger.error(f"Error closing geyser client: {e}")

        # 关闭 Redis 连接
        if self.redis:
            try:
                await RedisClient.close()
                self.redis = None
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

        logger.info("Wallet monitor stopped")

    async def subscribe_wallet_transactions(self, wallet: Pubkey) -> None:
        """订阅钱包的交易信息。

        每次发送新的订阅请求都会完全替换之前的订阅状态。
        这是 Geyser API 的设计：它使用 gRPC 的双向流，每个新请求都会更新整个订阅列表。

        Args:
            wallet (Pubkey): 要订阅的钱包地址
        """
        if self.request_queue is None:
            raise Exception("Request queue is not initialized")

        if str(wallet) in self.subscribed_wallets:
            logger.warning(f"Wallet {wallet} already subscribed")
            return

        # 添加到订阅集合
        self.subscribed_wallets.add(str(wallet))

        # 发送订阅请求，包含所有已订阅的钱包
        # 这个请求会完全替换服务器端之前的订阅状态
        subscribe_request = self.__build_subscribe_request()
        json_str = subscribe_request.model_dump_json()
        pb_request = Parse(json_str, geyser_pb2.SubscribeRequest())
        await self.request_queue.put(pb_request)

    async def unsubscribe_wallet_transactions(self, wallet: Pubkey) -> None:
        """取消订阅钱包的交易信息。

        每次发送新的订阅请求都会完全替换之前的订阅状态。
        这是 Geyser API 的设计：它使用 gRPC 的双向流，每个新请求都会更新整个订阅列表。

        Args:
            wallet (Pubkey): 要取消订阅的钱包地址
        """
        if self.request_queue is None:
            raise Exception("Request queue is not initialized")

        if str(wallet) not in self.subscribed_wallets:
            logger.warning(f"Wallet {wallet} not subscribed")
            return

        # 从订阅集合中移除钱包
        self.subscribed_wallets.remove(str(wallet))

        # 发送新的订阅请求，只包含剩余的钱包
        # 这个请求会完全替换服务器端之前的订阅状态
        subscribe_request = self.__build_subscribe_request()
        json_str = subscribe_request.model_dump_json()
        pb_request = Parse(json_str, geyser_pb2.SubscribeRequest())
        await self.request_queue.put(pb_request)


if __name__ == "__main__":
    from solbot_db.redis import RedisClient

    async def main():
        wallets = [
            "4kNZdGyqn1zK6tJsMjFXNiErPjKHhWchcmdLj4yCD9sj",
            "2TUNQSoPQvV8XHArVQeUwiwJcfrvsmdPCQMzSZZofFT4",
            "FDewhjnJ2BvF8r1RGBx2jpcZ9W4BrhfU5ud5dDqsDEbu",
            "2BPkYM8xWzMoSJHWpjKz3HYZ3Gw9gUC5kSBKDV95Z777",
            "2dV7UHwdooBxowaNTjLALuFJaGeRfgcuP6DkUNysMdpX",
            "5BAVxxaUS1ykh4A6EqLGxxZLaUH9t7qxtabPYFWSswCd",
            "12BRrNxzJYMx7cRhuBdhA71AchuxWRcvGydNnDoZpump",
            "DhfRG9Q1UUCmY1XpYYJZrk66CQfuyNjm3PL4fscoFYvT",
            "9WXBAVFR84XKaPDwfUURwtqK4xRKvFswcRMybPqbVUe3",
            "8853FvS6QYwELksRtX8G3rZgCxZxae7LNSSskg4ckBZ5",
            "5TLuLT2y4Tcbs8MJPNoxxANebDko6NiCQZQKxejoT3VP",
        ]
        endpoint = settings.rpc.geyser.endpoint
        api_key = settings.rpc.geyser.api_key
        monitor = TransactionDetailSubscriber(
            endpoint,
            api_key,
            RedisClient.get_instance(),
            [Pubkey.from_string(wallet) for wallet in wallets],
        )

        # 设置信号处理
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(monitor.stop()))

        try:
            await monitor.start()
        except asyncio.CancelledError:
            logger.info("Monitor cancelled, shutting down...")
            await monitor.stop()
        except Exception as e:
            logger.error(f"Error in main: {e}")
            await monitor.stop()
            raise

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
