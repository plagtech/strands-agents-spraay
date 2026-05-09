# 💧 Strands Agents Spraay

[![PyPI version](https://img.shields.io/pypi/v/strands-agents-spraay)](https://pypi.org/project/strands-agents-spraay/)
[![License](https://img.shields.io/github/license/plagtech/strands-agents-spraay)](LICENSE)

**Spraay batch payment tool for [Strands Agents](https://strandsagents.com/)** — send ETH or ERC-20 tokens to up to 200 recipients in a single transaction on Base with ~80% gas savings.

## Installation

```bash
pip install strands-agents-spraay
```

## Quick Start

```python
from strands import Agent
from strands_spraay import spraay_batch_payment

agent = Agent(tools=[spraay_batch_payment])

# The agent can now handle batch payment requests
agent("Send 0.01 ETH to 0xAAA..., 0xBBB..., and 0xCCC... using batch payment")
```

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `SPRAAY_PRIVATE_KEY` or `PRIVATE_KEY` | Wallet private key for signing transactions | Yes |
| `BASE_RPC_URL` | Base RPC endpoint | No (defaults to `https://mainnet.base.org`) |

## Actions

| Action | Description |
|---|---|
| `batch_eth` | Send equal ETH to all recipients |
| `batch_eth_variable` | Send different ETH amounts per recipient |
| `batch_token` | Send equal ERC-20 tokens to all recipients |
| `batch_token_variable` | Send different token amounts per recipient |

## Direct Tool Usage

```python
from strands import Agent
from strands_spraay import spraay_batch_payment

agent = Agent(tools=[spraay_batch_payment])

# Equal ETH batch
agent.tool.spraay_batch_payment(
    action="batch_eth",
    recipients=["0xAAA...", "0xBBB..."],
    amount="0.01"
)

# Variable ETH batch
agent.tool.spraay_batch_payment(
    action="batch_eth_variable",
    recipients=["0xAAA...", "0xBBB..."],
    amounts=["0.01", "0.05"]
)

# Equal token batch (USDC on Base)
agent.tool.spraay_batch_payment(
    action="batch_token",
    recipients=["0xAAA...", "0xBBB..."],
    amount="100",
    token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
)

# Variable token batch
agent.tool.spraay_batch_payment(
    action="batch_token_variable",
    recipients=["0xAAA...", "0xBBB..."],
    amounts=["100", "250"],
    token_address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
)
```

## Features

- **Up to 200 recipients** per transaction
- **~80% gas savings** vs individual transfers
- **Automatic token approval** handling for ERC-20 transfers
- **0.3% protocol fee**
- **Full input validation** — address format, recipient limits, amount checks
- **Chain ID verification** — prevents sending to wrong network
- **10% gas buffer** on estimates to prevent out-of-gas errors
- **Environment-based config** — RPC URL, private key via env vars

## Protocol Details

- **Contract**: [`0x1646452F98E36A3c9Cfc3eDD8868221E207B5eEC`](https://basescan.org/address/0x1646452F98E36A3c9Cfc3eDD8868221E207B5eEC) (Base Mainnet)
- **Chain**: Base (Chain ID 8453)
- **Website**: [spraay.app](https://spraay.app)

## Development

```bash
# Clone and install
git clone https://github.com/plagtech/strands-agents-spraay.git
cd strands-agents-spraay
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Format & lint
hatch run prepare
```

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
