from x402fetchtxs import *

BLOCKPAGE = 40#int(sys.argv[1])
LIMITSIZE = 10000
RPCSIZE = 100
TABLENAME = f"x402txs_{BLOCKPAGESIZE}_{BLOCKPAGE}"

runsql("select 1")
conn = thread_data.__dict__.get("conn")
with BulkInserter(conn, TABLENAME, ["txhash","revertreason"], onduplicate="revertreason=values(revertreason)") as inserter:
    try:
        lastbn = int(sys.argv[2])
    except:
        lastbn = 0
    while True:
        print("r", flush=True, end="")
        data = runsql(f"select txhash,blocknumber from {TABLENAME} where blocknumber>={lastbn} and status=0 and revertreason is null order by blocknumber asc limit {LIMITSIZE}")
        print("o", flush=True, end="")
        if not data:
            break
        txhashes = [b16e(i[0]) for i in data]
        traces = []
        for j in range(0, len(data), RPCSIZE):
            traces.extend(p.batch_debugtrace_calltracer(txhashes[j:j+RPCSIZE]))
            print(".", flush=True, end="")
        for idx, (txhash,blocknumber) in enumerate(data):
            x = traces[idx]
            reason = x["error"] +"/" + x.get("revertReason", x.get("output",""))
            inserter.write([txhash, reason])
            lastbn = blocknumber
        myprint(blocknumber,reason)
        inserter._flush()