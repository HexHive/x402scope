from x402fetchtxs import *
import common, concurrent
from base58 import b58decode,b58encode
RPC = "https://explorer-api.mainnet-beta.solana.com/"
common.RPC2Referer[RPC]="https://explorer.solana.com"

p = Endpoint_Provider([RPC, config.SOLRPC])

def parsetx(addr, txhash, tx):
    txbin = b58decode(txhash)
    blocktime = tx["blockTime"]
    slot = tx["slot"]
    meta = tx["meta"]
    postTokenBalances = meta["postTokenBalances"]
    fee = Decimal(meta["fee"])/10**9
    transaction = tx["transaction"]
    msg = transaction["message"]
    assert transaction["signatures"][0] == txhash
    is_x402 = False
    usealt = True
    accs = [i["pubkey"] for i in msg["accountKeys"]]
    acc2postbalance = dict(zip(accs, meta["postBalances"]))
    signers = [i["pubkey"] for i in msg["accountKeys"] if i["signer"]]
    if addr not in signers:
        return False, None #ignore non facilitator signed txs
    payer = signers[0]
    payer_aftersolbalance = Decimal(acc2postbalance[payer])/10**9
    save = False # should we save this tx to disk for further analysis
    if tx["version"]==0 and msg["addressTableLookups"]:
        save = "alt used"
    ok = "Ok" in meta["status"]
    gaslimit = 0
    gasprice = 0
    tx_category = None
    withata = False
    x402_from, x402_to, x402_token, x402_amount, x402_from_afterbalance, x402_to_afterbalance = None, None, None, None, None, None
    for ins in msg["instructions"]:
        if ins["programId"] == "ComputeBudget111111111111111111111111111111":
            d = b58decode(ins["data"])
            if d[0]==2: #set compute unit limit
                gaslimit = int.from_bytes(d[1:], "little")
            elif d[0]==3:
                gasprice = int.from_bytes(d[1:], "little")
        elif ins["programId"] in ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA","TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"]:
            info = ins["parsed"]["info"]
            if ins["parsed"]["type"] in ["transferChecked","transfer"] and "authority" in info: #exclude multisig
                is_x402 = True
                tx_category = "x402_token"
                if ins["programId"]=="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb":
                    tx_category = "x402_token2022"
                x402_from = info["authority"]
                fromata = info["source"]
                toata = info["destination"]
                if "mint" in info:
                    x402_token = info["mint"]
                try:
                    toata_detail = [i for i in postTokenBalances if i["accountIndex"]==accs.index(toata)][0]
                    x402_to = toata_detail['owner']
                    x402_to_afterbalance = Decimal(toata_detail['uiTokenAmount']['uiAmountString'])
                    if x402_token is None and "mint" in toata_detail:
                        x402_token = toata_detail["mint"]
                except:
                    pass
                fromata_detail = None
                try:
                    fromata_detail = [i for i in postTokenBalances if i["accountIndex"]==accs.index(fromata)][0]
                    x402_from_afterbalance = Decimal(fromata_detail['uiTokenAmount']["uiAmountString"])
                except:
                    pass
                if "tokenAmount" in info:
                    x402_amount = Decimal(info["tokenAmount"]["uiAmountString"])
                else:
                    if fromata_detail:
                        decimals = fromata_detail['uiTokenAmount']["decimals"]
                    else:
                        decimals = 0
                    x402_amount = Decimal(info["amount"])/10**decimals
            else:
                save="unknown token instruction"
        elif ins["programId"]=="ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL" and ins["parsed"]["type"]=="create":
            #print("ata included:", txhash, ins)
            #save="ata included"
            withata = True
        else:
            save="unknown program"
    if tx_category and withata:
        tx_category+="_ata"
    return save, [
            txbin, blocktime, slot, fee, payer, gaslimit, gasprice, ok, payer_aftersolbalance, tx_category, 
            x402_from, x402_to, x402_token, x402_amount, x402_from_afterbalance, x402_to_afterbalance
        ]

def worker_addr(addr):
    mints, maxts = runsql("select min(blocktime),max(blocktime) from solanatxs where payer=%s", addr)[0]
    maxts = maxts or 0
    mints = mints or int(time.time())+100
    print("maxts:", time2human(maxts), "mints:", time2human(mints))
    conn = thread_data.__dict__.get("conn")
    fields = "txhash, blocktime, slot, fee, payer, gaslimit, gasprice, ok, payer_aftersolbalance, tx_category, x402_from, x402_to, x402_token, x402_amount, x402_from_afterbalance, x402_to_afterbalance".replace(" ","").split(",")
    with BulkInserter(conn, "solanatxs", fields) as inserter:
        before = None
        round1 = True
        while True:
            txhashes = sol_getSignaturesForAddress(RPC, addr, before=before)
            if not txhashes:
                myprint(f"[return] no data {addr}")
                return
            txs = p.batch_sol_getTransaction(txhashes)
            before = txhashes[-1]
            for idx, (txhash, tx) in enumerate(zip(txhashes, txs)):
                sys.tx = tx
                save, item = parsetx(addr, txhash, tx)
                if save:
                    #print("save:", save, txhash)
                    open(f"/tank/x402db/solanatxs/{txhash}", "w").write(json.dumps(tx))
                if item:
                    if idx==0:
                        myprint(time2human(item[1]), txhash, item[2:])
                    inserter.write(item)
                    if item[1]<maxts and round1:
                        myprint(f"[finish maxts] {addr}")
                        before = b58encode(runsql("select txhash from solanatxs where blocktime>%s limit 1", mints)[0][0]).decode()
                        round1 = False
                        break
        
        

if __name__ == "__main__":
    if sys.argv[1].isdigit():
        addrs = [solADDRS[int(i)] for i in sys.argv[1:]]
    elif sys.argv[1] in solADDRS:
        addrs = sys.argv[1:]
    else:
        addrs = solEOAs[sys.argv[1]]
    for addr in addrs:
        worker_addr(addr)
