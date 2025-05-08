import asyncio

from solana.rpc.async_api import AsyncClient
from solbot_common.log import logger
from solders.keypair import Keypair  # type: ignore
from solders.signature import Signature  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore

from trading.swap import SwapDirection, SwapInType
from trading.transaction.base import TransactionSender
from trading.transaction.builders.base import TransactionBuilder
from trading.transaction.builders.gmgn import GMGNTransactionBuilder
from trading.transaction.builders.jupiter import JupiterTransactionBuilder
from trading.transaction.builders.pump import PumpTransactionBuilder
from trading.transaction.builders.ray_v4 import RaydiumV4TransactionBuilder
from trading.transaction.protocol import TradingRoute
from trading.transaction.sender import (
    DefaultTransactionSender,
    GMGNTransactionSender,
    JitoTransactionSender,
)


class Swapper:
    """交换服务，协调交换的构建和执行"""

    def __init__(self, builder: TransactionBuilder, sender: TransactionSender):
        """初始化交换服务"""
        self.builder = builder
        self.sender = sender

    async def swap(
            self,
            keypair: Keypair,
            token_address: str,
            ui_amount: float,
            swap_direction: SwapDirection,
            slippage_bps: int,
            in_type: SwapInType | None = None,
            use_jito: bool = False,
            priority_fee: float | None = None,
    ) -> Signature | None:
        """执行代币交换操作

        Args:
            keypair (Keypair): 钱包密钥对
            token_address (str): 代币地址
            ui_amount (float): 交易数量
            swap_direction (SwapDirection): 交易方向
            slippage_bps (int): 滑点，以 bps 为单位
            in_type (SwapInType | None, optional): 输入类型. Defaults to None.
            use_jito (bool, optional): 是否使用 Jito. Defaults to False.
            priority_fee (float | None, optional): 优先费用. Defaults to None.

        Returns:
            Optional[Signature]: 交易签名，如果交易失败则返回 None
        """
        transaction = await self.builder.build_swap_transaction(
            keypair=keypair,
            token_address=token_address,
            ui_amount=ui_amount,
            swap_direction=swap_direction,
            slippage_bps=slippage_bps,
            in_type=in_type,
            use_jito=use_jito,
            priority_fee=priority_fee,
        )
        logger.debug(f"Built swap transaction: {transaction}")
        signature = await self.sender.send_transaction(transaction)
        logger.info(f"Transaction sent successfully: {signature}")
        # signature = await self.send_and_confirm_with_notify(self,transaction)
        logger.info(f"Transaction finished")
        return signature

    async def wait_for_confirmation(client: AsyncClient, signature: str, timeout=30, interval=2):
        """轮询确认交易是否上链"""
        for _ in range(int(timeout / interval)):
            resp = await client.get_signature_statuses([signature])
            status = resp.value and resp.value[0]
            if status and status.confirmation_status in ("confirmed", "finalized"):
                return True
            if status and status.err is not None:
                raise Exception(f"交易失败: {status.err}")
            await asyncio.sleep(interval)
        raise TimeoutError("交易确认超时")


    async def send_with_retry(self, transaction, opts=None, max_retries=3):
        for attempt in range(max_retries):
            try:
                resp = await self.client.send_transaction(transaction, opts=opts)
                return resp.value
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # 指数退避


    async def safe_send_message(text, bot=None, chat_id=None, max_retries=3):
        if bot is None or chat_id is None:
            logger.info(f"消息未发送（无bot或chat_id）：{text}")
            return
        for attempt in range(max_retries):
            try:
                await bot.send_message(parse_mode="HTML")
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"通知用户失败: {e}，内容：{text}")
                else:
                    await asyncio.sleep(2 ** attempt)


    async def send_and_confirm_with_notify(self, transaction):
        try:
            signature = await self.send_with_retry(transaction)
            await self.wait_for_confirmation(self.client, signature)
            await self.safe_send_message(f"✅ 交易成功: {signature}")
            return signature
        except Exception as e:
            await self.safe_send_message(f"❌ 交易失败: {str(e)}")

class AggregateTransactionBuilder(TransactionBuilder):
    """聚合多个交易构建器,返回最快成功的结果"""

    def __init__(self, rpc_client: AsyncClient, builders: list[TransactionBuilder]):
        """初始化聚合构建器

        Args:
            rpc_client (AsyncClient): RPC客户端
            builders (List[TransactionBuilder]): 交易构建器列表
        """
        super().__init__(rpc_client)
        self.builders = builders

    async def _try_build_with_builder(
            self,
            builder: TransactionBuilder,
            keypair: Keypair,
            token_address: str,
            ui_amount: float,
            swap_direction: SwapDirection,
            slippage_bps: int,
            in_type: SwapInType | None = None,
            use_jito: bool = False,
            priority_fee: float | None = None,
    ) -> tuple[TransactionBuilder, VersionedTransaction]:
        """尝试使用指定构建器构建交易

        Returns:
            Tuple[TransactionBuilder, VersionedTransaction]: 返回构建器和构建的交易
        """
        try:
            tx = await builder.build_swap_transaction(
                keypair=keypair,
                token_address=token_address,
                ui_amount=ui_amount,
                swap_direction=swap_direction,
                slippage_bps=slippage_bps,
                in_type=in_type,
                use_jito=use_jito,
                priority_fee=priority_fee,
            )
            return builder, tx
        except Exception as e:
            logger.warning(f"Builder {builder.__class__.__name__} failed: {e!s}")
            raise

    async def build_swap_transaction(
            self,
            keypair: Keypair,
            token_address: str,
            ui_amount: float,
            swap_direction: SwapDirection,
            slippage_bps: int,
            in_type: SwapInType | None = None,
            use_jito: bool = False,
            priority_fee: float | None = None,
    ) -> VersionedTransaction:
        """并行尝试所有构建器,返回最快成功的交易

        Raises:
            Exception: 当所有构建器都失败时抛出异常

        Returns:
            VersionedTransaction: 构建好的交易
        """
        if not self.builders:
            raise ValueError("No transaction builders provided")

        # 创建所有构建器的任务
        tasks = [
            self._try_build_with_builder(
                builder,
                keypair,
                token_address,
                ui_amount,
                swap_direction,
                slippage_bps,
                in_type,
                use_jito,
                priority_fee,
            )
            for builder in self.builders
        ]

        # 等待第一个成功的结果
        while tasks:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                try:
                    builder, tx = await task
                    # 取消其他正在进行的任务
                    for p in pending:
                        p.cancel()
                    logger.info(f"Successfully built transaction with {builder.__class__.__name__}")
                    return tx
                except Exception:
                    # 如果这个任务失败了,继续等待其他任务
                    pass

            # 更新剩余的任务
            tasks = list(pending)

        raise Exception("All transaction builders failed")


class TradingService:
    """交易服务，协调交易的构建和执行"""

    def __init__(self, rpc_client: AsyncClient):
        """初始化交易服务"""
        self._rpc_client = rpc_client
        self._aggreage_txn_builder = AggregateTransactionBuilder(
            self._rpc_client,
            builders=[
                # GMGNTransactionBuilder(self._rpc_client),
                JupiterTransactionBuilder(self._rpc_client),
            ],
        )
        self._pump_txn_builder = PumpTransactionBuilder(self._rpc_client)
        self._raydium_v4_txn_builder = RaydiumV4TransactionBuilder(self._rpc_client)
        self._gmgn_sender = GMGNTransactionSender(self._rpc_client)
        self._jito_sender = JitoTransactionSender(self._rpc_client)
        self.default_sender = DefaultTransactionSender(rpc_client)

    def select_builder(self, route: TradingRoute) -> TransactionBuilder:
        if route == TradingRoute.PUMP:
            return self._pump_txn_builder
        elif route == TradingRoute.RAYDIUM_V4:
            return self._raydium_v4_txn_builder
        elif route == TradingRoute.DEX:
            return self._aggreage_txn_builder
        else:
            raise ValueError(f"Unsupported trading route: {route}")

    def select_sender(
            self, builder: TransactionBuilder, use_jito: bool = False
    ) -> TransactionSender:
        if isinstance(builder, GMGNTransactionBuilder):
            sender = self._gmgn_sender
        elif use_jito:
            sender = self._jito_sender
        else:
            sender = self.default_sender
        return sender

    def use_route(self, route: TradingRoute, use_jito: bool = False) -> Swapper:
        builder = self.select_builder(route)
        sender = self.select_sender(builder, use_jito)
        return Swapper(builder, sender)


