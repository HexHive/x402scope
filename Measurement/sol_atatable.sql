create table solanatxs_ata select txhash,blocktime,payer,x402_from from solanatxs where ok=1 and tx_category in ('x402_token_ata','x402_token2022_ata');
ALTER TABLE solanatxs_ata
    ADD COLUMN ata_payer varchar(255) DEFAULT NULL AFTER x402_from,
    ADD COLUMN ata_account varchar(255) DEFAULT NULL AFTER ata_payer,
    ADD COLUMN ata_owner varchar(255) DEFAULT NULL AFTER ata_account,
    ADD COLUMN signer_length tinyint(4) DEFAULT NULL AFTER ata_owner,
    ADD PRIMARY KEY (txhash, blocktime),
    ADD KEY ata_payer (ata_payer),
    ADD KEY signer_length (signer_length);

create table solanatxs_failed select * from solanatxs where `blocktime`<=1766789345 and ok=0;