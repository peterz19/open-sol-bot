import struct
from dataclasses import dataclass
from solbot_common.log import logger

@dataclass
class BondingCurveAccount:
    discriminator: int
    virtual_token_reserves: int
    virtual_sol_reserves: int
    real_token_reserves: int
    real_sol_reserves: int
    token_total_supply: int
    complete: bool

    def get_buy_price(self, amount: int) -> int:
        if self.complete:
            raise Exception("Curve is complete")

        if amount <= 0:
            return 0

        # Calculate the product of virtual reserves
        n = self.virtual_sol_reserves * self.virtual_token_reserves

        # Calculate the new virtual sol reserves after the purchase
        i = self.virtual_sol_reserves + amount

        # Calculate the new virtual token reserves after the purchase
        r = n // i + 1

        # Calculate the amount of tokens to be purchased
        s = self.virtual_token_reserves - r

        # Return the minimum of the calculated tokens and real token reserves
        return min(s, self.real_token_reserves)

    def get_sell_price(self, amount: int, fee_basis_points: int) -> int:
        if self.complete:
            raise Exception("Curve is complete")

        if amount <= 0:
            return 0

        # Calculate the proportional amount of virtual sol reserves to be received
        n = (amount * self.virtual_sol_reserves) // (self.virtual_token_reserves + amount)

        # Calculate the fee amount in the same units
        a = (n * fee_basis_points) // 10000

        # Return the net amount after deducting the fee
        return n - a

    def get_market_cap_sol(self) -> int:
        if self.virtual_token_reserves == 0:
            return 0

        return (self.token_total_supply * self.virtual_sol_reserves) // self.virtual_token_reserves

    def get_final_market_cap_sol(self, fee_basis_points: int) -> int:
        total_sell_value = self.get_buy_out_price(self.real_token_reserves, fee_basis_points)
        total_virtual_value = self.virtual_sol_reserves + total_sell_value
        total_virtual_tokens = self.virtual_token_reserves - self.real_token_reserves

        if total_virtual_tokens == 0:
            return 0

        return (self.token_total_supply * total_virtual_value) // total_virtual_tokens

    def get_buy_out_price(self, amount: int, fee_basis_points: int) -> int:
        sol_tokens = self.real_sol_reserves if amount < self.real_sol_reserves else amount
        total_sell_value = (sol_tokens * self.virtual_sol_reserves) // (
            self.virtual_token_reserves - sol_tokens
        ) + 1
        fee = (total_sell_value * fee_basis_points) // 10000
        return total_sell_value + fee

    @classmethod
    def from_buffer(cls, buffer: bytes) -> "BondingCurveAccount":
        """
        从字节缓冲区解析账户数据
        格式: <Q Q Q Q Q Q ?
        ssQ: unsigned long long (8 bytes)
        ?: boolean (1 byte)
        """
        logger.error(f"Buffer size length: {len(buffer)}")
        logger.error(f"Buffer ===: {buffer}")
        try:
            (
                discriminator,
                virtual_token_reserves,
                virtual_sol_reserves,
                real_token_reserves,
                real_sol_reserves,
                token_total_supply,
                complete,
            ) = struct.unpack("<QQQQQQ?", buffer)

            return cls(
                discriminator=discriminator,
                virtual_token_reserves=virtual_token_reserves,
                virtual_sol_reserves=virtual_sol_reserves,
                real_token_reserves=real_token_reserves,
                real_sol_reserves=real_sol_reserves,
                token_total_supply=token_total_supply,
                complete=complete,
            )
        except struct.error as e:
            raise ValueError(f"Failed to decode buffer: {e}")

