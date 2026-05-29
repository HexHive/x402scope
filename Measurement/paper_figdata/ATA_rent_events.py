import pandas as pd
from runsql import runsql
from solders.signature import Signature

ATA_TABLE = "solanatxs_ata"

SIGNER_LENGTH_FILTER = 2

PRINT_SAMPLES = True
SAMPLE_LIMIT = 20

OUT_SUMMARY = "ata_rentpayer_summary.csv"
OUT_FAC_BREAKDOWN = "ata_rentpayer_by_facilitator.csv"
OUT_PAYER_TOP = "ata_rentpayer_top_payers.csv"

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

def build_eoa_to_fac(solEOAs: dict) -> dict:
    m = {}
    for fac, addrs in solEOAs.items():
        for a in addrs:
            m[a] = fac
    return m

def to_sig(txhash):
    """binary txhash -> base58 signature string"""
    if isinstance(txhash, (bytes, bytearray)):
        return str(Signature.from_bytes(txhash))
    return str(txhash)

def main():
    eoa2fac = build_eoa_to_fac(solEOAs)
    facilitator_eoas = set(eoa2fac.keys())

    rows = runsql(f"""
        SELECT
            txhash,
            blocktime,
            payer,
            x402_from,
            ata_payer,
            ata_owner,
            ata_account,
            signer_length
        FROM {ATA_TABLE}
        WHERE signer_length = {SIGNER_LENGTH_FILTER}
    """)

    df = pd.DataFrame(rows, columns=[
        "txhash","blocktime","payer","x402_from","ata_payer","ata_owner","ata_account","signer_length"
    ])


    df["payer_is_facilitator"] = df["ata_payer"].isin(facilitator_eoas)
    df["facilitator"] = df["ata_payer"].map(eoa2fac).fillna("other")

    total_rent_events = int(len(df))
    fac_paid_events = int(df["payer_is_facilitator"].sum())
    other_paid_events = total_rent_events - fac_paid_events

    fac_paid_share = (fac_paid_events / total_rent_events) if total_rent_events else 0.0

    fac_breakdown = (df[df["payer_is_facilitator"]]
                     .groupby("facilitator")
                     .size()
                     .reset_index(name="rent_event_cnt")
                     .sort_values("rent_event_cnt", ascending=False))
    fac_breakdown.to_csv(OUT_FAC_BREAKDOWN, index=False)
    print(f"Saved: {OUT_FAC_BREAKDOWN}")

    payer_top = (df.groupby("ata_payer")
                 .size()
                 .reset_index(name="rent_event_cnt")
                 .sort_values("rent_event_cnt", ascending=False))
    payer_top["facilitator"] = payer_top["ata_payer"].map(eoa2fac).fillna("other")
    payer_top.to_csv(OUT_PAYER_TOP, index=False)
    print(f"Saved: {OUT_PAYER_TOP}")

    summary = pd.DataFrame([{
        "signer_length_filter": SIGNER_LENGTH_FILTER,
        "total_rent_events": total_rent_events,
        "facilitator_paid_events": fac_paid_events,
        "other_paid_events": other_paid_events,
        "facilitator_paid_share": fac_paid_share,
        "unique_ata_payers": int(df["ata_payer"].nunique()),
        "unique_facilitator_payers": int(df.loc[df["payer_is_facilitator"], "ata_payer"].nunique()),
        "unique_facilitators": int(fac_breakdown["facilitator"].nunique()),
    }])
    summary.to_csv(OUT_SUMMARY, index=False)
    print(f"Saved: {OUT_SUMMARY}\n")
    print(summary)

    if PRINT_SAMPLES:
        print("\n=== Sample ATA rent events (first few rows) ===")
        sample = df.sort_values("blocktime", ascending=True).head(SAMPLE_LIMIT)
        for _, r in sample.iterrows():
            sig = to_sig(r["txhash"])
            print("blocktime:", int(r["blocktime"]))
            print("ata_payer:", r["ata_payer"], "| facilitator:", r["facilitator"])
            print("ata_owner:", r["ata_owner"])
            print("ata_account:", r["ata_account"])
            print("txhash(signature):", sig)
            print("explorer:", f"https://explorer.solana.com/tx/{sig}")
            print("-" * 60)

    print("\n=== Key stats ===")
    print(f"Total ATA rent events (proxy): {total_rent_events}")
    print(f"Facilitator-paid events:       {fac_paid_events} ({fac_paid_share*100:.2f}%)")
    print(f"Non-facilitator-paid events:   {other_paid_events}")

if __name__ == "__main__":
    main()
