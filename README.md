# # When HTTP 402 Meets the Blockchain: Risks on Emerging x402 Payments

This repo contains the **core code for x402scope**, including the **on-chain measurement code referenced in the paper** and **security rule-violation detection scripts**.
It provides measurement scripts for collecting and analyzing x402-related on-chain data, plus security rule-violation checks. It does not include attack or exploit tooling.

## Repository Structure
- `Measurement/`: Core scripts for blockchain data ingestion (ETL), database management, and statistical analysis.
- `Measurement/paper_figdata/`: Scripts specifically tuned to generate the data points for Figures 3-6 and Tables 3-5 in the paper.
- `SecurityViolation/`: core code for x402scope for detecting and verifying security rule violations against live x402 facilitators.
- `requirements.txt` Python dependencies.
- `config.example.py`: Example template for configuration and API keys.

## 1. Prerequisites

### Hardware & OS
* **OS**: Linux (Ubuntu 22.04+ recommended).
* **Python**: Version 3.10 or higher.
* **Storage**: At least **1TB SSD** is recommended if reproducing the full blockchain data ingestion (Base block history and Solana transaction history).
* **Database**: A running **MariaDB** (or MySQL) instance.

### External Services
To reproduce the measurement results, you require access to high-performance RPC nodes. The scripts perform heavy historical data fetching.

* **Base RPC**: An **Alchemy Base Mainnet** endpoint is required for stable block and receipts downloading.
* **Solana RPC**: We recommend an **Alchemy Solana Archival Node**.

## 2. Installation & Setup

### Environment Setup
Clone the repository and install dependencies:

```bash
git clone https://github.com/HexHive/x402scope.git
cd x402scope

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration
1. Copy the template to a usable config file:
```bash
cp config.example.py config.py
```

2. Edit `config.py`:
* **Database**: Fill in `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, and `MYSQL_DB`.
* **RPC Endpoints**: Insert your Alchemy RPC urls for Base and Solana.
* **Private Keys**: Provide your Base and Solana private keys for executing rule checks in `config.py`.
* **Facilitators**: Coinbase and ThridWeb requires API keys to use their facilitator services.

3. Copy/Link the `config.py` to `SecurityViolation` folder:

```
ln -s config.py SecurityViolation/config.py
```

## 3. Experiment Workflow

### Part A: Security Rule Verification (SecurityViolation)
This section reproduces the detection of security rules described in the paper.

1. **Define Config**: ensure your `config.py` includes:

- **Private keys**: `pk1` and `poor_pk` (test payer), `pk2` (recipient), `solpk` and `poor_pk_sol` (Solana payer), and `solpk_server` (recipient)
- **API credentials**:
  - Coinbase: `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET` (for coinbase targets)
  - Thirdweb: `ThidWeb_Secret_key` (for thirdweb targets)

2. **Define Targets**: Ensure `target.py` contains the facilitator metadata (Pay-to address, API endpoints).
You may need to add or customize targets in `target.py` (FacilitatorTarget entries in FACILITATORS dict):

```python
"custom-target": FacilitatorTarget(
    name="my_facilitator",
    facilitator_base="https://your-facilitator.example.com/x402",
    merchant_base="http://127.0.0.1:8001",
    network="base",  # or "base-sepolia", "solana", "solana-devnet"
    price="$0.001",
    pay_to_address="0x...",  # Merchant address
    pay_amount=1000,  # Amount in smallest unit
    threads=1,
    valid_after_offset=-60,
    valid_before_offset=180, # 1 2 3 4 5 6 7 8
    description="my facilitator.",
)
```



3. **Execute Detection**: Run the x402scope script against a specific target.

You can use the unified runner:
```bash
python3 SecurityViolation/run.py -t <target_facilitator>
```

Optional: run the basesupport matrix (pay_amount=0, valid_before_offset=1..10):
```bash
python3 SecurityViolation/run.py -t <target_facilitator> --support-matrix
```

Run a specific subset of tests:
```bash
python3 SecurityViolation/run.py -t <target_facilitator> --tests evm_erc1271_test,evm_6492_test
```

Default tests are defined in `SecurityViolation/tests.py` (EVM/Solana verify+settle, ERC-1271, ERC-6492, and the EVM client flow).

You can also run any test script directly:
```bash
python3 SecurityViolation/<script>.py -t <target_facilitator>
```

### Part B: Empirical Measurement (Base)
This workflow reproduces the data collection for the Base network (Block height > 30M, approx. 2025/05/09).

1. **Ingest Raw Data**:
Download blocks and filter for facilitator interactions.
```bash
cd Measurement/
python3 base_downloadblocks.py # Connects to Alchemy Base RPC
python3 x402fetchtxs.py # Filters txs by facilitator EOAs
```

2. **Verify Integrity**:
Ensure the nonce consecutiveness so that no blocks were skipped due to RPC timeouts.
```bash
python3 base_confirmintegrity.py
```

3. **Process Metadata**:
Fetch transaction receipts to determine success status, revert reasons, and gas usage.
```bash
python3 base_updatestatus.py
python3 base_updaterevertreason.py
```

4. **Generate Statistics**:
```bash
mysql -h <host> -p < base_stattable.sql
```

### Part C: Empirical Measurement (Solana)
This workflow reproduces the data collection for the Solana network.

1. **Fetch Transaction History**:
Uses `getSignaturesForAddress` to sync facilitator history. *Note: This step benefits significantly from Alchemy's specialized archive infrastructure.*
```bash
python3 sol_fetchtxs.py
```

2. **Analyze Token Accounts (ATAs)**:
Investigate "Token Account Creation Abuse" and rent exemptions.
```bash
mysql -h <host> -p < sol_atatable.sql
python3 sol_atafetch.py
python3 sol_failed.py
```

3. **Generate Statistics**:
```bash
mysql -h <host> -p < sol_stattable.sql
```

## 4. Reproducing Paper Results

The following scripts in `Measurement/paper_figdata/` query the processed SQL tables to generate the exact data points used in the paper's figures and tables.

| Paper Element | Description | Script Command |
| :--- | :--- | :--- |
| **Figure 3** | Growth of x402 transaction activity & volume | `python3 transaction_activity.py` |
| **Figure 4** | Top-10 Facilitators by volume | `python3 top_facilitators.py` |
| **Figure 5** | Gas consumption comparison (Base vs. Sol) | `python3 gas_consumption.py` <br> `python3 daily_gas_fee_trend.py` |
| **Figure 6** | Revert reason distribution | `python3 revert_statistics.py` |
| **Table 4** | Revert statistics summary | `python3 revert_statistics.py` |
| **Table 5** | ATA Rent Events (Sponsor costs) | `python3 ATA_rent_events.py` |
| **Table 6** | ATA Creation Abuse (Scale) | `python3 ATA_owner_distribution.py` |

## Notes
* **API Limits**: The measurement scripts are optimized for commercial RPC providers (Alchemy). If using free-tier endpoints, you may need to adjust concurrency settings (e.g., `RPCSIZE`) in the scripts to avoid rate-limiting (HTTP 429).
* **Security**: The `SecurityViolation` scripts are for educational and verification purposes only. Do not run these against production services without explicit authorization.
* **Credentials**: Never commit `config.py` containing your private keys or RPC secrets.
* **Full Version**: For ethical considerations, some mutation/PoC components are sanitized in this release. If researchers need access to the full codebase, please contact us via the paper contact email or request access to the restricted Zenodo artifact.

## Artifact Release Channels

The artifact follows the release channels described in the paper's Open-Science section:

1. **Public Zenodo record**: [Zenodo record 20328962](https://zenodo.org/records/20328962) contains the sanitized, non-sensitive public artifact, including the x402scope framework, configuration template, execution instructions, measurement code, MariaDB schema/query scripts, and figure/table regeneration code.
2. **GitHub repository**: [HexHive/x402scope](https://github.com/HexHive/x402scope) mirrors the same non-sensitive public artifact and will be maintained long term.
3. **Restricted-access Zenodo record**: [Zenodo record 20329071](https://zenodo.org/records/20329071) contains the full x402scope codebase and sensitive validation records for controlled access.

## Sanitization Notice

This public repository is the sanitized, non-sensitive release of the x402scope artifact. It intentionally omits sensitive validation records, exact evaluation target configurations, per-facilitator security-rule pass/fail matrices, HTTP and on-chain evidence logs, adjudication records, and exploit-enabling materials. These materials are provided separately through the restricted-access Zenodo record to support independent assessment while reducing the risk of abuse against live x402 payment infrastructure.
