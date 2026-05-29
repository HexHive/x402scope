import sys,os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "SecurityViolation")))
from simplebase import *
from runsql import runsql
from tqdm import tqdm

RPC2Referer = {}
def GET_EXTRA_HEADERS(endpoint):
    if endpoint not in RPC2Referer:
        return {}
    return {"Referer": RPC2Referer[endpoint], "Origin": RPC2Referer[endpoint]}
config.GET_EXTRA_HEADERS = GET_EXTRA_HEADERS

pBase = Endpoint_Provider([config.RPC_BASE])

def getp(chainid):
    assert chainid==8453
    return pBase