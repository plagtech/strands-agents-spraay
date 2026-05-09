# Copyright Spraay Protocol
# SPDX-License-Identifier: Apache-2.0

"""Spraay batch payment tool for Strands Agents.

Enables AI agents to batch-send ETH or ERC-20 tokens to up to 200 recipients
in a single transaction on Base, with ~80% gas savings vs individual transfers.

Protocol: https://spraay.app
Contract: 0x1646452F98E36A3c9Cfc3eDD8868221E207B5eEC (Base Mainnet)
"""

import json
import logging
import os
from typing import Any

from strands import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPRAAY_CONTRACT_ADDRESS = "0x1646452F98E36A3c9Cfc3eDD8868221E207B5eEC"
BASE_CHAIN_ID = 8453
BASE_RPC_URL_DEFAULT = "https://mainnet.base.org"
PROTOCOL_FEE_BPS = 30  # 0.3%
MAX_RECIPIENTS = 200
MAX_APPROVAL = 2**256 - 1

SPRAAY_ABI = json.loads(
    """[
    {"inputs":[{"internalType":"address[]","name":"recipients","type":"address[]"},
    {"internalType":"uint256","name":"amount","type":"uint256"}],
    "name":"spraayETH","outputs":[],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},
    {"internalType":"address[]","name":"recipients","type":"address[]"},
    {"internalType":"uint256","name":"amount","type":"uint256"}],
    "name":"spraayToken","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address[]","name":"recipients","type":"address[]"},
    {"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
    "name":"spraayETHVariable","outputs":[],"stateMutability":"payable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},
    {"internalType":"address[]","name":"recipients","type":"address[]"},
    {"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
    "name":"spraayTokenVariable","outputs":[],"stateMutability":"nonpayable","type":"function"}
]"""
)

ERC20_ABI = json.loads(
    """[
    {"inputs":[{"internalType":"address","name":"spender","type":"address"},
    {"internalType":"uint256","name":"amount","type":"uint256"}],
    "name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],
    "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"owner","type":"address"},
    {"internalType":"address","name":"spender","type":"address"}],
    "name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
    "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"address","name":"account","type":"address"}],
    "name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
    "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],
    "stateMutability":"view","type":"function"}
]"""
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_w3():
    """Lazy-import web3 and return a connected Web3 instance."""
    from web3 import Web3

    rpc_url = os.environ.get("BASE_RPC_URL", BASE_RPC_URL_DEFAULT)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Base RPC at {rpc_url}")
    return w3


def _get_account(w3):  # type: ignore[no-untyped-def]
    """Get the signing account from environment variables."""
    private_key = os.environ.get("SPRAAY_PRIVATE_KEY") or os.environ.get("PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set SPRAAY_PRIVATE_KEY or PRIVATE_KEY environment variable.")
    return w3.eth.account.from_key(private_key)


def _validate_recipients(w3, recipients: list[str]) -> list[str]:  # type: ignore[no-untyped-def]
    """Validate and checksum recipient addresses."""
    if not recipients:
        raise ValueError("Recipients list cannot be empty.")
    if len(recipients) > MAX_RECIPIENTS:
        raise ValueError(f"Maximum {MAX_RECIPIENTS} recipients allowed.")
    checksummed = []
    for addr in recipients:
        if not w3.is_address(addr):
            raise ValueError(f"Invalid address: {addr}")
        checksummed.append(w3.to_checksum_address(addr))
    return checksummed


def _calculate_fee(total_wei: int) -> int:
    """Calculate the 0.3% protocol fee."""
    return (total_wei * PROTOCOL_FEE_BPS) // 10_000


def _build_and_send(w3, account, tx) -> str:  # type: ignore[no-untyped-def]
    """Sign and send a transaction, return the tx hash hex string."""
    tx["nonce"] = w3.eth.get_transaction_count(account.address)
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.1)  # 10% buffer
    tx["gasPrice"] = w3.eth.gas_price
    tx["chainId"] = BASE_CHAIN_ID
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.to_hex(tx_hash)


def _ensure_approval(w3, account, token_addr: str, needed: int) -> str | None:  # type: ignore[no-untyped-def]
    """Check allowance and approve if necessary. Returns approval tx hash or None."""
    token_contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    allowance = token_contract.functions.allowance(account.address, SPRAAY_CONTRACT_ADDRESS).call()
    if allowance < needed:
        approve_tx = token_contract.functions.approve(SPRAAY_CONTRACT_ADDRESS, MAX_APPROVAL).build_transaction(
            {"from": account.address}
        )
        return _build_and_send(w3, account, approve_tx)
    return None


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _batch_eth(w3, account, recipients: list[str], amount_str: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    checksummed = _validate_recipients(w3, recipients)
    amount_wei = w3.to_wei(amount_str, "ether")
    if amount_wei <= 0:
        return {"status": "error", "error": "Amount must be greater than 0."}
    total_wei = amount_wei * len(checksummed)
    fee_wei = _calculate_fee(total_wei)
    contract = w3.eth.contract(address=SPRAAY_CONTRACT_ADDRESS, abi=SPRAAY_ABI)
    tx = contract.functions.spraayETH(checksummed, amount_wei).build_transaction(
        {"from": account.address, "value": total_wei + fee_wei}
    )
    tx_hash = _build_and_send(w3, account, tx)
    return {
        "status": "success",
        "tx_hash": tx_hash,
        "recipients_count": len(checksummed),
        "amount_per_recipient": amount_str,
        "total_eth": str(w3.from_wei(total_wei + fee_wei, "ether")),
    }


def _batch_eth_variable(w3, account, recipients: list[str], amounts_str: list[str]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    checksummed = _validate_recipients(w3, recipients)
    if len(amounts_str) != len(checksummed):
        return {"status": "error", "error": "Amounts and recipients length mismatch."}
    amounts_wei = [w3.to_wei(a, "ether") for a in amounts_str]
    if any(a <= 0 for a in amounts_wei):
        return {"status": "error", "error": "All amounts must be greater than 0."}
    total_wei = sum(amounts_wei)
    fee_wei = _calculate_fee(total_wei)
    contract = w3.eth.contract(address=SPRAAY_CONTRACT_ADDRESS, abi=SPRAAY_ABI)
    tx = contract.functions.spraayETHVariable(checksummed, amounts_wei).build_transaction(
        {"from": account.address, "value": total_wei + fee_wei}
    )
    tx_hash = _build_and_send(w3, account, tx)
    return {
        "status": "success",
        "tx_hash": tx_hash,
        "recipients_count": len(checksummed),
        "total_eth": str(w3.from_wei(total_wei + fee_wei, "ether")),
    }


def _batch_token(w3, account, recipients: list[str], amount_str: str, token_address: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    checksummed = _validate_recipients(w3, recipients)
    token_addr = w3.to_checksum_address(token_address)
    token_contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    decimals = token_contract.functions.decimals().call()
    amount_units = int(float(amount_str) * (10**decimals))
    if amount_units <= 0:
        return {"status": "error", "error": "Amount must be greater than 0."}
    total_units = amount_units * len(checksummed)
    fee_units = _calculate_fee(total_units)
    approval_hash = _ensure_approval(w3, account, token_addr, total_units + fee_units)
    contract = w3.eth.contract(address=SPRAAY_CONTRACT_ADDRESS, abi=SPRAAY_ABI)
    tx = contract.functions.spraayToken(token_addr, checksummed, amount_units).build_transaction(
        {"from": account.address}
    )
    tx_hash = _build_and_send(w3, account, tx)
    result: dict[str, Any] = {
        "status": "success",
        "tx_hash": tx_hash,
        "recipients_count": len(checksummed),
        "amount_per_recipient": amount_str,
        "token_address": token_address,
    }
    if approval_hash:
        result["approval_tx_hash"] = approval_hash
    return result


def _batch_token_variable(w3, account, recipients: list[str], amounts_str: list[str], token_address: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    checksummed = _validate_recipients(w3, recipients)
    if len(amounts_str) != len(checksummed):
        return {"status": "error", "error": "Amounts and recipients length mismatch."}
    token_addr = w3.to_checksum_address(token_address)
    token_contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    decimals = token_contract.functions.decimals().call()
    amounts_units = [int(float(a) * (10**decimals)) for a in amounts_str]
    if any(a <= 0 for a in amounts_units):
        return {"status": "error", "error": "All amounts must be greater than 0."}
    total_units = sum(amounts_units)
    fee_units = _calculate_fee(total_units)
    approval_hash = _ensure_approval(w3, account, token_addr, total_units + fee_units)
    contract = w3.eth.contract(address=SPRAAY_CONTRACT_ADDRESS, abi=SPRAAY_ABI)
    tx = contract.functions.spraayTokenVariable(token_addr, checksummed, amounts_units).build_transaction(
        {"from": account.address}
    )
    tx_hash = _build_and_send(w3, account, tx)
    result: dict[str, Any] = {
        "status": "success",
        "tx_hash": tx_hash,
        "recipients_count": len(checksummed),
        "token_address": token_address,
    }
    if approval_hash:
        result["approval_tx_hash"] = approval_hash
    return result


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------

ACTION_MAP = {
    "batch_eth": lambda w3, acct, inp: _batch_eth(w3, acct, inp["recipients"], inp["amount"]),
    "batch_eth_variable": lambda w3, acct, inp: _batch_eth_variable(w3, acct, inp["recipients"], inp["amounts"]),
    "batch_token": lambda w3, acct, inp: _batch_token(w3, acct, inp["recipients"], inp["amount"], inp["token_address"]),
    "batch_token_variable": lambda w3, acct, inp: _batch_token_variable(
        w3, acct, inp["recipients"], inp["amounts"], inp["token_address"]
    ),
}


@tool
def spraay_batch_payment(
    action: str,
    recipients: list[str],
    amount: str = "",
    amounts: list[str] | None = None,
    token_address: str = "",
) -> dict[str, Any]:
    """Send batch payments on Base using Spraay Protocol.

    Batch-send ETH or ERC-20 tokens to up to 200 recipients in a single
    transaction with ~80% gas savings. 0.3% protocol fee.

    Args:
        action: The batch action — 'batch_eth', 'batch_eth_variable',
                'batch_token', or 'batch_token_variable'.
        recipients: List of recipient wallet addresses (max 200).
        amount: Amount per recipient for equal-amount actions (e.g. '0.01').
        amounts: List of amounts for variable-amount actions. Must match recipients length.
        token_address: ERC-20 token contract address (required for token actions).

    Returns:
        Dict containing status, tx_hash, and transaction details.
    """
    if action not in ACTION_MAP:
        return {"status": "error", "error": f"Unknown action '{action}'. Use one of: {list(ACTION_MAP.keys())}"}

    try:
        w3 = _get_w3()
        account = _get_account(w3)

        # Verify chain ID
        chain_id = w3.eth.chain_id
        if chain_id != BASE_CHAIN_ID:
            return {
                "status": "error",
                "error": (
                    f"RPC chain ID {chain_id} does not match Base ({BASE_CHAIN_ID}). "
                    "Check your BASE_RPC_URL configuration."
                ),
            }

        inp: dict[str, Any] = {
            "recipients": recipients,
            "amount": amount,
            "amounts": amounts or [],
            "token_address": token_address,
        }

        return ACTION_MAP[action](w3, account, inp)

    except Exception as e:
        logger.exception("Spraay batch payment failed")
        return {"status": "error", "error": str(e)}
