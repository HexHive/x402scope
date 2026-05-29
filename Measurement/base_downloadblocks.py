from common import *
from mpms import MPMS
from tqdm import tqdm
import zstandard as zstd

DIR = "/tank/x402db/blocks_base"
SIZE = 100
SIZE2 = 50

def worker(i):
    for _ in range(3):
        try:
            if not os.path.isfile(f"{DIR}/{i}.zst"):
                x = p.batch_eth_getBlockByNumber(range(i*SIZE, i*SIZE+SIZE), verify=False)
                zstd.open(f"{DIR}/{i}.zst", "wt", cctx=zstd.ZstdCompressor(level=3)).write(json.dumps(x))
            return
        except:
            traceback.print_exc()
            print("error:", i, sys.x.text[:1000])
            sleep(1)

def handler(meta, res):
    meta["done"][0] += 1

if __name__ == "__main__":
    known = set(os.listdir(DIR))
    print("known:", len(known))
    latest_height = p.eth_blockNumber()
    print("latest_height:", latest_height)
    meta = {"done":[0]}
    m = MPMS(worker, handler, processes=2, threads=2, meta=meta)
    m.start()
    total = 0
    for i in range(30000000//SIZE, int(latest_height/SIZE)-1):
        if str(i)+".zst" in known:
            continue
        m.put(i)
        total += 1

    oldlen = 0
    with tqdm(total = total) as pbar:
        while len(m)>10:
            #print("len(m)", len(m))
            pbar.set_description("len(m)="+str(len(m)))
            size = meta["done"][0]
            pbar.update(size - oldlen)
            oldlen = size
            sleep(1)
    m.join()