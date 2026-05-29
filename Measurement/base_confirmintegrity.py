from x402fetchtxs import *
import concurrent

def worker(n):
    starttime = time.time()
    myprint(f"n={n} start")
    data = runsql(f"select `from`,count(*),min(nonce),max(nonce) from x402txs_1000000_{n} group by `from`")
    myprint(f"n={n} ok, used {time.time()-starttime:.2f}s")
    return data

if __name__ == '__main__':
    numbers = list(range(30,41))
    res = {} #addr:[lastpage,lastmaxnonce]
    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = executor.map(worker, numbers)
        
        for idx,result in enumerate(results):
            page = numbers[idx]
            for addr_bin, cnt, minnonce, maxnonce in result:
                addr=b16e(addr_bin)
                if addr not in EOAADDRS_set:
                    continue
                lastpage,lastnonce = res.get(addr,[0,-1])
                assert maxnonce-minnonce+1==cnt
                assert minnonce==lastnonce+1
                res[addr] = [page, maxnonce]
            print(f"verified {page}")