# Local configuration template for x402scope checks.
#
# Fill these values in your private/local copy before running experiments.
# Do not publish live private keys, paid RPC endpoints, or API credentials.

# EVM test accounts
pk1 = ""       # client private key; balance >= 1 USDC
pk2 = ""       # merchant/server private key
poor_pk = ""   # client private key; balance = 0

# Solana test accounts
solpk = ""        # client private key; balance >= 1 USDC
solpk_server = "" # merchant/server private key
poor_pk_sol = ""  # client private key; balance = 0

# Coinbase facilitator credentials
CDP_API_KEY_ID = ""
CDP_API_KEY_SECRET = ""

# Thirdweb facilitator credential; only needed for thirdweb targets.
ThirdWeb_Secret_key = ""

# Database used by measurement scripts
MYSQL_USER = "root"
MYSQL_PASSWORD = "x402dbpassword"
MYSQL_HOST = "x402db"
MYSQL_PORT = 3306
MYSQL_DB = "x402db"

# RPC endpoints. Replace with archival/high-throughput endpoints for full reproduction.
RPC_BASE = "https://mainnet.base.org"
RPC = RPC_BASE
SOLRPC = "https://api.mainnet.solana.com"
