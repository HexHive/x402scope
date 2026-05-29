import pymysql, threading, warnings
from config import *
thread_data = threading.local()

def db():
    global thread_data
    conn = pymysql.connect(user=MYSQL_USER,passwd=MYSQL_PASSWORD,host=MYSQL_HOST,port=MYSQL_PORT,
        db=MYSQL_DB ,charset='utf8',init_command="set NAMES utf8mb4", use_unicode=True)
    thread_data.__dict__["conn"] = conn
    return conn

def runsql(sql, *args, onerror='raise', returnid=False, allow_retry=True, returnrows=False):
    global thread_data
    conn = thread_data.__dict__.get("conn")
    if len(args)==1 and isinstance(args[0], list):
        args = args[0]
    if sql.endswith(","):
        sql = sql[:-1]
    if not conn:
        conn = db()
    if not conn.open:
        conn = db()
    cur = conn.cursor()
    try:
        conn.ping()
    except:
        print("conn.ping() failed, reconnect")
        conn = db()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rows = cur.execute(sql, args)
    except pymysql.err.OperationalError as e:
        conn.commit()
        cur.close()
        if allow_retry and ("Lost connection to MySQL" in str(e) or "MySQL server has gone away" in str(e)):
            conn.close()
            conn = db()
            return runsql(sql, *args, onerror=onerror, returnid=returnid, allow_retry=False)
        else:
            raise
    except:
        conn.commit()
        cur.close()
        if onerror=="ignore":
            return False
        else:
            raise
    if not returnrows:
        if returnid:
            cur.execute("SELECT LAST_INSERT_ID();")
            result = list(cur)[0][0]
        else:
            result = list(cur)
    conn.commit()
    cur.close()
    if returnrows:
        return rows
    else:
        return result