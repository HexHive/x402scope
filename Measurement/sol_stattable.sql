create table solview39_bypayer select payer,ok,tx_category,count(*) as cnt,sum(fee) as sum_fee from solanatxs where `blocktime`<=1766789345 group by payer,ok,tx_category;

create table solview39_byx402_to select x402_to,x402_token,payer,count(*) as cnt,sum(fee) as sum_fee,sum(x402_amount) as sum_x402_amount from solanatxs where `blocktime`<=1766789345 and ok=1 and tx_category in ('x402_token','x402_token_ata','x402_token2022','x402_token2022_ata') group by x402_to,x402_token,payer;

create table solview39_byday select (`blocktime` DIV 86400) as day,x402_token,count(*) as cnt,sum(fee) as sum_fee,sum(x402_amount) as sum_x402_amount from solanatxs where `blocktime`<=1766789345 and ok=1 and tx_category in ('x402_token','x402_token_ata','x402_token2022','x402_token2022_ata')  group by day,x402_token;

create table solview39_byday_payer select (`blocktime` DIV 86400) as day,x402_token,payer,count(*) as cnt,sum(fee) as sum_fee,sum(x402_amount) as sum_x402_amount from solanatxs where `blocktime`<=1766789345 and ok=1 and tx_category in ('x402_token','x402_token_ata','x402_token2022','x402_token2022_ata')  group by day,x402_token,payer;

create table solview39_byday_x402_to select (`blocktime` DIV 86400) as day,x402_token,x402_to,count(*) as cnt,sum(fee) as sum_fee,sum(x402_amount) as sum_x402_amount from solanatxs where `blocktime`<=1766789345 and ok=1 and tx_category in ('x402_token','x402_token_ata','x402_token2022','x402_token2022_ata')  group by day,x402_token,x402_to;

