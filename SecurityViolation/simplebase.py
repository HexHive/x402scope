#pip install web3==7.14.0 eth-account==0.13.7 coincurve solana==0.34.0 httpx==0.27.0
__version__="20251206"
import inspect
try:
    inspect.getargspec = inspect.getfullargspec
except:
    pass
import time, requests, hashlib, random, json, os, subprocess, sys, threading, traceback, pickle, math, binascii
from datetime import datetime
import eth_abi
try:
    eth_abi.decode_abi = eth_abi.decode
    eth_abi.encode_abi = eth_abi.encode
    eth_abi.decode_single = lambda a,b:eth_abi.decode([a],b)[0]
except:
    pass
from decimal import Decimal
from time import sleep
from base64 import *
import eth_utils
toChecksumAddress = eth_utils.address.to_checksum_address
from pprint import pprint
from functools import lru_cache, partial, wraps
import requests
import eth_account
FOLDER = os.path.dirname(os.path.abspath(__file__))

def D(i, j=None):
    if not i:
        return 0
    if j is not None:
        i = int(i,j)
    return Decimal(i)

@lru_cache()
def eth_chainId(endpoint):
    return simple_rpccall(endpoint, "eth_chainId", [], returnint=True)

def getsess():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'}
    try:
        from config import EXTRA_HEADERS
        print("extra headers:", EXTRA_HEADERS)
        headers.update(EXTRA_HEADERS)
    except:
        pass
    sess=requests.session()
    sess.headers.update(headers)
    return sess

sess=getsess()

def reset_sess():
    global sess
    sess=getsess()
    thread_data.__dict__["sess"] = sess

RPC= "http://127.0.0.1:8545"
try:
    _chainidcache = json.load(open("/tmp/chainid.json"))
except:
    _chainidcache = {}

def get_chainid(endpoint, method="eth_chainId"):
    global _chainidcache
    if not isinstance(endpoint, str):
        return endpoint.eth_chainId()
    if endpoint in _chainidcache:
        return _chainidcache[endpoint]
    headers = {}
    try:
        from config import GET_EXTRA_HEADERS
        headers.update(GET_EXTRA_HEADERS(endpoint))
    except:
        pass
    print("get chain id...", endpoint, flush=True, end="")
    starttime = time.time()
    x = sess.post(endpoint, json={"jsonrpc":"2.0","id":1,"method":method,"params":[]}, headers=headers)
    sys.x = x
    chainid = int(x.json()["result"], 16)
    print(" ok,", chainid, "latency: %.2f"%(1000*(time.time()-starttime)))
    _chainidcache[endpoint] = chainid
    json.dump(_chainidcache, open("/tmp/chainid.json", "w"))
    return chainid

if os.getenv("RPC"):
    RPC = os.getenv("RPC")
    CHAINID = get_chainid(RPC)
else:
    CHAINID = -1

L="http://127.0.0.1:8545"

def topub(privatekey):
    try:
        return eth_account.Account.from_key(privatekey).address
    except:
        return eth_account.Account.privateKeyToAccount(privatekey).address

try:
    from config import privatekey
    badaddr=False
except:
    privatekey = "a"*64
    badaddr=True
MYADDR = topub(privatekey)
if not badaddr and not os.getenv("NOADDR"):
    print("MYADDR:", MYADDR)
def myprint(*args, **kwargs):
    args = list(args)
    args[0] = "["+time.strftime("%Y-%m-%d %H:%M:%S")+"] " + str(args[0])
    print(*args, **kwargs)

def tohex(i):
    if isinstance(i, str):
        assert i.startswith("0x"), f"tohex: str {i} no 0x prefix"
        return i
    else:
        assert isinstance(i, int), f"tohex: {i} is not int"
        return hex(i)
def eth_estimateGas(endpoint, to, data, value, from_):
    return simple_rpccall(endpoint, "eth_estimateGas", [{"to":to, "data":data, "value":tohex(value), "from":from_}], returnint=True)

class NonceError(Exception):
    pass

class BaseFeeError(Exception):
    pass

class AlreadyKnownError(Exception):
    pass

class UnderPricedError(Exception):
    pass

def eth_gasPrice1559(RPC, includeBlob=False):
    x = simple_rpccall(RPC, "eth_feeHistory", ["0x1", "latest", [10]])
    bf = x["baseFeePerGas"][-1]
    if bf:
        bf = toi(bf)
    else:
        bf = 0
    res = [bf, toi(x["reward"][0][0])]
    if includeBlob:
        res.append(toi(x["baseFeePerBlobGas"][-1]))
    return res

def eth_blobGasPrice(RPC):
    return eth_gasPrice1559(RPC, includeBlob=True)[-1]

class CallNetworkFailed(Exception): #network issue, should retry to this RPC
    pass

class CallReverted(Exception): # contract revert, no retry to all RPCs
    pass

class CallRPCFailed(Exception): # rpc not supported, no retry to this RPC
    pass

from eth_account.messages import encode_defunct
def sign_text(text=None, hexstr=None, pk=None, returnbytes=True):
    if text:
        if isinstance(text, str):
            msg = encode_defunct(text=text)
        else:
            msg = encode_defunct(text)
    else:
        assert hexstr, "sign_text: text or hexstr must be provided"
        msg = encode_defunct(hexstr=hexstr.replace("0x",""))
    if text and hexstr is not None and pk is None:
        pk = hexstr
    assert pk is not None, "pk must be provided"
    sig = eth_account.Account.sign_message(msg, pk)
    if not returnbytes:
        return sig
    ret = sig.signature.hex()
    if not ret.startswith("0x"):
        ret = "0x"+ret
    return ret

def sign_struct(domain_data=None, message_types=None, message_data=None, pk=None, returnbytes=True):
    full_message = None
    if domain_data and message_types is not None and pk is None:
        full_message = domain_data
        domain_data = None
        pk = message_types
        message_types = None
    assert pk is not None, "pk must be provided"
    sig = eth_account.Account.sign_typed_data(private_key=pk, domain_data=domain_data, message_types=message_types, message_data=message_data, full_message=full_message)
    if not returnbytes:
        return sig
    ret = sig.signature.hex()
    if not ret.startswith("0x"):
        ret = "0x"+ret
    return ret
sign_eip712 = sign_typed_data = sign_struct

TXSENT = False
def maketx(to, data, nonce=None, gasprice=None, needstx=False, gaslimit=2000000, sendamount=None, showgas=False, writetx=False, rpc=None, pk=None, gaslimitratio=1.1, requirecontract=False, chainid=None):
    if rpc is None:
        rpc = RPC
    if chainid is not None:
        CHAINID = chainid
    else:
        CHAINID = get_chainid(rpc)
    if pk is None:
        pk, myaddr = privatekey, MYADDR
    else:
        myaddr = topub(pk)
    if to:
        to = toChecksumAddress(to)
    if nonce is None:
        nonce= eth_getTransactionCount(rpc, myaddr)
    if gasprice is None:
        try:
            suggest = eth_gasPrice1559(rpc)
            gasprice = [suggest[0]+10**9, suggest[1]+10**6]
        except:
            suggest = eth_gasPrice(rpc)
            gasprice = suggest+10**6
    value=sendamount if sendamount else 0
    if requirecontract:
        code = eth_getCode(rpc, to)
        assert len(code)>10, "to is not contract?"
    if showgas:
        gl = eth_estimateGas(rpc, to, data, value, myaddr)
        if gaslimit<gl*gaslimitratio:
            gaslimit = int(gl*gaslimitratio)
        myprint("CHAINID:",CHAINID, "to:",to, "4bytes:",data[:10], "gas:", gl)
    if isinstance(gasprice, int):
        myprint(rpc, "nonce:", nonce, "gasprice:", "%.2f"%(gasprice/10**9))
        tx=dict(nonce=nonce, gasPrice=gasprice, gas=gaslimit, to=to, 
            value=value, data=data, chainId=CHAINID)
    else:
        assert len(gasprice)==2, "gasPrice should be (baseFee, priority)"
        myprint(rpc, "nonce:", nonce, "gasprice:", "%.2f"%(gasprice[0]/10**9), "+", "%.2f"%(gasprice[1]/10**9))
        tx=dict(nonce=nonce, maxFeePerGas=int(gasprice[0]+gasprice[1]), maxPriorityFeePerGas=int(gasprice[1]), gas=gaslimit, to=to, 
            value=value, data=data, chainId=CHAINID)
    stx=eth_account.Account.sign_transaction(tx, pk)
    if getattr(stx, "raw_transaction", None):
        stx.rawTransaction = stx.raw_transaction
    if writetx:
        try:
            os.makedirs(f"__pycache__/sendtx{myaddr}", exist_ok=True)
            open(f"__pycache__/sendtx{myaddr}/evm{CHAINID}_{nonce}","w").write(json.dumps({
                "stx":stx.rawTransaction.hex(),
                "tx": tx
            }))
        except:
            pass
    sys.stx = stx
    if needstx:
        return stx.rawTransaction
    txid = eth_sendRawTransaction(rpc, stx.rawTransaction)
    return txid

def eth_maketx(rpc, *args, **kwargs):
    return maketx(*args, rpc=rpc, **kwargs)

class TxTimeout(Exception):
    pass

def waittx(txhash, _times=50, sleeptime=1, rpc=None):
    if rpc is None:
        rpc = RPC
    times = _times
    myprint("wait for tx", txhash)
    while times>0:
        if times!=_times:
            sleep(sleeptime)
        times -= 1
        try:
            tx = eth_getTransactionReceipt(rpc, txhash)
            if tx and tx['blockNumber']:
                if toi(tx["status"])==1:
                    myprint("success in block", toi(tx["blockNumber"]))
                    #sleep(3)
                else:
                    myprint("failed:", txhash)
                return tx
        except Exception as e:
            print(e)
            continue
    myprint("[timeout]", txhash)
    raise TxTimeout(txhash)

def eth_waittx(rpc, txhash, _times=50, sleeptime=1):
    return waittx(txhash, _times=_times, sleeptime=sleeptime, rpc=rpc)

from Crypto.Hash import keccak

def sha3(s):
    if isinstance(s, str):
        assert all([i.lower() in "0123456789abcdef" for i in s.replace("0x","")])
        s = bd(s)
    return keccak.new(digest_bits=256).update(s).hexdigest()

def event_hash(s):
    return sha3(s.encode("utf-8"))


def function_hash(func_str):
    if not func_str:
        return ""
    if func_str.startswith("0x") and len(func_str)==10:
        return func_str[2:]
    return event_hash(func_str)[:8]

def addrtoarg(addr, *kargs):
    if kargs:
        return addrtoarg([addr]+list(kargs))
    if isinstance(addr, (list,tuple)):
        return "".join([addrtoarg(i) for i in addr])
    if isinstance(addr, int):
        assert addr>=0, f"toarg error: negative int {addr}"
        addr = hex(addr)
    if isinstance(addr, bytes):
        addr = b16e(addr)
    if addr.startswith("0x"):
        addr = addr[2:]
    res = addr.lower().rjust(64, "0")
    assert len(res)==64, f"wrong toarg param: {addr}"
    return res
toarg = addrtoarg


import threading
thread_data = threading.local()

def rpccall(endpoint, data, timeout=None, headers=None, verify=True):
    if isinstance(endpoint, Endpoint_Provider):
        return endpoint.rpccall(data, timeout=timeout, headers=headers, verify=verify)
    if timeout is None:
        timeout = int(os.getenv("TIMEOUT", 10))
    sess = thread_data.__dict__.get("sess")
    if not sess:
        sess = getsess()
        thread_data.__dict__["sess"] = sess
    auth = None
    if headers is None:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15"}
    if isinstance(data, dict):
        data["jsonrpc"]="2.0"
        if "id" not in data:
            data["id"] = 1
        if "params" not in data:
            data["params"] = []
    try:
        from config import GET_EXTRA_HEADERS
        headers.update(GET_EXTRA_HEADERS(endpoint))
    except:
        pass
    x = sess.post(endpoint, json=data, auth=auth, headers=headers, timeout=timeout, verify=verify)
    sys.x = x
    if os.getenv("PAUSE", False):
        input(f"pause... {x} {x.url}")
    return x

def callfunction(endpoint, addr, func_str, args_str, blockid="latest", returnint=True, from_=None, stateoverride=None):
    # stateoverride = {contract:{slot:value}}, here slot and value can be int
    if isinstance(endpoint, Endpoint_Provider):
        return endpoint.callfunction(addr, func_str, args_str, blockid=blockid, returnint=returnint, from_=from_)
    if os.environ.get("DEBUG", False):
        print("[callfunction]", endpoint, addr, func_str, "0x" + function_hash(func_str) + args_str, end="", flush=True)
    try:
        height = hex(int(blockid))
    except:
        height = blockid
    if isinstance(args_str, int) or len(args_str)<64:
        args_str = toarg(args_str)
    if args_str.startswith("0x"):
        args_str = args_str[2:]
    params = [{"data": "0x" + function_hash(func_str) + args_str, "to": addr, }, height]
    if stateoverride:
        s = {}
        for addr, v in stateoverride.items():
            s[addr] = {"stateDiff":{}}
            for slot, value in v.items():
                for i in ["balance","nonce","code"]:
                    if slot==i:
                        if isinstance(value, int):
                            value = hex(value)
                        s[addr][slot] = value
                        break
                else:
                    s[addr]["stateDiff"]["0x"+toarg(slot)] = "0x"+toarg(value)
        params.append(s)
    data = {
        "id": 1, "jsonrpc": "2.0",
        "method": "eth_call",
        "params": params
    }
    if from_ is not None:
        data["params"][0]["from"] = from_
    try:
        x = rpccall(endpoint, data)
    except Exception as e:
        raise CallNetworkFailed(e)
    if os.environ.get("DEBUG", False):
        print()
    if x.status_code!=200:
        raise CallRPCFailed(x.text[:1000], x.url, x)
    d = x.json()
    if "result" in d:
        res = d["result"]
    else:
        if "error" in d:
            try:
                msg = d["error"]["message"]
            except:
                raise CallRPCFailed(x.text[:1000], x.url, x)
            if msg.startswith("execution reverted"):
                if d["error"].get("data",None):
                    raise CallReverted(d["error"]["message"], d["error"]["data"])    
                else:
                    raise CallReverted(d["error"]["message"])
            else:
                raise CallRPCFailed(d["error"]["message"])
        else:
            print(x, x.request.body, x.text)
            raise CallNetworkFailed()
    if not returnint:
        return res
    else:
        return int(res, 16)


def erc20_balanceOf(endpoint, contract, addr):
    return callfunction(endpoint, contract, "balanceOf(address)", toarg(addr))
    
def erc20_allowance(endpoint, token, router, myaddr):
    return callfunction(endpoint, token, "allowance(address,address)", toarg(myaddr)+toarg(router))

def eth_getStorageAt(endpoint, contract, index, height="latest", format="int"):
    if isinstance(index, int):
        index = hex(index)
    if isinstance(height, int):
        height = hex(height)
    data = {
        "id":1, "jsonrpc":"2.0",
        "method":"eth_getStorageAt",
        "params":[contract, index, height]
    }
    x = rpccall(endpoint, data, timeout=5)
    shouldprint = os.environ.get("DEBUG", False)
    err = None
    try:
        res = x.json()["result"]
    except Exception as e:
        err = e
        shouldprint = True
    if shouldprint:
        print(x, x.text)
    if err:
        raise err
    if format == "int":
        return int(res, 16)
    elif format == "addr":
        return "0x"+res[-40:]
    else:
        return res

seenerrs = set()
def endpoint_broadcast(rpc, stx, ret=None, times=5):
    knownerrs = ["Non-hexadecimal digit found", "already known", "nonce too low", "Known transaction", "Too Many Requests", "insufficient funds for gas"]
    for i in range(times):
        try:
            txid = eth_sendRawTransaction(rpc, stx)
            if ret is not None and "tx" not in ret:
                ret["tx"] = txid
                print(txid)
        except NonceError:
            return
        except AlreadyKnownError:
            pass
        except Exception as e:
            if any([i in str(e) for i in knownerrs]):
                pass
                #return
            else:
                if (rpc, str(e)) not in seenerrs:
                    print(rpc, e)
                    seenerrs.add((rpc, str(e)) )
        sleep(1)
        if ret is not None and ret.get("done", False):
            return

def batch_callfunction(endpoint, datalist, height, timeout=None, returnerror=False):
    if isinstance(endpoint, Endpoint_Provider):
        return endpoint.batch_callfunction(datalist, height, timeout=timeout)
    if timeout is None:
        timeout = int(os.getenv("TIMEOUT",10))
    data = []
    idx = 0
    globalheight = toh(height)
    if os.environ.get("DEBUG", False):
        print("[batch_call]", len(datalist), "calls", endpoint)
    for item in datalist:
        height = globalheight
        extra = {}
        if len(item)==3:
            addr, func_str, args_str = item
        else:
            addr, func_str, args_str, extra = item
        idx += 1
        if extra.get("height", None):
            height = hex(extra["height"]) if isinstance(extra["height"], int) else extra["height"]
        if func_str == "eth_getStorageAt":
            if isinstance(args_str, int):
                args_str = hex(args_str)
            data.append({"id": idx, "jsonrpc":"2.0", "method":func_str,
                "params": [addr, args_str, height]
            })
        elif func_str == "eth_blockNumber":
            data.append({"id": idx, "jsonrpc":"2.0", "method":func_str,
                "params": []
            })
        elif func_str.startswith("eth_"):
            data.append({"id": idx, "jsonrpc":"2.0", "method":func_str,
                "params": [args_str, height]
            })
        else:
            if args_str.startswith("0x"):
                args_str = args_str[2:]
            param = {"data": "0x"+function_hash(func_str)+args_str, "to": addr,}
            if extra.get("from", None):
                param["from"] = extra["from"]
            if extra.get("value", None):
                v = extra["value"]
                if isinstance(v, int):
                    v = hex(v)
                param["value"] = v
            p = [param, height]
            if extra.get("override", None):
                s = {}
                for addr, v in extra["override"].items():
                    s[addr] = {"stateDiff":{}}
                    for slot, value in v.items():
                        for i in ["balance","nonce","code"]:
                            if slot==i:
                                if isinstance(value, int):
                                    value = hex(value)
                                s[addr][slot] = value
                                break
                        else:
                            s[addr]["stateDiff"]["0x"+toarg(slot)] = "0x"+toarg(value)
                p.append(s)
            data.append({"id": idx, "jsonrpc":"2.0", "method":"eth_call",
                "params":p
            })
    if os.environ.get("DEBUG_VERBOSE", False):
        print(data)
    x = rpccall(endpoint, data, timeout=timeout)
    sys.x = x
    if os.environ.get("DEBUG_VERBOSE", False):
        print(x.text, x)
    resjson = x.json()
    if not isinstance(resjson, list):
        resjson = [resjson]
    try:
        if returnerror:
            res = [(i["id"]-1,i.get("result", None),i.get("error", None)) for i in resjson]
        else:
            res = [(i["id"]-1,i.get("result", None)) for i in resjson]
    except TypeError as e:
        raise CallRPCFailed(e)
    #res.sort(key=lambda i:i[0])
    return res

def b16e(i):
    if isinstance(i, str) and i.startswith("0x"):
        return i
    return "0x"+b16encode(i).decode().lower()

def bd(result_str):
    # base16 decode rpc result str, return bytes
    if isinstance(result_str, bytes):
        return result_str
    if not result_str:
        return None
    if isinstance(result_str, tuple) and len(result_str)==2 and isinstance(result_str[0], int):
        result_str = result_str[1]
    if result_str.startswith("0x"):
        result_str = result_str[2:]
        if len(result_str)%2!=0:
            result_str = "0"+result_str
    return binascii.unhexlify(result_str.encode("ascii"))

MULTICALL={ #aggregate((address,bytes)[]) returns (uint256 blockNumber, bytes[] returnData)
    1:"0xca11bde05977b3631167028862be2a173976ca11",#eth
    42161:"0xca11bde05977b3631167028862be2a173976ca11",#arb
    8453:"0xca11bde05977b3631167028862be2a173976ca11",#base
    10:"0xca11bde05977b3631167028862be2a173976ca11",#op
    146:"0xca11bde05977b3631167028862be2a173976ca11",#sonic
    43114:"0xca11bde05977b3631167028862be2a173976ca11",#avax
    56:"0xca11bde05977b3631167028862be2a173976ca11",#bsc
}

def multicall_encode(multicall, params):
    calls = []
    for contract, func, args in params:
        calls.append([contract, bd("0x"+function_hash(func)+args)])
    return [multicall, "aggregate((address,bytes)[])", ec(["(address,bytes)[]"], [calls])]

def multicall_decode(todecode, outtypes):
    res = []
    if not isinstance(outtypes[0], list):
        outtypes = [outtypes]*len(todecode)
    for idx, item in enumerate(todecode):
        d = eth_abi.decode_abi(outtypes[idx], item)
        if len(d)==1:
            d = d[0]
        res.append(d)
    return res

def batch_callfunction_decode(endpoint, datalist, outtypes, height=None, needidx=False, timeout=int(os.getenv("TIMEOUT",10)), canfail=False, canrevert=False, usemulticall=None):
    if isinstance(endpoint, Endpoint_Provider):
        return endpoint.batch_callfunction_decode(datalist, outtypes, height=height, needidx=needidx, timeout=timeout)
    assert datalist, "empty datalist"
    import eth_abi
    if not height:
        height = "latest"
    if not isinstance(outtypes[0], list):
        outtypes = [outtypes]*len(datalist)
    if usemulticall:
        assert (not canfail) and (not canrevert), "multicall is not compatible with canfail/canrevert"
        if usemulticall is True:
            chainid = get_chainid(endpoint)
            assert chainid in MULTICALL, f"unknown multicall chain {chainid}"
            usemulticall = MULTICALL[chainid]
        assert usemulticall.startswith("0x"), "need MultiCall contract address"
        datalist2 = multicall_encode(usemulticall, datalist)
        data = batch_callfunction(endpoint, [datalist2], height, timeout=timeout)
        assert data[0][1] is not None, "multicall failed"
        bn, d = eth_abi.decode_abi(["uint","bytes[]"],bd(data[0][1]))
        return multicall_decode(d, outtypes)
    data = batch_callfunction(endpoint, datalist, height, timeout=timeout, returnerror=True)
    res = []
    for i, item, error in data:
        if not item:
            if canfail:
                res.append((i, None))
            elif canrevert and "revert" in str(error).lower():
                res.append((i, None))
            else:
                raise Exception(sys.x.text[:1000])
        else:
            #print(outtypes[i], item)
            try:
                if outtypes[i]==["raw"]:
                    d = item
                elif outtypes[i]==["hex"]:
                    d = int(item, 16)
                else:
                    d = eth_abi.decode_abi(outtypes[i], bd(item))
                    if len(d)==1:
                        d = d[0]
                res.append((i, d))
            except:
                if canfail:
                    res.append((i, None))
                else:
                    raise
    if needidx:
        return res
    else:
        return [i[1] for i in res]

def batch_eth_balanceOf(endpoint, addrs):
    return [int(i[1], 16) for i in batch_callfunction(endpoint, [["", "eth_getBalance", addr] for addr in addrs], "latest")]

_IMPLEMENTATION_SLOT = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
def getImpl(endpoint, address, height="latest"):
    return eth_getStorageAt(endpoint, address, _IMPLEMENTATION_SLOT, height, "addr")
    
class NoBlock(Exception):
    def __init__(self, text):
        self.text = text
def Endpoint_Provider_retry_wrapper_allowexc(allowed_exceptions=None):
    if allowed_exceptions is None:
        allowed_exceptions = [CallReverted, TypeError, NonceError, BaseFeeError, TxTimeout, KeyboardInterrupt, AssertionError, eth_abi.exceptions.DecodingError, eth_abi.exceptions.EncodingError]
    def Endpoint_Provider_retry_wrapper(f):
        @wraps(f)
        def do_f(self, *args, **kwargs):
            retrytimes = kwargs.get("retrytimes", 3)
            checker = kwargs.get("checker", None)
            if "retrytimes" in kwargs:
                del kwargs["retrytimes"]
            if "checker" in kwargs:
                del kwargs["checker"]
            exc = None
            for i in range(retrytimes):
                j = 0
                for n in self.endpoints[:]:
                    #print("about to try",n)
                    self.E = n
                    j += 1
                    sys.x = None
                    try:
                        res = f(self, *args, **kwargs)
                        if checker:
                            checker(res)
                        return res
                    except Exception as e:
                        exc = e
                        if allowed_exceptions:
                            if any([isinstance(e, i) for i in allowed_exceptions]):
                                raise
                        if os.getenv("DEBUG"):
                            traceback.print_exc()
                        print("[error]", str(e)[:100], "retry:", i, "bad_node:", n, sys.x, end=" ", file=sys.stderr)
                        if sys.x:
                            print(sys.x.text.strip()[:1000], file=sys.stderr)
                        self.endpoints = self.endpoints[1:]+[self.endpoints[0]]
                        if retrytimes!=1 and i==retrytimes-1:
                            traceback.print_exc()
                if retrytimes!=1:
                    print("all failed, sleep 1", f.__name__, args, kwargs, sys.argv)
                    sleep(1)
            raise exc
        return do_f
    return Endpoint_Provider_retry_wrapper

Endpoint_Provider_retry_wrapper=Endpoint_Provider_retry_wrapper_allowexc()

class Endpoint_Provider():
    def __init__(self, endpoints):
        self.endpoints = endpoints
        self.E = endpoints[0]
    def batch_callfunction_decode_canfail(self, *args, **kwargs):
        kwargs["canfail"] = True
        return batch_callfunction_decode(self.E, *args, **kwargs)
    def rotateE(self):
        random.shuffle(self.endpoints)
        self.E = self.endpoints[0]
    def __getattr__(self, method_name):
        f = globals()[method_name]
        @Endpoint_Provider_retry_wrapper
        @wraps(f)
        def method(self, *args, **kwargs):
            nonlocal method_name
            if "DEBUG" in os.environ:
                print("method:", method_name, args, kwargs)
            return f(self.E, *args, **kwargs)
        ret = partial(method, self)
        ret.__qualname__ = "Endpoint_Provider."+f.__qualname__
        return ret
    def __dir__(self):
        return [i for i in globals() if i.startswith("eth_")]

def split_solidity_signature(params_string):  
    if "(" not in params_string:
        return params_string.split(",")

    params = []
    nesting_level = 0
    current_param_start_index = 0

    for i, char in enumerate(params_string):
        if char == '(':
            nesting_level += 1
        elif char == ')':
            nesting_level -= 1
        elif char == ',' and nesting_level == 0:
            param = params_string[current_param_start_index:i].strip()
            params.append(param)
            current_param_start_index = i + 1
    last_param = params_string[current_param_start_index:].strip()
    params.append(last_param)
    return params

def ed(abi, calldata):
    if len(calldata)%64==10:
        calldata = calldata[10:]
    if isinstance(abi, str):
        abi = split_solidity_signature(abi)
    return eth_abi.decode_abi(abi, bd(calldata))

def ec(abi, calldata):
    if isinstance(abi, str):
        abi = abi.split(",")
    return b16e(eth_abi.encode_abi(abi, calldata))[2:]

def eth_accounts(endpoint=L):
    return rpccall(endpoint, {"method":"eth_accounts"}).json()["result"]

def debugtrace(endpoint, txhash):
    res = simple_rpccall(endpoint, "debug_traceTransaction", [txhash, {"enableMemory": True, "enableReturnData": True}], timeout=600)
    l = res['structLogs']
    for idx, item in enumerate(l):
        item["idx"] = idx
    return l

def debugtrace_calltracer(endpoint, txhash):
    return simple_rpccall(endpoint, "debug_traceTransaction", [txhash, {"tracer":"callTracer"}], timeout=600)

def eth_getBlockByNumber(endpoint, height, needtx=True, verify=False):
    if isinstance(height, int):
        height = hex(height)
    res = {}
    x = None
    try:
        x = rpccall(endpoint, {"id":6,"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[height,needtx]})
        if os.environ.get("DEBUG_VERBOSE", False):
            print(endpoint, x, x.text, height)
        res = x.json()["result"]
    except KeyboardInterrupt:
        raise
    except:
        if os.environ.get("DEBUG", False):
            if x:
                print(x, x.text, endpoint)
            traceback.print_exc()
        pass
    if not res or "transactions" not in res:
        if x:
            raise NoBlock(x.text[:1000])
        else:
            raise NoBlock("network failed, no x")
    if verify:
        validate_tx_sender(res)
    return res

def eth_blockNumber(endpoint):
    return simple_rpccall(endpoint, "eth_blockNumber", [], returnint=True)

def eth_gasPrice(endpoint):
    if isinstance(endpoint, Endpoint_Provider):
        return endpoint.eth_gasPrice()
    return simple_rpccall(endpoint, "eth_gasPrice", [], returnint=True)

def toi(text):
    if text is None:
        return None
    if isinstance(text, int):
        return text
    if text.startswith("0x"):
        return int(text, 16)
    print("warning: toi", text)
    return int(text, 16)
toint = toi
def toh(i):
    if isinstance(i, str):
        return i
    return hex(i)

LOG_TRANSFER="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def eth_getLogs(endpoint, fromBlock, toBlock="latest", topics0=LOG_TRANSFER, moretopics=None, address=None, blockhash=None):
    topics = []
    if topics0:
        topics = [topics0]
        if moretopics:
            topics.extend(moretopics)
    param = {"fromBlock": toh(fromBlock), "toBlock": toh(toBlock), "topics": topics}
    if address is not None:
        param["address"] = address
    if blockhash is not None:
        param["blockhash"] = blockhash
    x = rpccall(endpoint, {"method":"eth_getLogs", "params":[param]})
    sys.x=x
    return x.json()["result"]


def safefilename(filename):
    """
    convert a string to a safe filename
    :param filename: a string, may be url or name
    :return: special chars replaced with _
    """
    for i in "\\/:*?\"<>|$":
        filename=filename.replace(i,"_")
    return filename

class TxNotFound(Exception):
    pass

def eth_getTransactionANDReceipt_naive(endpoint, txid, allow_incorrect=True, canNone=True):
    tx = simple_rpccall(endpoint, "eth_getTransactionByHash", [txid])
    receipt = simple_rpccall(endpoint, "eth_getTransactionReceipt", [txid])
    if not tx:
        if canNone:
            return None
        else:
            raise TxNotFound(endpoint, txid, False)
    tx["from"] = tx["from"].lower()
    if not allow_incorrect:
        sender = recover_sender(tx)
        if sender:
            if sender != tx["from"]:
                sender = recover_sender(tx, forceNoChain=True)
            assert tx["from"] == sender, ("tx sender mismatch", tx["hash"], sender, tx["from"])
    if not receipt:
        if canNone:
            return None
        else:
            raise TxNotFound(endpoint, txid, True)
    tx.update(receipt)
    tx["from"] = tx["from"].lower()
    if not allow_incorrect:
        if sender:
            assert tx["from"] == sender, ("tx receipt sender mismatch", tx["hash"], sender, tx["from"])
    return tx

def eth_getTransactionANDReceipt(endpoint, txid, allow_incorrect=True, usenaive=False, canNone=True):
    if usenaive:
        return eth_getTransactionANDReceipt_naive(endpoint, txid, allow_incorrect=allow_incorrect)
    data = [{
        "id":1, "jsonrpc":"2.0",
        "method":"eth_getTransactionByHash",
        "params":[txid]
    }, {
        "id":2, "jsonrpc":"2.0",
        "method":"eth_getTransactionReceipt",
        "params":[txid]
    }, ]
    x = rpccall(endpoint, data)
    assert x.status_code == 200, (x.text[:1000], x.url, x)
    if os.environ.get("DEBUG_VERBOSE"):
        print(x.text)
    tx, receipt = x.json()
    tx = tx["result"]
    if not tx:
        if canNone:
            return None
        else:
            raise TxNotFound(endpoint, txid, False)
    tx["from"] = tx["from"].lower()
    if not allow_incorrect:
        sender = recover_sender(tx)
        if sender:
            if sender != tx["from"]:
                sender = recover_sender(tx, forceNoChain=True)
            assert tx["from"] == sender, ("tx sender mismatch", tx["hash"], sender, tx["from"])
    if "result" not in receipt or not receipt["result"]:
        if canNone:
            return None
        else:
            raise TxNotFound(endpoint, txid, True)
    tx.update(receipt["result"])
    if not allow_incorrect:
        if sender:
            assert tx["from"] == sender, ("tx receipt sender mismatch", tx["hash"], sender, tx["from"])
    return tx

def batch_eth_getTransactionANDReceipt(endpoint, txids):
    data = []
    for txid in txids:
        data.append({
            "id":len(txids), 
            "jsonrpc":"2.0",
            "method":"eth_getTransactionByHash",
            "params":[txid]
        })
        data.append({
            "id":len(txids), 
            "jsonrpc":"2.0",
            "method":"eth_getTransactionReceipt",
            "params":[txid]
        })
    x = rpccall(endpoint, data)
    assert x.status_code == 200, (x.text[:1000], x.url, x)
    if os.environ.get("DEBUG_VERBOSE"):
        print(x.text)
    res = {}
    for idx, txid in enumerate(txids):
        tx, receipt = x.json()[idx*2:idx*2+2]
        if not tx["result"] and not receipt["result"]:
            print("not found txid:", txid)
            continue
        res[txid] = tx["result"]
        res[txid].update(receipt["result"])
    return res

def simple_rpccall(endpoint, method, params, returnint=False, returnx=False, headers=None, verify=True, timeout=None):
    if isinstance(endpoint, Endpoint_Provider):
        return endpoint.simple_rpccall(method, params, returnint=returnint, returnx=returnx, headers=headers, verify=verify)
    if endpoint.endswith("/api/eth-rpc"): #blockscout API
        if method=="eth_getBalance":
            params[1] = str(int(params[1], 16))
    data={"method":method, "params":params}
    x = rpccall(endpoint, data, headers=headers, verify=verify, timeout=timeout)
    if x.status_code not in [200,201]:
        raise CallRPCFailed(x.text[:1000], x.url, x)
    if os.environ.get("DEBUG_VERBOSE"):
        print(x.text)
    if returnx:
        return x
    d = x.json()
    if "error" in d and d["error"]:
        if isinstance(d["error"], dict) and "message" in d["error"]:
            msg = d["error"]["message"]
        else:
            msg = str(d["error"])
        if msg.startswith("execution reverted"):
            if d["error"].get("data",None):
                raise CallReverted(d["error"]["message"], d["error"]["data"])
            else:
                raise CallReverted(d["error"]["message"])
        else:
            raise CallRPCFailed(d["error"]["message"])
    if "result" in d:
        res = d["result"]
    else:
        print(x, x.request.body, x.text)
        raise CallNetworkFailed()
    if returnint:
        if isinstance(res, str):
            res = int(res,16)
    return res

def eth_getTransactionReceipt(endpoint, txid):
    return simple_rpccall(endpoint, "eth_getTransactionReceipt", [txid])

def eth_getCode(endpoint, addr):
    return simple_rpccall(endpoint, "eth_getCode", [addr, "latest"])

def eth_getNonce(endpoint, addr, height="latest"):
    return simple_rpccall(endpoint, "eth_getTransactionCount", [addr, toh(height)], returnint=True)
eth_getTransactionCount = eth_getNonce

def eth_getBalance(endpoint, address, height="latest"):
    if isinstance(endpoint, Endpoint_Provider):
        return endpoint.eth_getBalance(address, height=height)
    return simple_rpccall(endpoint, "eth_getBalance", [address, toh(height)], returnint=True) 
eth_balanceOf = eth_getBalance

def eth_sendRawTransaction(endpoint, tx_hex):
    global TXSENT
    TXSENT = True
    if not isinstance(tx_hex, str):
        tx_hex = tx_hex.hex()
    if not tx_hex.startswith("0x"):
        tx_hex = "0x"+tx_hex
    try:
        return simple_rpccall(endpoint, "eth_sendRawTransaction", [tx_hex])
    except Exception as e:
        if "nonce too low" in str(e):
            raise NonceError(e)
        elif "max fee per gas less than block base fee" in str(e):
            raise BaseFeeError(e)
        elif "already known" in str(e) or "Known transaction" in str(e):
            raise AlreadyKnownError(e)
        elif "transaction underpriced" in str(e):
            raise UnderPricedError(e)
        else:
            raise

def eth_sendRawTransactionConditional(endpoint, tx_hex, options):
    if not isinstance(tx_hex, str):
        tx_hex = tx_hex.hex()
    if not tx_hex.startswith("0x"):
        tx_hex = "0x"+tx_hex
    return simple_rpccall(endpoint, "eth_sendRawTransactionConditional", [tx_hex, options])

def batch_callRPC(data, checkfunc=None, endpoint=None):
    assert endpoint is not None, "batch_callRPC need endpoint"
    try:
        x = rpccall(endpoint, data)
        res = x.json()
        if checkfunc:
            checkfunc(res)
    except Exception as e:
        if os.getenv("DEBUG", False):
            print("batch_callRPC failed:", e)
        raise
    return res

def batch_eth_getBlockByNumber(endpoint, heights, detail=True, returnraw=False, verify=False):
    data = []
    for height in heights:
        if isinstance(height, int):
            height = hex(height)
        data.append({"id":len(data),"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[height,detail]})
    def f(res):
        assert res and "transactions" in res[0]["result"]
    res = batch_callRPC(data, checkfunc=f, endpoint=endpoint)
    if returnraw:
        return res
    else:
        ret = [i["result"] for i in res]
        if verify:
            if verify=="quick":
                [validate_tx_sender(i, quick=True) for i in ret[:5]]
            else:
                [validate_tx_sender(i) for i in ret[:5]]
        return ret

def batch_getNonce(endpoint, addrs, height="latest"):
    data = []
    if isinstance(height, int):
        height = hex(height)
    for addr in addrs:
        data.append({"id":len(data), "jsonrpc":"2.0","method":"eth_getTransactionCount","params":[addr,height]})
    res = batch_callRPC(data, endpoint=endpoint)
    return [int(i["result"], 16) for i in res]
batch_eth_getNonce = batch_getNonce

def batch_getTransaction(endpoint, hashes):
    data = []
    for h in hashes:
        data.append({"id":len(data), "jsonrpc":"2.0","method":"eth_getTransactionByHash","params":[h]})
    res = batch_callRPC(data, endpoint=endpoint)
    return [i["result"] for i in res]

def batch_getTransactionReceipt(endpoint, hashes):
    data = []
    for h in hashes:
        data.append({"id":len(data), "jsonrpc":"2.0","method":"eth_getTransactionReceipt","params":[h]})
    res = batch_callRPC(data, endpoint=endpoint)
    return [i["result"] for i in res]

class class_PYTHPRICE():
    def load_conf(self, refresh=False):
        if not self.conf:
            if (not refresh) and os.path.isfile("/tmp/pyth.json"):
                self.conf = json.load(open("/tmp/pyth.json"))
            else:
                self.conf = sess.get("https://benchmarks.pyth.network/v1/price_feeds/?asset_type=crypto").json()
                open("/tmp/pyth.json", "w").write(json.dumps(self.conf))
        return self.conf

    def __init__(self, cachetime=60, refresh=False):
        self.conf = None
        self.cache = {}
        self.cachetime = cachetime
        if refresh:
            self.load_conf(refresh=True)

    def __getattr__(self, token):
        if token in self.cache and time.time()-self.cache[token][0]<self.cachetime:
            return self.cache[token][1]
        conf = self.load_conf()
        pythid = [i for i in conf if i["attributes"]["generic_symbol"]==token.upper()+"USD"][0]["id"]
        x = sess.get("https://hermes.pyth.network/api/latest_price_feeds?ids[]="+pythid)
        p = x.json()[0]["price"]
        price = float(p["price"])*10**(p["expo"])
        self.cache[token] = [p["publish_time"], price]
        return price
PYTHP = class_PYTHPRICE()

class class_CEXPRICE():
    def __init__(self, cachetime=60):
        self.updatetime = -1
        self.cachetime = cachetime
    def __getattr__(self, token):
        if token.startswith("__"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{token}'")
        if time.time()-self.updatetime>=self.cachetime:
            print("fetch", self.__class__.__name__.replace("class_", ""), token, end="", flush=True)
            self.data = self.fetchprice()
            print()
            self.updatetime = time.time()
        return self.handleprice(token)

class class_BINANCE_Price(class_CEXPRICE):
    def fetchprice(self):
        return sess.get("https://api.binance.com/api/v3/ticker/price", timeout=5).json()
    def handleprice(self, token):
        if token.lower()=="usdt":
            return 1
        if token.lower()=="dai":
            return 1/float(self.handleprice("usdtdai"))
        if "busd" not in token.lower() and "usdt" not in token.lower():
            token = token.lower()+"usdt"
        return [i for i in self.data if i["symbol"]==token.upper()][0]["price"]
BP=BINANCE_Price=class_BINANCE_Price()
class _fBP():
    def __getattr__(self, token):
        p = getattr(BP, token)
        return float(p)
fBP=_fBP()

class class_BINANCE_Future_Price(class_CEXPRICE):
    def fetchprice(self):
        return sess.get("https://fapi.binance.com/fapi/v1/ticker/price", timeout=5).json()
    def handleprice(self, token):
        return [i for i in self.data if i["symbol"]==token.upper()][0]["price"]
BFP=BINANCE_Future_Price=class_BINANCE_Future_Price()

class class_BINANCE_MARGIN_COST(class_CEXPRICE):
    def fetchprice(self):
        return sess.get("https://www.binance.com/bapi/margin/v1/friendly/isolated-margin/pair/vip-level", timeout=5).json()["data"]
    def handleprice(self, pair):
        base,quote = pair.upper().split("_")
        x = [i for i in self.data if i["base"]["assetName"]==base and i["quote"]["assetName"]==quote][0]
        return x["base"]["levelDetails"][0]
# BINANCE_MARGIN_Cost.mdx_usdt == {level: "0", maxBorrowable: "1600.00000000", interestRate: "0.00120000"}
BINANCE_MARGIN_Cost=class_BINANCE_MARGIN_COST(3600)

class class_MXC_Price(class_CEXPRICE):
    def fetchprice(self):
        return sess.get("https://www.mxc.com/open/api/v2/market/ticker", timeout=5).json()["data"]
    def handleprice(self, token):
        return [i for i in self.data if i["symbol"]==token.upper()+"_USDT"][0]["last"]
MXC_Price = class_MXC_Price()

class class_OKX_Price(class_CEXPRICE):
    def fetchprice(self):
        return sess.get("https://www.okx.com/api/v5/market/tickers?instType=SPOT", timeout=5).json()["data"]
    def handleprice(self, token):
        return [i for i in self.data if i["instId"]==token.upper()+"-USDT"][0]["last"]
OKX_Price = OKEX_Price = class_OKX_Price()

class class_Kucoin_Price(class_CEXPRICE):
    def fetchprice(self):
        return sess.get("https://api.kucoin.com/api/v1/market/allTickers", timeout=5).json()["data"]["ticker"]
    def handleprice(self, token):
        return [i for i in self.data if i["symbol"]==token.upper()+"-USDT"][0]["last"]
Kucoin_Price = class_Kucoin_Price()

FUNC_APPROVE = '0x095ea7b3'
FUNC_TRANSFER = '0xa9059cbb'


def showlp(endpoint, lpaddr):
    token0, token1 = batch_callfunction_decode(endpoint, [[lpaddr, "token0()", ""], [lpaddr, "token1()", ""]], ["address"])
    symbol0, decimal0, symbol1, decimal1, (r0, r1) = batch_callfunction_decode(endpoint, [
        [token0, "symbol()", ""], [token0, "decimals()", ""], 
        [token1, "symbol()", ""], [token1, "decimals()", ""],
        [lpaddr, "getReserves()", ""]
    ], [["string"], ["uint256"], ["string"], ["uint256"], ["uint256", "uint256"]])
    price0 = r0/10**decimal0 / (r1/10**decimal1)
    price1 = 1/price0
    print(f"""token0: {symbol0}\t{decimal0}
token1: {symbol1}\t{decimal1}
Price: 1{symbol1}=\t{price0:.4f} {symbol0}    lpprice(RPC, "{lpaddr}", {decimal0}, {decimal1})[0]
       1{symbol0}=\t{price1:.4f} {symbol1}    lpprice(RPC, "{lpaddr}", {decimal0}, {decimal1})[1]""")

def showlp_naive(endpoint, lpaddr, returndata=False):
    token0 = "0x"+callfunction(endpoint, lpaddr, "token0()", "", "latest", False)[-40:]
    token1 = "0x"+callfunction(endpoint, lpaddr, "token1()", "", "latest", False)[-40:]
    symbol0 = eth_abi.decode_abi(["string"], bd(callfunction(endpoint, token0, "symbol()", "", "latest", False)))[0]
    symbol1 = eth_abi.decode_abi(["string"], bd(callfunction(endpoint, token1, "symbol()", "", "latest", False)))[0]
    decimal0 = callfunction(endpoint, token0, "decimals()", "")
    decimal1 = callfunction(endpoint, token1, "decimals()", "")
    r0, r1, _ = eth_abi.decode_abi(["uint256"]*3, bd(callfunction(endpoint, lpaddr, "getReserves()", "", "latest", False)))
    price0 = r0/10**decimal0 / (r1/10**decimal1)
    price1 = 1/price0
    text = f"token0: {symbol0}\t{decimal0}\ntoken1: {symbol1}\t{decimal1}\nPrice: 1{symbol1}=\t{price0:.4f} {symbol0}\n       1{symbol0}=\t{price1:.4f} {symbol1}"
    if returndata:
        return locals()
    print(text)

def lpprice(endpoint, lpaddr, decimal0=18, decimal1=18, needDecimal=False):
    r0, r1, _ = eth_abi.decode_abi(["uint256"]*3, bd(callfunction(endpoint, lpaddr, "getReserves()", "", "latest", False)))
    if needDecimal:
        r0, r1 = D(r0), D(r1)
    price0 = r0/10**decimal0 / (r1/10**decimal1)
    price1 = 1/price0
    return price0, price1


def recover_sender(tx, forceNoChain=False):
    if forceNoChain:
        print("forceNoChain enabled for tx:", tx["hash"])
    if toi(tx["from"])==0:
        return #bevm system tx
    if "v" not in tx: # zksync system tx
        return
    v, r, s = toi(tx["v"]), toi(tx["r"]), toi(tx["s"])
    if v == r == s == 0: #polygon system tx
        return
    if "type" not in tx: #mantle
        typ = 0
    else:
        typ = toi(tx["type"])
    if typ==0:
        (chain_id, _v) = eth_account._utils.signing.extract_chain_id(v)
        gp = toi(tx["gasPrice"])
        if "maxFeePerGas" in tx: #zksync
            gp = toi(tx["maxFeePerGas"])
        if forceNoChain or not chain_id:
            data = [toi(tx["nonce"]), gp, toi(tx["gas"]), bd(tx["to"]) if tx["to"] else b'', toi(tx["value"]), bd(tx["input"])]
            msg_hash = eth_account._utils.legacy_transactions.UnsignedTransaction(*data).hash()
        else:
            data = [toi(tx["nonce"]), gp, toi(tx["gas"]), bd(tx["to"]) if tx["to"] else b'', toi(tx["value"]), bd(tx["input"]), chain_id, 0, 0]
            msg_hash = eth_account._utils.legacy_transactions.ChainAwareUnsignedTransaction(*data).hash()
    elif typ in [1,2,3]:
        tx_dict = {
            "r":tx["r"],"s":tx["s"],"v":tx["v"],
            "type":tx["type"],"nonce":tx["nonce"],
            "gas":tx["gas"],
            "to":bd(tx["to"]) if tx["to"] else None,
            "data":tx["input"],"accessList":tx.get("accessList",[]),
            "chainId":tx["chainId"],
            "value":tx["value"]
        }
        if "blobVersionedHashes" in tx:
            tx_dict.update({
                "blobVersionedHashes":tx["blobVersionedHashes"],
                "maxFeePerBlobGas":tx["maxFeePerBlobGas"],
            })
        if "maxFeePerGas" in tx:
            tx_dict.update({
                "maxFeePerGas":tx["maxFeePerGas"],
                "maxPriorityFeePerGas":tx["maxPriorityFeePerGas"],
            })
        else:
            tx_dict.update({
                "gasPrice": tx["gasPrice"]
            })
        try:
            TypedTransaction = eth_account._utils.typed_transactions.TypedTransaction
        except:
            TypedTransaction = eth_account.typed_transactions.TypedTransaction
        try:
            msg_hash = TypedTransaction.from_dict(tx_dict).hash()
        except:
            return
    else:
        return
    sender = eth_account.account.Account._recover_hash(msg_hash, (v,r,s))
    return sender.lower()


def validate_tx_sender(tx, _raise=True, quick=False):
    ok = True
    if "transactions" in tx: #block param
        tx = tx["transactions"]
        if quick and len(tx)>10:
            tx = tx[:5] + tx[-5:]
    if not isinstance(tx, list):
        txs = [tx]
    else:
        txs = tx
    for tx in txs:
        sys.tx = tx
        sender = recover_sender(tx)
        if sender:
            if _raise:
                if sender != tx["from"].lower():
                    sender = recover_sender(tx, forceNoChain=True)
                assert sender == tx["from"].lower(), ("tx sender mismatch", tx["hash"], sender, tx["from"])
            else:
                if sender != tx["from"].lower():
                    ok = False
    return ok

def eth_getRawTransaction(endpoint, txhash):
    return simple_rpccall(endpoint, "eth_getRawTransactionByHash", [txhash])

MAX = 2**256 - 1

def hex2str(hexvalue):
    return b16decode(hexvalue.upper().replace("0X","")).decode()

sol_Memo = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
sol_RPC = "https://api.mainnet-beta.solana.com"
def sol2hex(hash):
    import base58
    return to256x(int.from_bytes(base58.b58decode(hash), "big"))
def hex2sol(hexvalue):
    import base58
    return base58.b58encode(int(hexvalue, 16).to_bytes(32,"big")).decode()

def sol_getBalance(endpoint, addr, commitment="processed", returnraw=False):
    x = simple_rpccall(endpoint, "getBalance", [addr, {"commitment":commitment}])
    if returnraw:
        return x
    return x["value"]

sol_balanceOf = sol_getBalance

def sol_blockNumber(endpoint, commitment="processed"):
    return simple_rpccall(endpoint, "getBlockHeight", [{"commitment":commitment}])

def sol_slotNumber(endpoint, commitment="processed"):
    return simple_rpccall(endpoint, "getSlot", [{"commitment":commitment}])

def sol_getAccountInfo(endpoint, addr, encoding="jsonParsed", commitment="processed"):
    return simple_rpccall(endpoint, "getAccountInfo", [str(addr), {"commitment":commitment, "encoding":encoding}])

def sol_getNonceFromAccount(endpoint, addr, returnslot=False):
    x = sol_getAccountInfo(endpoint, addr)
    hash = x["value"]["data"]["parsed"]["info"]["blockhash"]
    if returnslot:
        return hash, x["context"]["slot"]
    else:
        return hash

def sol_getBlock(endpoint, slot_number, encoding="jsonParsed", transactionDetails="full", commitment="processed"):
    b = simple_rpccall(endpoint, "getBlock", [slot_number, {"encoding":encoding, "transactionDetails":transactionDetails, "commitment":commitment, "maxSupportedTransactionVersion":0}])
    #non_votes = [i for i in b["transactions"] if i["transaction"]["message"]["instructions"][0]["programId"]!="Vote111111111111111111111111111111111111111"]
    return b

def sol_getTransaction(endpoint, txhash, encoding="jsonParsed", commitment="confirmed", allow_incorrect=None):
    #not found => return None
    #tx["slot"], tx["blockTime"] not in sol_getBlock().transactions
    return simple_rpccall(endpoint, "getTransaction", [txhash, {"encoding":encoding, "commitment":commitment, "maxSupportedTransactionVersion":0}])

sol_getTransactionANDReceipt = sol_getTransaction
sol_getTransactionReceipt = sol_getTransaction

def sol_getTokenAccount(token_mint, user):
    from solders.token.associated import get_associated_token_address
    user = sol_topubkey(user)
    token_mint = sol_topubkey(token_mint)
    return str(get_associated_token_address(user, token_mint))

def sol_splBalance(endpoint, token, user):
    #{'amount': '9179527', 'decimals': 6, 'uiAmount': 9.179527, 'uiAmountString': '9.179527'}
    token_account = sol_getTokenAccount(token, user)
    info = sol_getAccountInfo(endpoint, token_account)
    return info["value"]["data"]["parsed"]["info"]["tokenAmount"]

def sol_getRecentPrioritizationFees(endpoint, accounts):
    if not isinstance(accounts, (list,tuple)):
        accounts = [accounts]
    accounts = [str(i) for i in accounts]
    return simple_rpccall(endpoint, "getRecentPrioritizationFees", [accounts])

def sol_getLatestBlockhash(endpoint, commitment="processed", returnraw=False):
    x = simple_rpccall(endpoint, "getLatestBlockhash", [{"commitment":commitment}])
    if returnraw:
        return x
    #print("sol_getLatestBlockhash", endpoint, x)
    return x["value"]["blockhash"]

def sol_sendTransaction(endpoint, stx, skipPreflight=False, preflightCommitment="processed"):
    return simple_rpccall(endpoint, "sendTransaction", [stx, {"skipPreflight":skipPreflight, "preflightCommitment":preflightCommitment}])
sol_sendRawTransaction = sol_sendTransaction
def sol_getMinimumBalanceForRentExemption(endpoint, size=0):
    return simple_rpccall(endpoint, "getMinimumBalanceForRentExemption", [size])
sol_minTransfer = sol_getMinimumBalanceForRentExemption

def sol_topub(pk):
    from solders.keypair import Keypair
    return str(Keypair.from_base58_string(pk).pubkey())

def sol_maketx_createNonceAccount(endpoint, pk, rent_value=1447680, needstx=False, gasprice=None, gaslimit=None):
    import base58
    from solders.hash import Hash
    from solders.keypair import Keypair
    from solders.system_program import create_nonce_account
    from solana.transaction import Transaction
    from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
    sender = Keypair.from_base58_string(pk)
    nonceacc = Keypair()
    if not rent_value:
        rent_value = sol_getMinimumBalanceForRentExemption(endpoint, 80)
    instructions = list(create_nonce_account(
        from_pubkey=sender.pubkey(),
        nonce_pubkey=nonceacc.pubkey(),
        authority=sender.pubkey(),
        lamports=rent_value
    ))
    tx = sol_maketx(endpoint, instructions, pk, nonceacc=None, noncevalue=None, needstx=needstx,
        memo=None, gasprice=gasprice, gaslimit=gaslimit, morekeys=[nonceacc])
    return str(nonceacc.pubkey()), tx

def sol_simulateTransaction(endpoint, stx, innerInstructions=True, commitment="processed"):
    return simple_rpccall(endpoint, "simulateTransaction", [stx, {"encoding":"base58","sigVerify":False,"commitment":commitment,"replaceRecentBlockhash":True, "innerInstructions":innerInstructions}])

def sol_topubkey(addr):
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    if isinstance(addr, str):
        return Pubkey.from_string(addr)
    elif isinstance(addr, Keypair):
        return addr.pubkey()
    else:
        assert isinstance(addr, Pubkey), addr
        return addr

def sol_getpda(programid, *seeds, returnbump=False):
    from solders.pubkey import Pubkey
    s = []
    if len(seeds)==1 and isinstance(seeds[0], list):
        seeds = seeds[0]
    for i in seeds:
        if isinstance(i, Pubkey):
            i = bytes(i)
        elif isinstance(i, str):
            i = i.encode("utf-8")
        assert isinstance(i, bytes), i
        s.append(i)
    x = Pubkey.find_program_address(s, sol_topubkey(programid))
    if returnbump:
        return x
    return x[0]

def sha256(s, returnbytes=False):
    if isinstance(s, str):
        s = s.encode("utf-8")
    x = hashlib.sha256(s)
    if returnbytes:
        return x.digest()
    else:
        return x.hexdigest()

def sol_anchor_instruction(programid, funcname, binargs, accounts):
    from solders.instruction import AccountMeta, Instruction
    accs = []
    for addr, is_signer, is_writable in accounts:
        accs.append(AccountMeta(sol_topubkey(addr), is_signer, is_writable))
    if not binargs:
        binargs = b''
    prefix = b''
    if funcname:
        prefix = sha256("global:"+funcname, returnbytes=True)[:8]
    data = prefix + binargs
    return Instruction(sol_topubkey(programid), data, accs)

def sol_maketx(endpoint, instructions, pk, nonceacc=None, noncevalue=None, needstx=False, memo=None, 
               gasprice=None, gaslimit=None, gasratio=1.5, morekeys=None, partialsign=False, 
               skipPreflight=False, viewonly=False, usev0=False, feepayer=None):
    import base58
    from solders.hash import Hash
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    from solders.system_program import AdvanceNonceAccountParams, advance_nonce_account
    from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
    from solana.transaction import Transaction
    from solders.instruction import AccountMeta, Instruction
    from solders.message import MessageV0, to_bytes_versioned
    from solders.transaction import VersionedTransaction
    from solders.null_signer import NullSigner
    # client pk
    sender = Keypair.from_base58_string(pk)
    # if feepay is none use client pk
    # if not should be facilitator
    if feepayer is None:
        feepayer = sender.pubkey()
    else:
        feepayer = sol_topubkey(feepayer)
    if isinstance(instructions, Instruction):
        instructions = [instructions]
    instructions = list(instructions)

    # get recent_blockhash
    if nonceacc:
        nonceacc = sol_topubkey(nonceacc)
        advance = advance_nonce_account(AdvanceNonceAccountParams(
            nonce_pubkey=nonceacc, 
            authorized_pubkey=sender.pubkey()
        ))
        instructions.insert(0,advance)
        if noncevalue:
            bh = noncevalue
        else:
            bh = sol_getNonceFromAccount(endpoint, str(nonceacc))
            print("nonce value:", bh)
    else:
        bh = sol_getLatestBlockhash(endpoint)
    
    # default false
    if viewonly:
        transaction = Transaction(recent_blockhash=Hash.from_string(bh), instructions=instructions, fee_payer=feepayer)
        estimatex = sol_simulateTransaction(endpoint, base58.b58encode(transaction.serialize(verify_signatures=False)).decode())
        sys.estimatex = estimatex
        res = b64decode([i for i in estimatex["value"]["logs"] if i.startswith("Program return:")][0].split()[-1])
        return res

    # support add Memo Program instruction
    if memo is not None:
        if isinstance(memo, str):
            memo = memo.encode("utf-8")
        memoins = Instruction(accounts=[AccountMeta(pubkey=sender.pubkey(), is_signer=True, is_writable=True)], program_id=sol_topubkey(sol_Memo), data=memo)
        instructions.append(memoins)
    
    # 
    if gasprice is None:
        transaction = Transaction(recent_blockhash=Hash.from_string(bh), instructions=instructions, fee_payer=feepayer)
        m = transaction.compile_message()
        sys.m = m
        writetos = [str(i) for idx,i in enumerate(m.account_keys) if m.is_writable(idx)]
        print("write to:", writetos)
        feex = sol_getRecentPrioritizationFees(endpoint, writetos)
        priorityfees = [i["prioritizationFee"] for i in feex]
        if os.getenv("DEBUG", False):
            print("priorityfees:", priorityfees)
        fee = max(priorityfees[-10:])
    else:
        fee = gasprice
    if fee:
        print("[sol tx] priority fee:", fee, end=" ")
        instructions.append(set_compute_unit_price(fee))
        transaction = Transaction(recent_blockhash=Hash.from_string(bh), instructions=instructions, fee_payer=feepayer)
    if gaslimit is None:
        estimatex = sol_simulateTransaction(endpoint, base58.b58encode(transaction.serialize(verify_signatures=False)).decode())
        gaslimit = int(estimatex["value"]["unitsConsumed"]*gasratio)
    if gaslimit:
        print("gaslimit:", gaslimit)
        instructions.append(set_compute_unit_limit(gaslimit))
    if usev0:
        signargs = [sender]
        # add signer
        if morekeys:
            for i in morekeys:
                if isinstance(i, str):
                    if partialsign:
                        assert needstx, "partialsign tx cannot be broadcasted"
                        i = NullSigner(sol_topubkey(i))
                    else:
                        i = Keypair.from_base58_string(i)
                signargs.append(i)
        try:
            import config
            instructions = config.modify_sol_instructions(instructions, signargs)
            print("instruction modified")
        except:
            traceback.print_exc()
            pass
        msg = MessageV0.try_compile(
            payer=feepayer,
            instructions=instructions,
            address_lookup_table_accounts=[],
            recent_blockhash=Hash.from_string(bh),
        )
        # print(msg)
        transaction = VersionedTransaction(msg, signargs)
        sys.tx = transaction
        stx = base58.b58encode(bytes(transaction)).decode()
    else:
        transaction = Transaction(recent_blockhash=Hash.from_string(bh), instructions=instructions, fee_payer=sender.pubkey())
        signargs = [sender]
        if morekeys:
            for i in morekeys:
                if isinstance(i, str):
                    signargs.append(Keypair.from_base58_string(i))
                else:
                    signargs.append(i)
        sys.tx = transaction
        if partialsign:
            transaction.sign_partial(*signargs)
            assert needstx, "partialsign tx cannot be broadcasted"
            sys.tx = transaction
            return base58.b58encode(transaction.serialize(verify_signatures=False)).decode()
        else:
            transaction.sign(*signargs)
        sys.tx = transaction
        stx = base58.b58encode(transaction.serialize()).decode()
    if needstx:
        return stx
    tx = sol_sendTransaction(endpoint, stx, skipPreflight=skipPreflight)
    return tx

def sol_create_associated_token_account_idempotent(payer, owner, mint):
    from spl.token.instructions import get_associated_token_address, Instruction, AccountMeta, SYS_PROGRAM_ID, TOKEN_PROGRAM_ID, RENT, ASSOCIATED_TOKEN_PROGRAM_ID
    payer, owner, mint = sol_topubkey(payer), sol_topubkey(owner), sol_topubkey(mint)
    associated_token_address = get_associated_token_address(owner, mint)
    return Instruction(
        accounts=[
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
            AccountMeta(pubkey=associated_token_address, is_signer=False, is_writable=True),
            AccountMeta(pubkey=owner, is_signer=False, is_writable=False),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
            AccountMeta(pubkey=RENT, is_signer=False, is_writable=False),
        ],
        program_id=ASSOCIATED_TOKEN_PROGRAM_ID,
        data=b'\x01',
    )

def sol_maketx_splTransfer(endpoint, token, to, value, pk, nonceacc=None, noncevalue=None, needstx=False, memo=None, 
                           gasprice=None, gaslimit=None, skipPreflight=False):
    import base58, solders
    from solders.pubkey import Pubkey
    from spl.token.instructions import TransferParams, transfer
    from spl.token.constants import TOKEN_PROGRAM_ID
    sender = solders.keypair.Keypair.from_base58_string(pk)
    to = sol_topubkey(to)
    token = sol_topubkey(token)
    instructions = []
    fromtokenacc = sol_topubkey(sol_getTokenAccount(token, sender.pubkey()))
    totokenacc = sol_topubkey(sol_getTokenAccount(token, to))
    info = sol_getAccountInfo(endpoint, totokenacc)

    if not info["value"]:
        instructions.append(sol_create_associated_token_account_idempotent(sender.pubkey(), to, token))

    instructions.append(transfer(TransferParams(
        amount=value, 
        dest=totokenacc, 
        owner=sender.pubkey(), 
        program_id=TOKEN_PROGRAM_ID, 
        source=fromtokenacc, 
        signers=[])
    ))

    return sol_maketx(endpoint, instructions, pk, nonceacc=nonceacc, noncevalue=noncevalue, needstx=needstx,
        memo=memo, gasprice=gasprice, gaslimit=gaslimit, skipPreflight=skipPreflight)

def sol_maketx_transfer(endpoint, to, value, pk, nonceacc=None, noncevalue=None, needstx=False, memo=None, gasprice=None, gaslimit=None):
    import base58, solders
    from solders.pubkey import Pubkey
    from solders.system_program import transfer, TransferParams
    sender = solders.keypair.Keypair.from_base58_string(pk)
    to = sol_topubkey(to)
    instruction = transfer(TransferParams(
        from_pubkey=sender.pubkey(), 
        to_pubkey=to, lamports=value
    ))
    
    return sol_maketx(endpoint, instruction, pk, nonceacc=nonceacc, noncevalue=noncevalue, needstx=needstx,
        memo=memo, gasprice=gasprice, gaslimit=gaslimit)

def filecache(prefix, ttl=86400, ignorefirst=True):
    def wrapper(f):
        @wraps(f)
        def real_f(*args):
            if ignorefirst:
                key = ",".join(str(i) for i in args[1:])
            else:
                key = ",".join(str(i) for i in args)
            filename = FOLDER+"/__pycache__/"+prefix+safefilename(key)
            if os.path.isfile(filename) and time.time()-os.path.getmtime(filename)<ttl:
                try:
                    return json.load(open(filename))
                except:
                    print("filecache failed:", filename)
            res = f(*args)
            open(filename, "w").write(json.dumps(res))
            return res
        return real_f
    return wrapper

@filecache("sol_getAddressLookupTable", 86400)
def cached_sol_getAddressLookupTable(endpoint, addr):
    x = sol_getAccountInfo(endpoint, addr)
    return x["value"]["data"]["parsed"]["info"]["addresses"]

sol_WSOL = "So11111111111111111111111111111111111111112"
sol_USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

def sol_getSignaturesForAddress(endpoint, addr, commitment="confirmed", limit=1000, returnraw=False):
    x = simple_rpccall(endpoint, "getSignaturesForAddress", [addr, {"commitment":commitment, "limit":limit}])
    if returnraw:
        return x
    return [i["signature"] for i in x]

def sol_batch_getTransaction(endpoint, hashes, encoding="jsonParsed"):
    data = []
    for h in hashes:
        data.append({"id":len(data), "jsonrpc":"2.0","method":"getTransaction","params":[h, {"encoding":encoding, "maxSupportedTransactionVersion":0}]})
    res = batch_callRPC(data, endpoint=endpoint)
    return [i["result"] for i in res]

def sol_decompile_instructions(endpoint, msg):
    from solders.pubkey import Pubkey
    from solders.instruction import AccountMeta, Instruction
    from solders.message import MessageV0, Message
    account_keys = msg.account_keys
    isv0 = isinstance(msg, MessageV0)
    if isv0:
        for lookup in msg.address_table_lookups:
            l = cached_sol_getAddressLookupTable(endpoint, lookup.account_key)
            account_keys+=[sol_topubkey(l[idx]) for idx in lookup.writable_indexes]
            account_keys+=[sol_topubkey(l[idx]) for idx in lookup.readonly_indexes]
    decompiled_instructions = []
    for compiled_ix in msg.instructions:
        program_id = account_keys[compiled_ix.program_id_index]
        #print(program_id, compiled_ix.accounts)
        account_metas = [
            AccountMeta(
                account_keys[idx],
                is_signer=msg.is_signer(idx),
                is_writable=getattr(msg, "is_maybe_writable" if isv0 else "is_writable")(idx),
            )
            for idx in compiled_ix.accounts
        ]
        decompiled_instructions.append(Instruction(program_id, compiled_ix.data, account_metas))
    return decompiled_instructions


ZERO_ADDRESS="0x0000000000000000000000000000000000000000"

def dprint(*args, **kwargs):
    if os.getenv("DEBUG", False):
        myprint(*args, **kwargs)

def eth_getProof(rpc, addr, slots=None, height="latest"):
    if not slots:
        slots = []
    slots = [toh(i) for i in slots]
    return simple_rpccall(rpc, "eth_getProof", [addr, slots, toh(height)])


ZEROADDR = "0x0000000000000000000000000000000000000000"

from datetime import datetime, timezone, timedelta

def time2human(timestamp, tz=8):
    tz = timezone(timedelta(hours=tz))
    dt = datetime.fromtimestamp(timestamp, tz=tz)
    return dt.strftime('%Y/%m/%d %H:%M:%S')

def x402_create_header(chainid, pk, payto, payamount, validwindow=60, returnpayload=False, rpc=None, feepayer=None, gaslimit=200_000, gasprice=100_000):
    import secrets
    x402conf = {
        84532: ["base-sepolia","0x036CbD53842c5426634e7929541eC2318f3dCF7e","2","USDC"],
        8453: ["base", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "2", "USD Coin"],
        "solana": ["EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",6],
        "solana-devnet":["4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",6],
    }
    if chainid in ["solana-devnet","solana"]:
        assert rpc is not None and feepayer is not None
        CHAINNAME = chainid
        USDC, decimals = x402conf[chainid]
        stx = sol_x402tx(rpc, USDC, pk, payto, payamount, feepayer, gaslimit=gaslimit, gasprice=gasprice, tokendecimals=decimals)
        payload_in = {
            "transaction": stx
        }
    else:
        if chainid in x402conf:
            CHAINNAME, USDC, USDC_version, USDC_name = x402conf[chainid]
        else:
            chainid, CHAINNAME, USDC, USDC_version, USDC_name = chainid
        ts = int(time.time())
        nonce_bytes = secrets.token_bytes(32)
        if isinstance(pk, dict):
            sendfrom = pk["from"]
        else:
            sendfrom = topub(pk)
        typed_data = {
            "types": {
                "TransferWithAuthorization": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                    {"name": "nonce", "type": "bytes32"},
                ]
            },
            "primaryType": "TransferWithAuthorization",
            "domain": {
                "name": USDC_name,
                "version": USDC_version,
                "chainId": chainid,
                "verifyingContract": USDC,
            },
            "message": {
                "from": sendfrom,
                "to": payto,
                "value": payamount,
                "validAfter": ts-validwindow,
                "validBefore": ts+validwindow,
                "nonce": nonce_bytes,
            },
        }
        if isinstance(pk, dict):
            sig = pk["sign"](typed_data)
        else:
            sig = sign_eip712(typed_data, pk)
        payload_in = {
            "signature":sig,
            "authorization":{
                "from":sendfrom,
                "to":payto,
                "value":str(payamount),
                "validAfter":str(ts-validwindow),
                "validBefore":str(ts+validwindow),
                "nonce":b16e(nonce_bytes)
            }
        }
    payload = {
        "x402Version":1,
        "scheme":"exact",
        "network":CHAINNAME,
        "payload":payload_in
    }
    if returnpayload:
        return USDC, payload
    paymentheader = urlsafe_b64encode(json.dumps(payload).encode("ascii")).decode()
    return paymentheader

def x402_transfer_usdc(facilitator, chainid, pk, payto, payamount, validwindow=60, resource_url='http://127.0.0.1', 
                       headers=None, returnx=False, action="settle", rpc=None, feepayer=None, gaslimit=200_000, gasprice=100_000):
    assert action in ["verify", "settle"]
    if not headers:
        headers = {}
    if facilitator=="coinbase":
        from config import CDP_API_KEY_ID, CDP_API_KEY_SECRET
        from cdp.x402 import create_facilitator_config
        import asyncio
        facilitator_config = create_facilitator_config(
            api_key_id=CDP_API_KEY_ID,
            api_key_secret=CDP_API_KEY_SECRET,
        )
        headers.update(asyncio.run(facilitator_config["create_headers"]())[action])
        url = facilitator_config["url"]+"/"+action
    else:
        url = facilitator
        if not url.endswith("/"+action):
            if url[-1]!="/":
                url += "/"
            url += action
    asset, payload = x402_create_header(chainid, pk, payto, payamount, validwindow=validwindow, 
                                        returnpayload=True, rpc=rpc, feepayer=feepayer, gaslimit=gaslimit, gasprice=gasprice)
    data={
        'x402Version': 1, 
        'paymentPayload': payload, 
        'paymentRequirements': {
            'scheme': 'exact', 
            'network': payload['network'], 
            'maxAmountRequired': str(payamount), 
            'resource': resource_url, 
            'description': '', 
            'mimeType': '', 
            'outputSchema': {
                'input': {'type': 'http', 'method': 'GET', 'discoverable': False}, 
                'output': None
            }, 
            'payTo': payto, 
            'maxTimeoutSeconds': 60, 
            'asset': asset, 
        }
    }
    x402conf = {
        84532: ["base-sepolia","0x036CbD53842c5426634e7929541eC2318f3dCF7e","2","USDC"],
        8453: ["base", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "2", "USD Coin"],
    }
    if chainid in x402conf:
        data["paymentRequirements"]["extra"] = {
            "name": x402conf[chainid][3],
            "version": x402conf[chainid][2],
        }
    print("verify request:")
    print(headers)
    print(data)
    x = sess.post(url, json=data, headers=headers)
    sys.x = x
    if returnx:
        return x
    # return x.json() #{'success': True, 'transaction': '0x...', 'network': 'base', 'payer': '0x...'}
    try:
        return x.json()
    except Exception as e:
        print("=== x402_transfer_usdc: response is not valid JSON ===")
        print("url:", x.url)
        print("status_code:", x.status_code)
        print("headers:", dict(x.headers))
        body = (x.text or "")
        print("body_len:", len(body))
        print("body_preview:", body[:2000])  # AVOID TOO LONG
        # check original bytes
        rb = getattr(x, "content", b"") or b""
        print("raw_bytes_len:", len(rb))
        print("raw_bytes_preview:", rb[:200])
        print("=== JSON decode error ===", repr(e))
        raise

def sol_x402tx(endpoint, USDC, pk, payto, payamount, feepayer, createata=False, gaslimit=200_000, gasprice=100_000, tokendecimals=6):
    from solders.keypair import Keypair
    from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
    from spl.token.instructions import TransferCheckedParams, transfer_checked
    from spl.token.constants import TOKEN_PROGRAM_ID
    import base58
    sender = Keypair.from_base58_string(pk)
    MYADDR = sol_topub(pk)
    # get client's ATA
    fromtokenacc = sol_topubkey(sol_getTokenAccount(USDC,MYADDR))
    # get server's ATA
    totokenacc = sol_topubkey(sol_getTokenAccount(USDC,payto))
    # construct instructions
    instructions = [
        # Solana compute budget; compute unit limit
        set_compute_unit_limit(gaslimit),
        # compute unit price
        set_compute_unit_price(gasprice),
        # SPL token; transfer_checked
        transfer_checked(TransferCheckedParams(
            amount=payamount, 
            dest=totokenacc, 
            owner=sender.pubkey(), 
            program_id=TOKEN_PROGRAM_ID, # SPL Token program
            source=fromtokenacc, 
            mint=sol_topubkey(USDC), # token mint（USDC mint）
            decimals=tokendecimals,  # mint decimals
            signers=[])
        )
    ]
    # if server doesn't have ATA so need to inject the ata creat instruction
    if createata:
        instructions.insert(2, sol_create_associated_token_account_idempotent(MYADDR, payto, USDC))
    
    # optional: add signers, which increases base fee and tx
    ks = []
    if os.getenv("X402_ADDEXTRASIGS", None):
        for i in range(int(os.environ["X402_ADDEXTRASIGS"])):
            ks.append(Keypair())
        def modify_sol_instructions(instructions, signargs):
            from spl.token.instructions import Instruction,AccountMeta
            instructions[0] = Instruction(accounts=[
                AccountMeta(
                    pubkey=i.pubkey(),
                    is_signer=True,
                    is_writable=False
                ) for i in ks
            ], data=instructions[0].data, program_id=instructions[0].program_id)
            return instructions
        import config
        # add hook to config
        config.modify_sol_instructions = modify_sol_instructions
    # construct the tx; 
    # - needstx=True: means return the transactions
    # - morekeys=[feepayer]+ks, add a signer and other signers
    # - partialsign=True:
    # - feepayer=feepayer should be facilitator
    stx = sol_maketx(endpoint, instructions, pk, needstx=True, morekeys=[feepayer]+ks,partialsign=True,usev0=True,feepayer=feepayer,gasprice=0,gaslimit=0,)
    return b64encode(base58.b58decode(stx)).decode()

