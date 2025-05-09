"""交易分析器

负责解析交易的具体内容，包括：
1. 分析交易输入输出
2. 计算实际的交易数量
3. 提取其他重要的交易信息
"""

from typing import TypedDict

from solbot_common.constants import SOL_DECIMAL, WSOL
from solbot_common.utils.helius import HeliusAPI

# [
#   {
#     "description": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg swapped 0.001 SOL for 3.689514 GFUgXbMeDnLkhZaJS3nYFqunqkFNMRo9ukhyajeXpump",
#     "type": "SWAP",
#     "source": "RAYDIUM",
#     "fee": 305000,
#     "feePayer": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#     "signature": "3byYeiXfEUW2ykRKvvHs7UYPt5CsVNBZvKFP5ANvESjVbgFbpkTfLXsUaNu6FjbWTrdxj72UPQtj8dzXfHGajnpF",
#     "slot": 310105416,
#     "timestamp": 1735290280,
#     "tokenTransfers": [
#       {
#         "fromTokenAccount": "6fMtMUiZR3KfvAk9z7Upx2k8SDf1E6E5rcu4fedMaG9g",
#         "toTokenAccount": "9w1QyPL16ZPgjjjoKse1T1G5kVQRCBVLwGhMVUuvUXd3",
#         "fromUserAccount": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#         "toUserAccount": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
#         "tokenAmount": 0.001,
#         "mint": "So11111111111111111111111111111111111111112",
#         "tokenStandard": "Fungible"
#       },
#       {
#         "fromTokenAccount": "EF8m8beMNBMoVaaAAGeoAznxpx6eUNVQ3RgQPcxAMZw9",
#         "toTokenAccount": "4Y1ypoSop5JezbosNUqMqNvWoiBzhL5d1LFC2NCtE6Fq",
#         "fromUserAccount": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
#         "toUserAccount": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#         "tokenAmount": 3.689514,
#         "mint": "GFUgXbMeDnLkhZaJS3nYFqunqkFNMRo9ukhyajeXpump",
#         "tokenStandard": "Fungible"
#       }
#     ],
#     "nativeTransfers": [
#       {
#         "fromUserAccount": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#         "toUserAccount": "BB5dnY55FXS1e1NXqZDwCzgdYJdMCj3B92PU6Q5Fb6DT",
#         "amount": 10000
#       }
#     ],
#     "accountData": [
#       {
#         "account": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#         "nativeBalanceChange": -1315000,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "6fMtMUiZR3KfvAk9z7Upx2k8SDf1E6E5rcu4fedMaG9g",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "9DCxsMizn3H1hprZ7xWe6LDzeUeZBksYFpBWBtSf1PQX",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "4Y1ypoSop5JezbosNUqMqNvWoiBzhL5d1LFC2NCtE6Fq",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": [
#           {
#             "userAccount": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#             "tokenAccount": "4Y1ypoSop5JezbosNUqMqNvWoiBzhL5d1LFC2NCtE6Fq",
#             "rawTokenAmount": {
#               "tokenAmount": "3689514",
#               "decimals": 6
#             },
#             "mint": "GFUgXbMeDnLkhZaJS3nYFqunqkFNMRo9ukhyajeXpump"
#           }
#         ]
#       },
#       {
#         "account": "ComputeBudget111111111111111111111111111111",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "11111111111111111111111111111111",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "BB5dnY55FXS1e1NXqZDwCzgdYJdMCj3B92PU6Q5Fb6DT",
#         "nativeBalanceChange": 10000,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "66NGSPspUYoF4rAAUa4So2XjkMtc9u5EpVjcg8N8dhCJ",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "9Frt99T7Z9if73GeBymnjTdSaiZaLayLpYpCtnxKEzvg",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "9w1QyPL16ZPgjjjoKse1T1G5kVQRCBVLwGhMVUuvUXd3",
#         "nativeBalanceChange": 1000000,
#         "tokenBalanceChanges": [
#           {
#             "userAccount": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
#             "tokenAccount": "9w1QyPL16ZPgjjjoKse1T1G5kVQRCBVLwGhMVUuvUXd3",
#             "rawTokenAmount": {
#               "tokenAmount": "1000000",
#               "decimals": 9
#             },
#             "mint": "So11111111111111111111111111111111111111112"
#           }
#         ]
#       },
#       {
#         "account": "EF8m8beMNBMoVaaAAGeoAznxpx6eUNVQ3RgQPcxAMZw9",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": [
#           {
#             "userAccount": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
#             "tokenAccount": "EF8m8beMNBMoVaaAAGeoAznxpx6eUNVQ3RgQPcxAMZw9",
#             "rawTokenAmount": {
#               "tokenAmount": "-3689514",
#               "decimals": 6
#             },
#             "mint": "GFUgXbMeDnLkhZaJS3nYFqunqkFNMRo9ukhyajeXpump"
#           }
#         ]
#       },
#       {
#         "account": "CdNDXyc9v52LcUnNiRgjVt2kqafTkPocaRR882izSBTJ",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "9JaC9jwtstwqAxjLDoDzXP1eYfZRfi2GLgGXogDM3Trb",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "DLumRgy7PvNMU1Gp5op8Syb7PD2Tqj7DUm6x8MGzcYvj",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "Av1NaTRYgdviyuLfVanw65dL22SGWYsip9GQEeZospBr",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "9AGXis3MNoFBuSu6GyVLvdXYWDocrxcgGnz4ieeJJAnM",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "6hp3pF5XBT4BNUPiwhNLAqcxBh2T5QmHxnioD5G5NswW",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "SysvarRent111111111111111111111111111111111",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "So11111111111111111111111111111111111111112",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       },
#       {
#         "account": "3WYKDwGpKM2m4Kf3bLwQoD4Hci4QBheP2ujdgwxEy5gy",
#         "nativeBalanceChange": 0,
#         "tokenBalanceChanges": []
#       }
#     ],
#     "transactionError": null,
#     "instructions": [
#       {
#         "accounts": [],
#         "data": "3QCwqmHZ4mdq",
#         "programId": "ComputeBudget111111111111111111111111111111",
#         "innerInstructions": []
#       },
#       {
#         "accounts": [],
#         "data": "Kq1GWK",
#         "programId": "ComputeBudget111111111111111111111111111111",
#         "innerInstructions": []
#       },
#       {
#         "accounts": [
#           "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#           "6fMtMUiZR3KfvAk9z7Upx2k8SDf1E6E5rcu4fedMaG9g"
#         ],
#         "data": "3ipZX9UbHT6idhJNYkpSNyLgzFkkJyrjohQtzzxk9976vaxEjD7TWc6CebnSPnCrD14TfPsxkSpouU2SRfFX8HqwNNyxtxRMjBriF3FRQBUBTdkcmWvY6XrMD4qPfaoH7dhUCrLt1oMbs8nwo6XyKa9ebyKv9WnroJDjVj7tt",
#         "programId": "11111111111111111111111111111111",
#         "innerInstructions": []
#       },
#       {
#         "accounts": [
#           "6fMtMUiZR3KfvAk9z7Upx2k8SDf1E6E5rcu4fedMaG9g",
#           "So11111111111111111111111111111111111111112",
#           "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#           "SysvarRent111111111111111111111111111111111"
#         ],
#         "data": "2",
#         "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
#         "innerInstructions": []
#       },
#       {
#         "accounts": [
#           "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
#           "66NGSPspUYoF4rAAUa4So2XjkMtc9u5EpVjcg8N8dhCJ",
#           "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
#           "9Frt99T7Z9if73GeBymnjTdSaiZaLayLpYpCtnxKEzvg",
#           "9DCxsMizn3H1hprZ7xWe6LDzeUeZBksYFpBWBtSf1PQX",
#           "9w1QyPL16ZPgjjjoKse1T1G5kVQRCBVLwGhMVUuvUXd3",
#           "EF8m8beMNBMoVaaAAGeoAznxpx6eUNVQ3RgQPcxAMZw9",
#           "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX",
#           "CdNDXyc9v52LcUnNiRgjVt2kqafTkPocaRR882izSBTJ",
#           "9JaC9jwtstwqAxjLDoDzXP1eYfZRfi2GLgGXogDM3Trb",
#           "DLumRgy7PvNMU1Gp5op8Syb7PD2Tqj7DUm6x8MGzcYvj",
#           "Av1NaTRYgdviyuLfVanw65dL22SGWYsip9GQEeZospBr",
#           "9AGXis3MNoFBuSu6GyVLvdXYWDocrxcgGnz4ieeJJAnM",
#           "6hp3pF5XBT4BNUPiwhNLAqcxBh2T5QmHxnioD5G5NswW",
#           "3WYKDwGpKM2m4Kf3bLwQoD4Hci4QBheP2ujdgwxEy5gy",
#           "6fMtMUiZR3KfvAk9z7Upx2k8SDf1E6E5rcu4fedMaG9g",
#           "4Y1ypoSop5JezbosNUqMqNvWoiBzhL5d1LFC2NCtE6Fq",
#           "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg"
#         ],
#         "data": "63SfuT4qF7xKWqPb3WZW5Ku",
#         "programId": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
#         "innerInstructions": [
#           {
#             "accounts": [
#               "6fMtMUiZR3KfvAk9z7Upx2k8SDf1E6E5rcu4fedMaG9g",
#               "9w1QyPL16ZPgjjjoKse1T1G5kVQRCBVLwGhMVUuvUXd3",
#               "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg"
#             ],
#             "data": "3QCwqmHZ4mdq",
#             "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
#           },
#           {
#             "accounts": [
#               "EF8m8beMNBMoVaaAAGeoAznxpx6eUNVQ3RgQPcxAMZw9",
#               "4Y1ypoSop5JezbosNUqMqNvWoiBzhL5d1LFC2NCtE6Fq",
#               "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
#             ],
#             "data": "3LXuNgQTeivs",
#             "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
#           }
#         ]
#       },
#       {
#         "accounts": [
#           "6fMtMUiZR3KfvAk9z7Upx2k8SDf1E6E5rcu4fedMaG9g",
#           "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#           "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg"
#         ],
#         "data": "A",
#         "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
#         "innerInstructions": []
#       },
#       {
#         "accounts": [
#           "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#           "BB5dnY55FXS1e1NXqZDwCzgdYJdMCj3B92PU6Q5Fb6DT"
#         ],
#         "data": "3Bxs43ZMjSRQLs6o",
#         "programId": "11111111111111111111111111111111",
#         "innerInstructions": []
#       }
#     ],
#     "events": {
#       "swap": {
#         "nativeInput": {
#           "account": "HyygEkpVJJpuUyUYdAWQTZMwX4Ee1BS9ND7Yd2YdkWQg",
#           "amount": "1000000"
#         },
#         "nativeOutput": null,
#         "tokenInputs": [],
#         "tokenOutputs": [
#           {
#             "userAccount": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
#             "tokenAccount": "EF8m8beMNBMoVaaAAGeoAznxpx6eUNVQ3RgQPcxAMZw9",
#             "rawTokenAmount": {
#               "tokenAmount": "3689514",
#               "decimals": 6
#             },
#             "mint": "GFUgXbMeDnLkhZaJS3nYFqunqkFNMRo9ukhyajeXpump"
#           }
#         ],
#         "nativeFees": [],
#         "tokenFees": [],
#         "innerSwaps": []
#       }
#     }
#   }
# ]


class Result(TypedDict):
    fee: int
    slot: int
    timestamp: int
    sol_change: float
    swap_sol_change: float
    other_sol_change: float
    token_change: float


class TransactionAnalyzer:
    """交易分析器"""

    def __init__(self) -> None:
        self.helius_api = HeliusAPI()

    async def analyze_transaction(self, tx_signature: str, user_account: str, mint: str) -> Result:
        """分析交易详情

        Args:
            tx_signature: 交易签名
        """
        # 获取交易详情
        tx_details = await self.helius_api.get_parsed_transaction(tx_signature)
        if len(tx_details) == 0:
            raise Exception("交易不存在")
        tx_detail = tx_details[0]
        fee = tx_detail["fee"]
        slot = tx_detail["slot"]
        timestamp = tx_detail["timestamp"]
        tx_type = tx_detail["type"]
        if tx_type != "SWAP":
            raise NotImplementedError(f"不支持的交易类型: {tx_type}")

        sol_change = 0
        token_change = 0
        swap_sol_change = 0
        token_transfers = tx_detail["tokenTransfers"]

        # 检查用户是转出代币（卖出）还是接收代币（买入）
        is_sell = False
        is_buy = False


        for token_transfer in token_transfers:
            # Buy
            if token_transfer["fromUserAccount"] == user_account and token_transfer["mint"] == str(
                WSOL
            ):
                sol_change -= token_transfer["tokenAmount"]
                swap_sol_change -= token_transfer["tokenAmount"]
            elif token_transfer["toUserAccount"] == user_account and token_transfer["mint"] == mint:
                token_change += token_transfer["tokenAmount"]
            # Sell
            elif (
                token_transfer["fromUserAccount"] == user_account and token_transfer["mint"] == mint
            ):
                token_change -= token_transfer["tokenAmount"]
            elif token_transfer["toUserAccount"] == user_account and token_transfer["mint"] == str(
                WSOL
            ):
                sol_change += token_transfer["tokenAmount"]
                swap_sol_change += token_transfer["tokenAmount"]

        for native_transfer in tx_detail["nativeTransfers"]:
            if native_transfer["fromUserAccount"] == user_account:
                sol_change -= native_transfer["amount"] / SOL_DECIMAL
            elif native_transfer["toUserAccount"] == user_account:
                sol_change += native_transfer["amount"] / SOL_DECIMAL

        return {
            "fee": fee,
            "slot": slot,
            "timestamp": timestamp,
            "sol_change": sol_change,
            "swap_sol_change": swap_sol_change,
            "other_sol_change": sol_change - swap_sol_change,
            "token_change": token_change,
        }
