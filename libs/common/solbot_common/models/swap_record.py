from enum import Enum

from sqlalchemy import BIGINT
from sqlmodel import Field

from solbot_common.models.base import Base


class TransactionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"


class SwapRecord(Base, table=True):
    __tablename__ = "swap_record"  # type: ignore

    signature: str | None = Field(default=None, nullable=True, description="交易 hash")
    status: TransactionStatus | None = Field(default=None, nullable=True, description="交易状态")
    user_pubkey: str = Field(nullable=False, index=True)
    swap_mode: str = Field(nullable=False)
    input_mint: str = Field(nullable=False)
    output_mint: str = Field(nullable=False)
    input_amount: int = Field(nullable=False, sa_type=BIGINT, description="输入金额")
    ui_amount: int = Field(nullable=False, sa_type=BIGINT, description="交易的显示金额")
    input_token_decimals: int = Field(nullable=False, description="输入代币精度")
    output_amount: int = Field(nullable=False, sa_type=BIGINT, description="输出金额")
    output_token_decimals: int = Field(nullable=False, description="输出代币精度")
    program_id: str | None = Field(default=None, nullable=True, description="程序ID")
    timestamp: int | None = Field(default=None, nullable=True, sa_type=BIGINT, description="时间戳")
    fee: int | None = Field(default=None, nullable=True, sa_type=BIGINT, description="手续费")
    slot: int | None = Field(
        default=None, nullable=True, sa_type=BIGINT, description="提交时的 slot"
    )
    sol_change: int | None = Field(
        default=None,
        nullable=True,
        sa_type=BIGINT,
        description="SOL 改变量",
    )
    swap_sol_change: int | None = Field(
        default=None,
        nullable=True,
        sa_type=BIGINT,
        description="交易 SOL 改变量",
    )
    other_sol_change: int | None = Field(
        default=None,
        nullable=True,
        sa_type=BIGINT,
        description="其他 SOL 改变量",
    )

    @property
    def input_ui_amount(self) -> float:
        return self.input_amount / 10**self.input_token_decimals

    @property
    def output_ui_amount(self) -> float:
        return self.output_amount / 10**self.output_token_decimals
