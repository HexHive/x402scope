import os
# EOA list is generated from x402scan codebase:
#   git clone https://github.com/Merit-Systems/x402scan
#   THISFOLDER=`pwd`
#   cd x402scan/packages/external/facilitators/src/facilitators 
#   python3 ${THISFOLDER}/x402scan_exportevmaddr.py 

EOAs = {'questflow': ['0x724efafb051f17ae824afcdf3c0368ae312da264', '0xa9a54ef09fc8b86bc747cec6ef8d6e81c38c6180', '0x4638bc811c93bf5e60deed32325e93505f681576', '0xd7d91a42dfadd906c5b9ccde7226d28251e4cd0f', '0x4544b535938b67d2a410a98a7e3b0f8f68921ca7', '0x59e8014a3b884392fbb679fe461da07b18c1ff81', '0xe6123e6b389751c5f7e9349f3d626b105c1fe618', '0xf70e7cb30b132fab2a0a5e80d41861aa133ea21b', '0x90da501fdbec74bb0549100967eb221fed79c99b', '0xce7819f0b0b871733c933d1f486533bab95ec47b'], '402104': ['0x73b2b8df52fbe7c40fe78db52e3dffdd5db5ad07'], 'codenut': ['0x8d8Fa42584a727488eeb0E29405AD794a105bb9b', '0x87aF99356d774312B73018b3B6562e1aE0e018C9', '0x65058CF664D0D07f68B663B0D4b4f12A5E331a38', '0x88E13D4c764a6c840Ce722A0a3765f55A85b327E'], 'treasure': ['0xe07e9cbf9a55d02e3ac356ed4706353d98c5a618'], 'meridian': ['0x8e7769d440b3460b92159dd9c6d17302b036e2d6', '0x3210d7b21bfe1083c9dddbe17e8f947c9029a584'], 'openx402': ['0x97316fa4730bc7d3b295234f8e4d04a0a4c093e8', '0x97db9b5291a218fc77198c285cefdc943ef74917'], 'payai': ['0xc6699d2aada6c36dfea5c248dd70f9cb0235cb63', '0xb2bd29925cbbcea7628279c91945ca5b98bf371b', '0x25659315106580ce2a787ceec5efb2d347b539c9', '0xb8f41cb13b1f213da1e94e1b742ec1323235c48f', '0xe575fa51af90957d66fab6d63355f1ed021b887b', '0x03a3f7ce8e21e6f8d9fa14c67d8876b2470dc2f1', '0x675707bc7d03089f820c1b7d49f7480083e8f4df', '0xf46833d4ac4f0f1405cc05c30edfd86770f721c9', '0x2daaef6f941de214bf7d6daf322bc6bc7406accb', '0x2fae4026a31f19183947f0a6045ef975ebfa9ca8', '0xe299c486066739c4a31609e1268d93229632dd47', '0x6ccf245c883f9f3c6caee0687aa61daf7bc96e32', '0xaf990eef9846b63d896056050fdc0b28bca9c24b', '0x489c40fc3c2a19ad8cb275b7dd6aa194e9219c4f', '0x9df61a719ddae27c20a63a417271cc2c704654bd'], 'ultravioletadao': ['0x103040545ac5031a11e8c03dd11324c7333a13c7'], 'virtuals': ['0x80735b3f7808e2e229ace880dbe85e80115631ca'], 'mogami': ['0xfe0920a0a7f0f8a1ec689146c30c3bbef439bf8a'], 'thirdweb': ['0x80c08de1a05df2bd633cf520754e40fde3c794d3', '0xaaca1ba9d2627cbc0739ba69890c30f95de046e4', '0xa1822b21202a24669eaf9277723d180cd6dae874', '0xec10243b54df1a71254f58873b389b7ecece89c2', '0x052aaae3cad5c095850246f8ffb228354c56752a', '0x91ddea05f741b34b63a7548338c90fc152c8631f', '0xea52f2c6f6287f554f9b54c5417e1e431fe5710e', '0x3a5ca1c6aa6576ae9c1c0e7fa2b4883346bc5aa0', '0x7e20b62bf36554b704774afb0fcc0ae8f899213b', '0xd88a9a58806b895ff06744082c6a20b9d7184b0f'], 'coinbase': ['0xdbdf3d8ed80f84c35d01c6c9f9271761bad90ba6', '0x9aae2b0d1b9dc55ac9bab9556f9a26cb64995fb9', '0x3a70788150c7645a21b95b7062ab1784d3cc2104', '0x708e57b6650a9a741ab39cae1969ea1d2d10eca1', '0xce82eeec8e98e443ec34fda3c3e999cbe4cb6ac2', '0x7f6d822467df2a85f792d4508c5722ade96be056', '0x001ddabba5782ee48842318bd9ff4008647c8d9c', '0x9c09faa49c4235a09677159ff14f17498ac48738', '0xcbb10c30a9a72fae9232f41cbbd566a097b4e03a', '0x9fb2714af0a84816f5c6322884f2907e33946b88', '0x47d8b3c9717e976f31025089384f23900750a5f4', '0x94701e1df9ae06642bf6027589b8e05dc7004813', '0x552300992857834c0ad41c8e1a6934a5e4a2e4ca', '0xd7469bf02d221968ab9f0c8b9351f55f8668ac4f', '0x88800e08e20b45c9b1f0480cf759b5bf2f05180c', '0x6831508455a716f987782a1ab41e204856055cc2', '0xdc8fbad54bf5151405de488f45acd555517e0958', '0x91d313853ad458addda56b35a7686e2f38ff3952', '0xadd5585c776b9b0ea77e9309c1299a40442d820f', '0x4ffeffa616a1460570d1eb0390e264d45a199e91'], 'corbits': ['0x06F0BfD2C8f36674DF5cdE852c1eeD8025C268C9'], 'daydreams': ['0x279e08f711182c79Ba6d09669127a426228a4653'], 'xecho': ['0x3be45f576696a2fd5a93c1330cd19f1607ab311d'], 'openmid': ['0x16e47d275198ed65916a560bab4af6330c36ae09'], 'aurracloud': ['0x222c4367a2950f3b53af260e111fc3060b0983ff', '0xb70c4fe126de09bd292fe3d1e40c6d264ca6a52a', '0xd348e724e0ef36291a28dfeccf692399b0e179f8'], 'x402rs': ['0xd8dfc729cbd05381647eb5540d756f4f8ad63eec', '0x76eee8f0acabd6b49f1cc4e9656a0c8892f3332e', '0x97d38aa5de015245dcca76305b53abe6da25f6a5', '0x0168f80e035ea68b191faf9bfc12778c87d92008', '0x5e437bee4321db862ac57085ea5eb97199c0ccc5', '0xc19829b32324f116ee7f80d193f99e445968499a'], 'polymer': ['0x66c40946b0dffd04be467e18309857307ecd37cb'], 'heurist': ['0xb578b7db22581507d62bdbeb85e06acd1be09e11', '0x021cc47adeca6673def958e324ca38023b80a5be', '0x3f61093f61817b29d9556d3b092e67746af8cdfd', '0x290d8b8edcafb25042725cb9e78bcac36b8865f8', '0x612d72dc8402bba997c61aa82ce718ea23b2df5d', '0x1fc230ee3c13d0d520d49360a967dbd1555c8326', '0x48ab4b0af4ddc2f666a3fcc43666c793889787a3', '0xd97c12726dcf994797c981d31cfb243d231189fb', '0x90d5e567017f6c696f1916f4365dd79985fce50f'], 'anyspend': ['0x179761d9eed0f0d1599330cc94b0926e68ae87f1']}
EOAADDRS_set = set()
for name, addrs in EOAs.items():
    EOAADDRS_set.update(addrs)
EOAADDRS = sorted(EOAADDRS_set)
solEOAs = {
    'codenut': ['HsozMJWWHNADoZRmhDGKzua6XW6NNfNDdQ4CkE9i5wHt'], 
    'openx402': ['5xvht4fYDs99yprfm4UeuHSLxMBRpotfBtUCQqM3oDNG'], 
    'payai': ['2wKupLR9q6wXYppw8Gr2NvWxKBUqm4PPJKkQfoxHDBg4', 'CjNFTjvBhbJJd2B5ePPMHRLx1ELZpa8dwQgGL727eKww', '8B5UKhwfAyFW67h58cBkQj1Ur6QXRgwWJJcQp8ZBsDPa'], 
    'ultravioletadao': ['F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq'], 
    'dexter': ['DEXVS3su4dZQWTvvPnLDJLRK1CeeKG6K3QqdzthgAkNV'], 
    'coinbase': ['L54zkaPQFeTn1UsEqieEXBqWrPShiaZEPD7mS5WXfQg'], 
    'corbits': ['AepWpq3GQwL8CeKMtZyKtKPa7W91Coygh3ropAJapVdU'], 
    'daydreams': ['DuQ4jFMmVABWGxabYHFkGzdyeJgS1hp4wrRuCtsJgT9a'], 
    'aurracloud': ['8x8CzkTHTYkW18frrTR7HdCV6fsjenvcykJAXWvoPQW'], 
    'anyspend': ['34DmdeSbEnng2bmbSj9ActckY49km2HdhiyAwyXZucqP']
}
solADDRS_set = set()
for name, addrs in solEOAs.items():
    solADDRS_set.update(addrs)
solADDRS = sorted(solADDRS_set)

import pymysql
from typing import Iterable, Sequence, Any, List, Tuple, Optional
import zstandard as zstd
from common import *
from runsql import runsql,thread_data

class BulkInserter:
    def __init__(
        self,
        connection: pymysql.connections.Connection,
        table: str,
        columns: Sequence[str],
        batch_size: int = 1000,
        autocommit: bool = True,
        onduplicate: str = "ignore",
    ):
        self.conn = connection
        self.table = table
        self.columns = columns
        self.batch_size = batch_size
        self.autocommit = autocommit

        placeholders = ", ".join(["%s"] * len(columns))
        if onduplicate=="ignore":
            self.sql = f"INSERT ignore INTO {table} (`{'`, `'.join(columns)}`) VALUES ({placeholders})"
        else:
            self.sql = f"INSERT INTO {table} (`{'`, `'.join(columns)}`) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {onduplicate}"

        self.buffer: List[Tuple[Any, ...]] = []
        self.cursor: Optional[pymysql.cursors.Cursor] = None

    def __enter__(self):
        self.cursor = self.conn.cursor()
        return self

    def write(self, row: Iterable[Any]):
        if self.cursor is None:
            raise RuntimeError("BulkInserter must be used within a 'with' block.")
        self.buffer.append(tuple(row))
        if len(self.buffer) >= self.batch_size:
            self._flush()

    def _flush(self):
        if not self.buffer:
            return
        self.cursor.executemany(self.sql, self.buffer)
        if self.autocommit:
            self.conn.commit()
        self.buffer.clear()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._flush()
            if not self.autocommit:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
        finally:
            if self.cursor is not None:
                self.cursor.close()
            self.cursor = None

currentfile, currentcache = None, None
def readblock(i):
    global currentfile, currentcache
    fileid, fileoffset = i//BLOCKFILESIZE, i%BLOCKFILESIZE
    if currentfile==fileid:
        return currentcache[fileoffset]
    currentfile = fileid
    #print("read file", fileid)
    currentcache = json.load(zstd.open(f"{BLOCKFILEFOLDER}/{fileid}.zst"))
    return currentcache[fileoffset]

p = getp(8453)
BLOCKPAGESIZE = 1000000
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
if __name__ == "__main__":
    from tqdm import tqdm
    try:
        BLOCKSTART = int(sys.argv[1])
    except:
        BLOCKSTART = runsql(f"select max(blocknumber) from x402txs_{BLOCKPAGESIZE}_40")[0][0]
    BLOCKPAGE = BLOCKSTART//BLOCKPAGESIZE
    BLOCKEND = (BLOCKPAGE+1)*BLOCKPAGESIZE
    TABLENAME = f"x402txs_{BLOCKPAGESIZE}_{BLOCKPAGE}"
    BLOCKFILESIZE = 100
    BLOCKFILEFOLDER = "/tank/x402db/blocks_base"
    runsql(f"""CREATE TABLE if not exists `{TABLENAME}`  (
    `txhash` binary(32) NOT NULL,
    `blocknumber` bigint NULL,
    `timestamp` bigint NULL,
    `from` binary(20) NULL,
    `to` binary(20) NULL,
    `value` decimal(30, 18) NULL,
    `input` varbinary(25000) NULL,
    `bytes4` binary(4) NULL,
    `gasprice` bigint NULL,
    `nonce` bigint NULL,
    `gaslimit` bigint NULL,
    `gasused` bigint NULL,
    `status` int NULL,
    `revertreason` varchar(255) NULL,
    `gasfee` decimal(20, 18) NULL,
    `tx_category` varchar(255) NULL,
    `x402_from` binary(20) NULL,
    `x402_to` binary(20) NULL,
    `x402_value` decimal(20, 6) NULL,
    `x402_validafter` bigint NULL,
    `x402_validbefore` bigint NULL,
    `x402_nonce` binary(32) NULL,
    `x402_signaturelength` int NULL,
    PRIMARY KEY (`txhash`),
    INDEX(`blocknumber`),
    INDEX(`timestamp`),
    INDEX(`from`),
    INDEX(`to`),
    INDEX(`bytes4`),
    INDEX(`nonce`),
    INDEX(`status`),
    INDEX(`revertreason`),
    INDEX(`tx_category`),
    INDEX(`x402_from`),
    INDEX(`x402_to`),
    INDEX(`x402_signaturelength`)
    );""")
    conn = thread_data.__dict__.get("conn")

    columns = "txhash,blocknumber,timestamp,from,to,value,input,bytes4,gasprice,nonce,gaslimit,tx_category,x402_from,x402_to,x402_value,x402_validafter,x402_validbefore,x402_nonce,x402_signaturelength".split(",")
    with BulkInserter(conn, TABLENAME, columns) as inserter:
        oldhash = None
        for blocknumber in tqdm(range(BLOCKSTART, BLOCKEND)):
            b = readblock(blocknumber)
            if oldhash:
                assert b["parentHash"] == oldhash
            oldhash = b["hash"]
            timestamp = toi(b["timestamp"])
            for tx in b["transactions"]:
                if "to" not in tx:
                    tx["to"] = None
                if tx["from"] in EOAADDRS_set or tx["to"] in EOAADDRS_set:
                    #print(tx["hash"])
                    sys.tx = tx
                    txhash, _from, to, value, _input, gasprice, nonce, gaslimit = bd(tx["hash"]), bd(tx["from"]), bd(tx["to"]), Decimal(toi(tx["value"]))/10**18, bd(tx["input"]), toi(tx["gasPrice"]), toi(tx["nonce"]), toi(tx["gas"])
                    tx_category = None
                    bytes4 = _input[:4]
                    x402_from, x402_to, x402_value, x402_validafter, x402_validbefore, x402_nonce, x402_signaturelength = None, None, None, None, None, None, None
                    if tx["to"]==USDC and bytes4==b'\xcf\t)\x95':
                        tx_category = "x"
                        x402_from, x402_to, x402_value, x402_validafter, x402_validbefore, x402_nonce, x402_sig = eth_abi.decode_abi(["address","address","uint","uint","uint","bytes32","bytes"], _input[4:])
                        x402_from, x402_to, x402_value = bd(x402_from), bd(x402_to), Decimal(x402_value)/10**6
                        x402_signaturelength = len(x402_sig)
                    elif not tx["to"]:
                        tx_category = "create_contract"
                    inserter.write([txhash,blocknumber,timestamp,_from,to,value,_input,bytes4,gasprice,nonce,gaslimit,tx_category,x402_from,x402_to,x402_value,x402_validafter,x402_validbefore,x402_nonce,x402_signaturelength])
