from solfetchtxs import *
runsql("select 1")
conn = thread_data.__dict__.get("conn")
LIMITSIZE=1000

with BulkInserter(conn, "solanatxs_failed", ["txhash","revertreason"], onduplicate="revertreason=values(revertreason)") as inserter:
    while True:
        print("r", flush=True, end="")
        txhashes = [b58encode(i[0]).decode() for i in runsql(f"select txhash from solanatxs_failed where revertreason is null and tx_category in ('x402_token','x402_token_ata','x402_token2022','x402_token2022_ata') limit {LIMITSIZE}")]
        if not txhashes:
            break
        txs = p.batch_sol_getTransaction(txhashes)
        print("o", flush=True, end="")
        for idx, txhash in enumerate(txhashes):
            tx = txs[idx]
            txbin = b58decode(txhash)
            if "Error: owner does not match" in str(tx):
                inserter.write([txbin, "owner not match"])
            elif "Program ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL failed: Provided owner is not allowed" in str(tx):
                inserter.write([txbin, "ata owner not allowed"])
            elif "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA failed: invalid account data for instruction" in str(tx):
                inserter.write([txbin, "token invalid account data"])
            elif "Error: insufficient funds" in str(tx):
                inserter.write([txbin, "insufficient funds"])
            elif "'InsufficientFundsForRent':" in str(tx):
                inserter.write([txbin, "InsufficientFundsForRent"])
            elif "Error Code: AccountOwnedByWrongProgram" in str(tx):
                inserter.write([txbin, "AccountOwnedByWrongProgram"])
            elif "Transfer: insufficient lamports" in str(tx) and "Program ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL failed: custom program error: 0x1" in str(tx):
                inserter.write([txbin, "rent insufficient"])
            else:
                print(tx)
                raise NotImplementedError