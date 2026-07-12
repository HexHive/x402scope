# When HTTP 402 Meets the Blockchain: Risks on Emerging x402 Payments

This repo contains the **core code for x402scope**, including the **on-chain measurement code referenced in the paper** and **security rule-violation detection scripts**.
It provides measurement scripts for collecting and analyzing x402-related on-chain data, plus security rule-violation checks. It does not include attack or exploit tooling.

For artifact evaluation, evaluators should follow the fixed workflows and commands specified in this Appendix and download the restricted-access version from Zenodo. 
The Appendix defines the version-specific AE workflow, while the repository README provides broader instructions for reuse, extension, and
testing additional or updated facilitator deployments. 

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
git clone <repository-url>
cd x402scope

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration
1. Copy the template to a local configuration file:
```bash
cp config.example.py config.py
```

2. Edit `config.py`:
* **Database**: Fill in `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, and `MYSQL_DB`.
* **RPC Endpoints**: Insert your Alchemy RPC urls for Base and Solana.
* **Private Keys**: Provide your Base and Solana private keys for executing rule checks in `config.py`.
* **Facilitators**: the included template keeps Coinbase fields (`CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`) and `ThirdWeb_Secret_key`; leave unused credential fields blank.

3. Copy/Link the `config.py` to `SecurityViolation` folder:

```
cp config.py SecurityViolation/config.py
```

### Recommended targets and test-account setup

We recommend starting with the bounded Coinbase test targets instead of running the full facilitator list:

| Target | Network | Recommended first test |
|---|---|---|
| `coinbase-test` | Base Sepolia / EVM | Start `server_app_v2.py`, then run `evmclient_v2.py` |
| `coinbase-solanadev` | Solana Devnet | `solana_verify_settle_v2` |

Test accounts are required. Do **not** commit private keys.

1. **Generate EVM test accounts for Base Sepolia.**

   Use an EVM wallet such as Rabby, MetaMask, or another compatible wallet to create/export the test-account private keys. For the full EVM verify/settle test, prepare:

   - `pk1`: funded client/payer private key. For Base Sepolia-only tests, reviewers may use the shared deterministic test key `"1" * 64`, whose address is `0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A`, after funding it with testnet USDC/gas.
   - `pk2`: merchant/server recipient private key
   - `poor_pk`: unfunded or underfunded client private key used for negative checks

   Export any private keys locally and place them only in your private `config.py`. The `"1" * 64` key is only for public testnet experiments and must not be used on mainnet.

2. **Generate Solana Devnet test accounts.**

   The Solana scripts expect base58-encoded private keys in `config.py`. Use the helper script to generate a keypair:

   ```bash
   python3 SecurityViolation/Scripts/generate_solana_keypair.py -o solana-server.json
   ```

   The command prints the Solana public address and the `Private key for config.py` value. It also writes a Solana CLI-style JSON byte-array key file to the `-o` path.

   Generate the required Solana local keys and place the printed base58 private-key strings in `config.py`:

   - `solpk`: funded client/payer private key
   - `solpk_server`: merchant/server recipient private key
   - `poor_pk_sol`: unfunded or underfunded client private key used for negative checks

3. **Fund the test accounts.**

   Use Circle's faucet to obtain testnet USDC:

   - <https://faucet.circle.com/>
   - choose **Ethereum Sepolia** for EVM test USDC used by the Base Sepolia flow
   - choose **Solana Devnet** for Solana Devnet test USDC

   If gas is needed, use the relevant network faucets:

   - Base Sepolia gas: <https://www.alchemy.com/faucets/base-sepolia>
   - Solana Devnet SOL: <https://faucet.solana.com/>

4. **Create Coinbase CDP API credentials.**

   Register at <https://portal.cdp.coinbase.com/> and create secret API keys. Put the generated values in your local `config.py`:

   ```python
   CDP_API_KEY_ID = "..."
   CDP_API_KEY_SECRET = "..."
   ```

5. **Fill `config.py` and local target values.**

   Fill the local keys, RPC endpoints, and Coinbase credentials in `config.py`, then copy it to `SecurityViolation/config.py` as shown above. Also set `pay_to_address` for the selected target in `SecurityViolation/target.py` to the reviewer-controlled merchant/recipient address:

   - `coinbase-test`: EVM recipient address derived from `pk2`
   - `coinbase-solanadev`: Solana recipient address derived from `solpk_server`

6. **Run the read-only preflight check.**

   Before running a state-changing security test, check the local environment
   and selected target. This does not contact an RPC, facilitator, merchant,
   or blockchain:

   ```bash
   python3 SecurityViolation/preflight_check.py -t coinbase-test
   python3 SecurityViolation/preflight_check.py -t coinbase-solanadev
   ```

   The command reports missing dependencies, credentials, addresses, fee-payer
   settings, authorization timing, and the expected CAIP-2 network. It returns
   a non-zero exit status when a required item is missing. For reliable
   verify/settle checks, set `valid_before_offset` to greater than 180 seconds;
   the preflight check warns when it is below 180 seconds.

   For the free-shopping attack, the reviewer should temporarily reduce
   `valid_before_offset` to a small value (for example `8`) and vary it to find
   the boundary where verify succeeds but settle fails. This short value is
   intentional for the attack and should not be treated as the normal default.

7. **Run tests one by one.**

   For the current Coinbase CDP v2 endpoint, start with the v2 local merchant/client flow. Run the server in one terminal and the client in another terminal:

   ```bash
   python3 SecurityViolation/server_app_v2.py -t coinbase-test
   python3 SecurityViolation/evmclient_v2.py -t coinbase-test
   ```

   Then run other direct checks as needed:

   ```bash
   python3 SecurityViolation/verify_settle_base_v2.py -t coinbase-test
   python3 SecurityViolation/verify_settle_solanav2.py -t coinbase-solanadev
   ```

## 3. Experiment Workflow

### Part A: Security Rule Verification (SecurityViolation)
This section reproduces the detection of security rules described in the paper.

1. **Define Config**: ensure your `config.py` includes:

- **Private keys**: `pk1` and `poor_pk` (test payer), `pk2` (recipient), `solpk` and `poor_pk_sol` (Solana payer), and `solpk_server` (recipient)
- **API credentials**:
  - Coinbase: `CDP_API_KEY_ID`, `CDP_API_KEY_SECRET` (for coinbase targets)
  - Thirdweb: `ThirdWeb_Secret_key` (only needed for thirdweb targets; keep it blank otherwise)

2. **Define Targets**: Ensure `target.py` contains the facilitator metadata (API endpoints, network, amount, timing window, and local merchant settings).

The target file provides facilitator metadata and local merchant settings. Merchant `pay_to_address` values are operator-provided test addresses: they are quick to generate and configure, are not intrinsic to x402scope, and are not required for inspecting the preserved evidence. To re-run checks, reviewers should insert their own merchant/test addresses. You may add or customize targets in `target.py` (FacilitatorTarget entries in `FACILITATORS`):

```python
"custom-target": FacilitatorTarget(
    name="my_facilitator",
    facilitator_base="https://your-facilitator.example.com/x402",
    merchant_base="http://127.0.0.1:8001",
    network="base",  # or "base-sepolia", "solana", "solana-devnet"
    price="$0.001",
    pay_to_address="0x...",  # Your merchant/test address
    pay_amount=1000,  # Amount in smallest unit
    threads=1,
    valid_after_offset=-60,
    valid_before_offset=180, # 1 2 3 4 5 6 7 8
    description="my facilitator.",
)
```



3. **Execute Detection**: Run one x402scope test script against one specific target.

Because target configuration is facilitator-specific and may require different credentials, networks, fee-payer settings, and test-account balances, reviewers should **select one target and one test script at a time** rather than running all targets/tests automatically. The test definitions are listed in `SecurityViolation/tests.py`, but the recommended artifact-review workflow is to invoke the corresponding scripts directly.

Example direct invocations:

```bash
# Recommended first EVM/Base Sepolia Coinbase v2 flow:
# terminal 1: local merchant server
python3 SecurityViolation/server_app_v2.py -t coinbase-test

# terminal 2: EVM client flow
python3 SecurityViolation/evmclient_v2.py -t coinbase-test

# Additional EVM/Base Sepolia Coinbase v2 checks
python3 SecurityViolation/verify_settle_base_v2.py -t coinbase-test
python3 SecurityViolation/erc1271testv2.py -t coinbase-test
python3 SecurityViolation/erc6492testv2.py -t coinbase-test

# Legacy/v1-compatible EVM checks for v1-compatible targets
python3 SecurityViolation/verify_settle_base.py -t <v1_compatible_target>
python3 SecurityViolation/erc1271test.py -t <v1_compatible_target>
python3 SecurityViolation/erc6492test.py -t <v1_compatible_target>

# Solana Devnet Coinbase v2 target
python3 SecurityViolation/verify_settle_solanav2.py -t coinbase-solanadev
```

Current security test cases:

| Test ID | Script | Chain / Scope | Purpose |
|---|---|---|---|
| `evm_verify_settle_base` | `verify_settle_base.py` | EVM | Base x402 verify/settle checks. |
| `evm_verify_settle_base_v2` | `verify_settle_base_v2.py` | EVM, x402 v2 | x402 v2 verify/settle checks on EVM targets. |
| `solana_verify_settle` | `verify_settle_solana.py` | Solana | Solana x402 verify/settle checks; requires a configured fee payer. |
| `solana_verify_settle_v2` | `verify_settle_solanav2.py` | Solana, x402 v2 | x402 v2 verify/settle checks on Solana targets; requires a configured fee payer. |
| `evm_6492_test` | `erc6492test.py` | EVM | ERC-6492 validation behavior test. |
| `evm_6492_test_v2` | `erc6492testv2.py` | EVM, x402 v2 | ERC-6492 validation behavior test for x402 v2. |
| `evm_erc1271_test_v2` | `erc1271testv2.py` | EVM, x402 v2 | ERC-1271 signature validation behavior test for x402 v2. |
| `evm_erc1271_test` | `erc1271test.py` | EVM | ERC-1271 signature validation behavior test for legacy/v1-compatible targets. |
| `evm_client_attack_v2` | `evmclient_v2.py` with `server_app_v2.py` | EVM client flow, x402 v2 | Recommended first Coinbase EVM flow; start `server_app_v2.py` separately before running `evmclient_v2.py`. |
| `evm_client_attack` | `evmclient.py` with `server_app.py` | EVM client flow, legacy/v1 | Legacy client flow for v1-compatible targets. |

Supporting scripts:

| Script | Role |
|---|---|
| `basesupport.py` | Optional EVM pre-check for basic facilitator support. |
| `server_app_v2.py` | Local merchant server used by the x402 v2 EVM client-flow test. |
| `server_app.py` | Local merchant server used by the legacy/v1 EVM client-flow test. |

Direct-script template:
```bash
python3 SecurityViolation/<script>.py -t <target_facilitator>
```

For the x402 v2 EVM client-flow test, run the local merchant server in one terminal, then run the client script in another terminal:

```bash
python3 SecurityViolation/server_app_v2.py -t <target_facilitator>
python3 SecurityViolation/evmclient_v2.py -t <target_facilitator>
```

For legacy/v1-compatible targets, use:

```bash
python3 SecurityViolation/server_app.py -t <target_facilitator>
python3 SecurityViolation/evmclient.py -t <target_facilitator>
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

The figure/table reproduction scripts and their required database configuration are documented in [`Measurement/paper_figdata/README.md`](Measurement/paper_figdata/README.md). After completing the measurement workflows above and preparing the processed SQL tables, follow that directory-level README to generate the paper figures, tables, and intermediate CSVs.

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


## License

The source code in this repository is released under the MIT License.