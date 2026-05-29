from x402fetchtxs import *

BLOCKPAGE = 40#int(sys.argv[1])
LIMITSIZE = 10000
RPCSIZE = 500
#for BLOCKPAGE in range(30,40):
TABLENAME = f"x402txs_{BLOCKPAGESIZE}_{BLOCKPAGE}"
    #runsql(f"ALTER TABLE `x402db`.`{TABLENAME}` ADD COLUMN `gasfee` decimal(20, 18) NULL AFTER `revertreason`;")
USETMP = True
if USETMP:
    myprint("create tmp table...", flush=True, end="")
    runsql(f"drop table if exists `tmp_{TABLENAME}`;")
    runsql(f"create TABLE `tmp_{TABLENAME}` (txhash binary(32) not null, blocknumber bigint not null, primary key(txhash), index bn(blocknumber)) select txhash,blocknumber from {TABLENAME} where status is null")
    myprint("ok")
runsql("select 1")
conn = thread_data.__dict__.get("conn")
with BulkInserter(conn, TABLENAME, ["txhash","status","gasused","gasfee"], onduplicate="status=values(status),gasused=values(gasused),gasfee=values(gasfee)") as inserter:
    try:
        lastbn = int(sys.argv[2])
    except:
        lastbn = 0
    while True:
        print("r", flush=True, end="")
        if USETMP:
            data = runsql(f"select txhash,blocknumber from tmp_{TABLENAME} order by blocknumber asc limit {LIMITSIZE}")
        else:
            data = runsql(f"select txhash,blocknumber from {TABLENAME} where blocknumber>={lastbn} and status is null order by blocknumber asc limit {LIMITSIZE}")
        print("o", flush=True, end="")
        if not data:
            break
        bns = sorted(set(i[1] for i in data))
        lastbn = bns[-1]
        myprint("bns:", len(bns), "lastbn:", lastbn)
        blockreceipts = []
        for j in range(0, len(bns), RPCSIZE):
            blockreceipts.extend(p.batch_eth_getBlockReceipts(bns[j:j+RPCSIZE]))
            print(".", end="", flush=True)
        receipts_cache = dict(zip(bns, blockreceipts))

        for txhash,blocknumber in data:
            txhash_hex = b16e(txhash)
            receipt = [i for i in receipts_cache[blocknumber] if i["transactionHash"]==txhash_hex][0]
            status, gasprice, gasused, l1fee, contractAddress = toi(receipt["status"]), toi(receipt["effectiveGasPrice"]), toi(receipt["gasUsed"]), toi(receipt["l1Fee"]), receipt["contractAddress"]
            gasfee = Decimal(gasprice*gasused + l1fee)/10**18
            if contractAddress:
                runsql(f"update {TABLENAME} set `to`=%s where `txhash`=%s", bd(contractAddress), txhash)
            inserter.write([txhash,status,gasused,gasfee])
        inserter._flush()
        if USETMP:
            print("d",flush=True,end="")
            runsql(f"delete from tmp_{TABLENAME} where txhash in ("+ ",".join(["%s"]*len(data)) +")", *[i[0] for i in data])