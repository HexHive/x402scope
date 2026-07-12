# x402 Measurement Reproduction

This directory contains the scripts used to reproduce the measurement CSVs, Figures 3--7, and Tables 4--6. The scripts query a MySQL-compatible `x402db` database through `../runsql.py` and write outputs under this directory.

## 1. Database configuration

Before running these scripts, install the project dependencies from the repository root:

```bash
cd Measurement/paper_figdata
```

Create a private `config.py` in this directory:

```bash
cp config.example.py config.py
chmod 600 config.py
```

Fill in the guest database credentials supplied with the artifact:

```python
MYSQL_HOST = "<db-host>"
MYSQL_PORT = <db-port>
MYSQL_USER = "<db-user>"
MYSQL_PASSWORD = "<db-password>"
MYSQL_DB = "x402db"
```

Quick connection check:

```bash
PYTHONPATH=.. python - <<'PY'
from runsql import runsql
print(runsql("SELECT 1;"))
print(runsql("SELECT DATABASE();"))
PY
```

Expected output shape:

```text
[(1,)]
[('x402db',)]
```

## 2. Generate measurement CSVs

Run from this directory after installing dependencies:

```bash
python transaction_activity.py
python daily_gas_fee_trend.py
python gas_consumption.py
python revert_statistics.py
python top_facilitators.py
python ATA_rent_events.py
python ATA_owner_distribution.py
```

Main generated CSVs:

| Script | Outputs |
|---|---|
| `transaction_activity.py` | `trend_daily.csv`, `contributors.csv` |
| `daily_gas_fee_trend.py` | `daily_gas_fee_trend.csv` |
| `gas_consumption.py` | `gas_total.csv` |
| `revert_statistics.py` | `failrate_summary.csv`, `base_revert_breakdown.csv`, `solana_fail_breakdown.csv` |
| `top_facilitators.py` | `facilitator_summary.csv`, `top10_facilitators_by_tx.csv`, `top10_facilitators_by_volume.csv`, `server_multi_facilitator.csv` |
| `ATA_rent_events.py` | `ata_rentpayer_summary.csv`, `ata_rentpayer_by_facilitator.csv`, `ata_rentpayer_top_payers.csv` |
| `ATA_owner_distribution.py` | `ata_owner_counts.csv`, `ata_owner_counts_top20.csv` |

Some scripts query large tables and may take a few minutes depending on database load.

## 3. Reproduce figures 3-7

After generating the measurement CSVs, run:

```bash
python plot/plot_fig3.py
python plot/plot_fig4.py
python plot/plot_fig5.py
python plot/plot_fig6.py
python plot/plot_fig7.py
```

Outputs:

| Figure | Command | Output |
|---|---|---|
| Figure 3 | `python plot/plot_fig3.py` | `plot/fig3.pdf` |
| Figure 4 | `python plot/plot_fig4.py` | `plot/fig4.pdf` |
| Figure 5 | `python plot/plot_fig5.py` | `plot/fig5.pdf` |
| Figure 6 | `python plot/plot_fig6.py` | `plot/fig6.pdf` |
| Figure 7 | `python plot/plot_fig7.py` | `plot/fig7.pdf` |


## 4. Reproduce tables 4-6

Run:

```bash
python table/table4.py
python table/table5.py
python table/table6.py
```

Outputs:

| Table | Command | Output | Required input |
|---|---|---|---|
| Table 4 | `python table/table4.py` | `table/table4.csv` | `failrate_summary.csv` |
| Table 5 | `python table/table5.py` | `table/table5.csv` | `ata_rentpayer_by_facilitator.csv` |
| Table 6 | `python table/table6.py` | `table/table6.csv` | `ata_owner_counts.csv` |

## 6. One-shot reproduction

```bash
source .venv/bin/activate

python transaction_activity.py
python daily_gas_fee_trend.py
python gas_consumption.py
python revert_statistics.py
python top_facilitators.py
python ATA_rent_events.py
python ATA_owner_distribution.py

python plot/plot_fig3.py
python plot/plot_fig4.py
python plot/plot_fig5.py
python plot/plot_fig6.py
python plot/plot_fig7.py

python table/table4.py
python table/table5.py
python table/table6.py
```

