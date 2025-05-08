import struct
from dataclasses import dataclass

from solders.pubkey import Pubkey  # type: ignore


@dataclass
class GlobalAccount:
    discriminator: int
    initialized: bool
    authority: Pubkey
    fee_recipient: Pubkey
    initial_virtual_token_reserves: int
    initial_virtual_sol_reserves: int
    initial_real_token_reserves: int
    token_total_supply: int
    fee_basis_points: int

    def get_initial_buy_price(self, amount: int) -> int:
        """
        计算初始买入价格
        """
        if amount <= 0:
            return 0

        n = self.initial_virtual_sol_reserves * self.initial_virtual_token_reserves
        i = self.initial_virtual_sol_reserves + amount
        r = n // i + 1  # 使用整数除法
        s = self.initial_virtual_token_reserves - r

        return min(s, self.initial_real_token_reserves)

    @classmethod
    def from_buffer(cls, buffer: bytes) -> "GlobalAccount":
        """
        从字节缓冲区解析账户数据
        格式: <Q ? 32s 32s Q Q Q Q Q
        Q: unsigned long long (8 bytes)
        ?: boolean (1 byte)
        32s: 32 bytes for Pubkey
        """
        try:
            # 如果缓冲区长度大于113字节，只使用前113字节
            if len(buffer) > 113:
                buffer = buffer[:113]
            elif len(buffer) < 113:
                raise ValueError(f"Buffer too short: expected 113 bytes, got {len(buffer)} bytes")

            # 解包数据
            (
                discriminator,
                initialized,
                authority_bytes,
                fee_recipient_bytes,
                initial_virtual_token_reserves,
                initial_virtual_sol_reserves,
                initial_real_token_reserves,
                token_total_supply,
                fee_basis_points,
            ) = struct.unpack("<Q?32s32sQQQQQ", buffer)

            # 转换 Pubkey
            authority = Pubkey.from_bytes(authority_bytes)
            fee_recipient = Pubkey.from_bytes(fee_recipient_bytes)

            return cls(
                discriminator=discriminator,
                initialized=initialized,
                authority=authority,
                fee_recipient=fee_recipient,
                initial_virtual_token_reserves=initial_virtual_token_reserves,
                initial_virtual_sol_reserves=initial_virtual_sol_reserves,
                initial_real_token_reserves=initial_real_token_reserves,
                token_total_supply=token_total_supply,
                fee_basis_points=fee_basis_points,
            )
        except struct.error as e:
            raise ValueError(f"Failed to decode buffer: {e}")

    def __post_init__(self):
        """
        数据类初始化后的验证
        """
        if not isinstance(self.authority, (Pubkey, type(None))):
            raise TypeError("authority must be a Pubkey or None")
        if not isinstance(self.fee_recipient, (Pubkey, type(None))):
            raise TypeError("fee_recipient must be a Pubkey or None")
