# Copyright Spraay Protocol
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Spraay batch payment tool."""

from unittest.mock import MagicMock, patch

import pytest

from strands_spraay.tool import (
    _calculate_fee,
    _validate_recipients,
    spraay_batch_payment,
)


class TestCalculateFee:
    """Test protocol fee calculation."""

    def test_fee_calculation(self):
        assert _calculate_fee(10000) == 30

    def test_fee_zero(self):
        assert _calculate_fee(0) == 0

    def test_fee_rounding_down(self):
        assert _calculate_fee(100) == 0

    def test_fee_large_amount(self):
        one_eth = 10**18
        expected = (one_eth * 30) // 10_000
        assert _calculate_fee(one_eth) == expected


class TestValidateRecipients:
    """Test recipient validation."""

    def setup_method(self):
        self.mock_w3 = MagicMock()
        self.mock_w3.is_address.return_value = True
        self.mock_w3.to_checksum_address.side_effect = lambda x: x

    def test_empty_recipients(self):
        with pytest.raises(ValueError, match="empty"):
            _validate_recipients(self.mock_w3, [])

    def test_too_many_recipients(self):
        recipients = [f"0x{i:040x}" for i in range(201)]
        with pytest.raises(ValueError, match="200"):
            _validate_recipients(self.mock_w3, recipients)

    def test_invalid_address(self):
        self.mock_w3.is_address.return_value = False
        with pytest.raises(ValueError, match="Invalid address"):
            _validate_recipients(self.mock_w3, ["invalid_address"])

    def test_valid_recipients(self):
        addrs = ["0x1234567890abcdef1234567890abcdef12345678"]
        result = _validate_recipients(self.mock_w3, addrs)
        assert len(result) == 1

    def test_max_recipients_allowed(self):
        recipients = [f"0x{i:040x}" for i in range(200)]
        result = _validate_recipients(self.mock_w3, recipients)
        assert len(result) == 200


class TestSpraayBatchPayment:
    """Test main tool entry point."""

    def test_unknown_action(self):
        result = spraay_batch_payment(
            action="invalid",
            recipients=["0x1234567890abcdef1234567890abcdef12345678"],
        )
        assert result["status"] == "error"
        assert "Unknown action" in result["error"]

    def test_missing_private_key(self):
        result = spraay_batch_payment(
            action="batch_eth",
            recipients=["0x1234567890abcdef1234567890abcdef12345678"],
            amount="0.01",
        )
        assert result["status"] == "error"

    @patch("strands_spraay.tool._get_w3")
    @patch("strands_spraay.tool._get_account")
    def test_chain_id_mismatch(self, mock_account, mock_w3):
        mock_w3_instance = MagicMock()
        mock_w3_instance.eth.chain_id = 1  # Ethereum mainnet, not Base
        mock_w3.return_value = mock_w3_instance
        mock_account.return_value = MagicMock()

        result = spraay_batch_payment(
            action="batch_eth",
            recipients=["0x1234567890abcdef1234567890abcdef12345678"],
            amount="0.01",
        )
        assert result["status"] == "error"
        assert "chain ID" in result["error"]

    def test_valid_actions_list(self):
        valid = ["batch_eth", "batch_eth_variable", "batch_token", "batch_token_variable"]
        for action in valid:
            result = spraay_batch_payment(
                action=action,
                recipients=["0x1234567890abcdef1234567890abcdef12345678"],
                amount="0.01",
            )
            # Should fail on connection/key, not on action validation
            assert "Unknown action" not in result.get("error", "")
