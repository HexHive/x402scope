

import pandas as pd
import matplotlib.pyplot as plt
from runsql import runsql

ATA_TABLE = "solanatxs_ata"
SOL_TABLE = "solanatxs"
SOL_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
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
TOPK_PAYER = 10
TOPK_OWNER = 20

def build_eoa_to_facilitator_map(solEOAs: dict) -> dict:
    m = {}
    for fac, addrs in solEOAs.items():
        for a in addrs:
            m[a] = fac
    return m

def main():
    eoa2fac = build_eoa_to_facilitator_map(solEOAs)

    rows = runsql(f"""
      SELECT
        a.blocktime,
        a.payer,
        a.x402_from,
        a.ata_payer,
        a.ata_owner,
        a.ata_account,
        s.ok,
        s.fee,
        s.x402_token,
        s.x402_amount
      FROM {ATA_TABLE} a
      LEFT JOIN {SOL_TABLE} s
        ON a.txhash = s.txhash AND a.blocktime = s.blocktime
      WHERE a.signer_length = 2
    """)
    df = pd.DataFrame(rows, columns=[
        "blocktime","payer","x402_from","ata_payer","ata_owner","ata_account",
        "ok","fee","x402_token","x402_amount"
    ])

    df_all = df.copy()

    # Total counts
    total_ata_all = int(runsql(f"SELECT COUNT(*) FROM {ATA_TABLE};")[0][0] or 0)
    total_ata = int(len(df_all))


    # Who paid ATA creation cost proxy: ata_payer
    paid_by_client = int((df_all["ata_payer"] == df_all["x402_from"]).sum())
    paid_by_txpayer = int((df_all["ata_payer"] == df_all["payer"]).sum())
    paid_by_other = int(total_ata - paid_by_client - paid_by_txpayer)

    # 2) Owner counts
    owner_counts = (df_all.groupby("ata_owner")
                    .size()
                    .reset_index(name="tx_cnt")
                    .sort_values("tx_cnt", ascending=False))
    owner_counts.to_csv("ata_owner_counts.csv", index=False)
    print("Saved: ata_owner_counts.csv")

    unique_owners = int(owner_counts.shape[0])
    repeated_owner_tx = int(owner_counts.loc[owner_counts["tx_cnt"] > 1, "tx_cnt"].sum())
    repeated_owner_rate = (repeated_owner_tx / total_ata) if total_ata else 0.0

    # top owners
    top_owner_df = owner_counts.head(TOPK_OWNER).copy()
    top_owner_df.to_csv(f"ata_owner_counts_top{TOPK_OWNER}.csv", index=False)
    print(f"Saved: ata_owner_counts_top{TOPK_OWNER}.csv")

    

if __name__ == "__main__":
    main()