from sol_fetchtxs import *
TABLENAME = "solanatxs_ata"
runsql("select 1")
conn = thread_data.__dict__.get("conn")
LIMITSIZE=1000
with BulkInserter(conn, TABLENAME, ["txhash","blocktime","ata_payer","ata_account","ata_owner","signer_length"], onduplicate="ata_payer=values(ata_payer),ata_account=values(ata_account),ata_owner=values(ata_owner),signer_length=values(signer_length)") as inserter:
    while True:
        print("r", flush=True, end="")
        data = runsql(f"select txhash,blocktime from {TABLENAME} where signer_length is null order by blocktime asc limit {LIMITSIZE}")
        print("o", flush=True, end="")
        if not data:
            break
        txhashes = [b58encode(i[0]).decode() for i in data]
        txs = p.batch_sol_getTransaction(txhashes)
        for idx,tx in enumerate(txs):
            txhash_bin, blocktime = data[idx]
            atains = [i for i in tx["transaction"]["message"]["instructions"] if i["programId"]=="ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"][0]
            assert atains["parsed"]["type"]=="create"
            atainfo = atains["parsed"]["info"]
            ata_payer,ata_account,ata_owner = atainfo["source"],atainfo["account"],atainfo["wallet"]
            signer_length = len(tx["transaction"]["signatures"])
            row = [txhash_bin, blocktime, ata_payer,ata_account,ata_owner,signer_length]
            if idx==0:
                print(row)
            inserter.write(row)
        inserter._flush()