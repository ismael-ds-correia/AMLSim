"""
Transforma dados do AMLSim em CSV de transações.
Produz colunas:
 - VALOR_TRANSACAO (base_amt)
 - I-d (1 se FRAGMENTED_DEPOSIT, 0 caso contrário; 0 para cash-in/cash-out)
 - I-e (1 se FRAGMENTED_WITHDRAWAL, 0 caso contrário; 0 para cash-in/cash-out)
 - CNAB: 220 para CASH-IN, 123 para CASH-OUT
 - NATUREZA_LANCAMENTO: C para CASH-IN, D para CASH-OUT
 - NOME_BANCO, NUMERO_CONTA, CPF_CNPJ_TITULAR, NOME_TITULAR,
   NUMERO_CONTA_OD, CPF_CNPJ_OD, NOME_PESSOA_OD
"""

import os
import sys
from io import StringIO
import argparse
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def get_natureza_lancamento(tx_type):
    tx_type = str(tx_type).upper()
    if tx_type in ("CASH-DEPOSIT", "CHECK-DEPOSIT", "FRAGMENTED_DEPOSIT", "CASH-IN"):
        return "C"
    elif tx_type in ("FRAGMENTED_WITHDRAWAL", "CASH-OUT"):
        return "D"
    elif tx_type in ("TRANSFER", "PAYMENT", "DEBIT"):
        return "D"
    else:
        return ""

def load_csv_skip_comments(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding) as f:
        lines = f.readlines()
    filtered = [ln for ln in lines if not ln.strip().startswith("//") and ln.strip() != ""]
    txt = "".join(filtered)
    return pd.read_csv(StringIO(txt))

def safe_str(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s == "-" or s.lower() == "nan":
        return ""
    return s

def build_lookup_tables(accounts_df=None, alert_accounts_df=None):
    accounts_lookup = {}
    alert_acct_lookup = {}

    if accounts_df is not None:
        df = accounts_df.copy()
        if "acct_id" not in df.columns:
            raise RuntimeError("accounts.csv não contém a coluna 'acct_id'")
        df["acct_id_str"] = df["acct_id"].astype(str)
        df.set_index("acct_id_str", inplace=True, drop=False)
        accounts_lookup = df.to_dict(orient="index")

    if alert_accounts_df is not None:
        df2 = alert_accounts_df.copy()
        if "acct_id" in df2.columns:
            df2["acct_id_str"] = df2["acct_id"].astype(str)
            df2.set_index("acct_id_str", inplace=True, drop=False)
            alert_acct_lookup = df2.to_dict(orient="index")

    return accounts_lookup, alert_acct_lookup

def enrich_account_info(acct_key, accounts_lookup, alert_acct_lookup):
    if not acct_key:
        return None
    if acct_key in accounts_lookup:
        return accounts_lookup[acct_key]
    if acct_key in alert_acct_lookup:
        return alert_acct_lookup[acct_key]
    return None

def format_base_amt(val):
    if pd.isna(val) or safe_str(val) == "":
        return ""
    try:
        return float(val)
    except Exception:
        return safe_str(val)

def build_transaction_rows(alert_tx_df, cash_tx, accounts_lookup, alert_acct_lookup):
    rows = []
    # Processa transações normais
    for _, tx in alert_tx_df.iterrows():
        orig_acct_raw = tx.get("orig_acct", "")
        bene_acct_raw = tx.get("bene_acct", "")

        orig_acct = safe_str(orig_acct_raw)
        bene_acct = safe_str(bene_acct_raw)

        nome_banco = ""
        numero_conta = ""
        cpf_cnpj_titular = ""
        nome_titular = ""

        numero_conta_od = ""
        cpf_cnpj_od = ""
        nome_pessoa_od = ""

        if bene_acct:
            acct_info = enrich_account_info(bene_acct, accounts_lookup, alert_acct_lookup)
            numero_conta_od = bene_acct
            if acct_info:
                cpf_cnpj_od = safe_str(acct_info.get("ssn", ""))
                fn = safe_str(acct_info.get("first_name", ""))
                ln = safe_str(acct_info.get("last_name", ""))
                if not (fn or ln):
                    acct_name = safe_str(acct_info.get("acct_name", ""))
                    nome_pessoa_od = acct_name if acct_name else ""
                else:
                    nome_pessoa_od = (fn + " " + ln).strip()

        base_amt = tx.get("base_amt", "")
        tx_type = safe_str(tx.get("tx_type", "")).upper()

        if tx_type == "FRAGMENTED_DEPOSIT":
            numero_conta = bene_acct
        elif orig_acct:
            numero_conta = orig_acct
        elif bene_acct:
            numero_conta = bene_acct
            
        valor_transacao = format_base_amt(base_amt)
        i_d = 1 if tx_type in ("CASH-DEPOSIT", "CHECK-DEPOSIT", "FRAGMENTED_DEPOSIT") else 0
        i_e = 1 if tx_type in ("FRAGMENTED_WITHDRAWAL",) else 0

        data_lancamento = safe_str(tx.get("tran_timestamp", ""))

        if tx_type == "CHECK-DEPOSIT":
            cnab = "201"
        elif tx_type == "CASH-DEPOSIT":
            cnab = "220"
        elif tx_type == "FRAGMENTED_WITHDRAWAL":
            cnab = "114"
        elif tx_type == "FRAGMENTED_DEPOSIT":
            cnab = "220"
        elif tx_type == "TRANSFER":
            cnab = "117"
        else:
            cnab = ""

        valor_saldo = tx.get("newbalanceDest", "")
        if pd.isna(valor_saldo) or safe_str(valor_saldo) == "":
            valor_saldo = tx.get("newbalanceOrig", "")

        natureza_lancamento = get_natureza_lancamento(tx_type)

        rows.append({
            "VALOR_TRANSACAO": valor_transacao,
            "CNAB": cnab,
            "I-d": i_d,
            "I-e": i_e,
            "DATA_LANCAMENTO": data_lancamento,
            "NOME_BANCO": nome_banco,
            "NUMERO_CONTA": numero_conta,
            "CPF_CNPJ_TITULAR": cpf_cnpj_titular,
            "NOME_TITULAR": nome_titular,
            "NUMERO_CONTA_OD": numero_conta_od,
            "CPF_CNPJ_OD": cpf_cnpj_od,
            "NOME_PESSOA_OD": nome_pessoa_od,
            "VALOR_SALDO": valor_saldo,
            "NATUREZA_LANCAMENTO": natureza_lancamento
        })

    # Processa cash_tx
    for _, tx in cash_tx.iterrows():
        orig_acct = safe_str(tx.get("orig_acct", ""))
        bene_acct = safe_str(tx.get("bene_acct", ""))

        nome_banco = ""
        numero_conta = ""
        cpf_cnpj_titular = ""
        nome_titular = ""

        numero_conta_od = ""
        cpf_cnpj_od = ""
        nome_pessoa_od = ""

        if orig_acct:
            acct_info = enrich_account_info(orig_acct, accounts_lookup, alert_acct_lookup)
            numero_conta = orig_acct
            if acct_info:
                nome_banco = safe_str(acct_info.get("bank_id", acct_info.get("bank", "")))
                cpf_cnpj_titular = safe_str(acct_info.get("ssn", ""))
                fn = safe_str(acct_info.get("first_name", ""))
                ln = safe_str(acct_info.get("last_name", ""))
                if not (fn or ln):
                    acct_name = safe_str(acct_info.get("acct_name", ""))
                    nome_titular = acct_name if acct_name else ""
                else:
                    nome_titular = (fn + " " + ln).strip()

        if bene_acct:
            acct_info = enrich_account_info(bene_acct, accounts_lookup, alert_acct_lookup)
            numero_conta_od = bene_acct
            if acct_info:
                cpf_cnpj_od = safe_str(acct_info.get("ssn", ""))
                fn = safe_str(acct_info.get("first_name", ""))
                ln = safe_str(acct_info.get("last_name", ""))
                if not (fn or ln):
                    acct_name = safe_str(acct_info.get("acct_name", ""))
                    nome_pessoa_od = acct_name if acct_name else ""
                else:
                    nome_pessoa_od = (fn + " " + ln).strip()

        base_amt = tx.get("base_amt", "")
        tx_type = safe_str(tx.get("tx_type", "")).upper()

        if tx_type == "CASH-OUT":
            numero_conta = bene_acct
            cpf_cnpj_titular = cpf_cnpj_od
            nome_titular = nome_pessoa_od
            # Campos OD ficam vazios
            numero_conta_od = ""
            cpf_cnpj_od = ""
            nome_pessoa_od = ""
        else:
            if orig_acct:
                numero_conta = orig_acct
            elif bene_acct:
                numero_conta = bene_acct
            else:
                numero_conta = ""

        valor_transacao = format_base_amt(base_amt)
        i_d = 0
        i_e = 0

        data_lancamento = safe_str(tx.get("tran_timestamp", ""))

        if tx_type == "CASH-IN":
            cnab = "220"
            natureza_lancamento = "C"
        elif tx_type == "CASH-OUT":
            cnab = "123"
            natureza_lancamento = "D"
        elif tx_type == "TRANSFER":
            cnab = "117"
        else:
            cnab = ""
            natureza_lancamento = ""

        valor_saldo = tx.get("newbalanceDest", "")
        if pd.isna(valor_saldo) or safe_str(valor_saldo) == "":
            valor_saldo = tx.get("newbalanceOrig", "")

        rows.append({
            "VALOR_TRANSACAO": valor_transacao,
            "CNAB": cnab,
            "I-d": i_d,
            "I-e": i_e,
            "DATA_LANCAMENTO": data_lancamento,
            "NOME_BANCO": nome_banco,
            "NUMERO_CONTA": numero_conta,
            "CPF_CNPJ_TITULAR": cpf_cnpj_titular,
            "NOME_TITULAR": nome_titular,
            "NUMERO_CONTA_OD": numero_conta_od,
            "CPF_CNPJ_OD": cpf_cnpj_od,
            "NOME_PESSOA_OD": nome_pessoa_od,
            "VALOR_SALDO": valor_saldo,
            "NATUREZA_LANCAMENTO": natureza_lancamento
        })

    cols = [
        "VALOR_TRANSACAO",
        "CNAB",
        "I-d",
        "I-e",
        "DATA_LANCAMENTO",
        "NOME_BANCO",
        "NUMERO_CONTA",
        "CPF_CNPJ_TITULAR",
        "NOME_TITULAR",
        "NUMERO_CONTA_OD",
        "CPF_CNPJ_OD",
        "NOME_PESSOA_OD",
        "VALOR_SALDO",
        "NATUREZA_LANCAMENTO"
    ]
    return pd.DataFrame(rows, columns=cols)

def main():
    parser = argparse.ArgumentParser(description="Transforma dados do AMLSim em CSV de transações.")
    parser.add_argument(
        "-d", "--data-dir",
        help="Pasta contendo alert_transactions.csv, accounts.csv, cash_tx.csv (padrão: %(default)s)"
    )
    parser.add_argument(
        "-o", "--out",
        default=None,
        help="Arquivo de saída CSV (padrão: <data-dir>/transactions_output.csv)"
    )
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        logging.error("Diretório de dados não encontrado: %s", data_dir)
        sys.exit(1)

    alert_tx_file = os.path.join(data_dir, "transactions.csv")
    cash_tx_file = os.path.join(data_dir, "cash_tx.csv")
    accounts_file = os.path.join(data_dir, "accounts.csv")
    alert_accounts_file = os.path.join(data_dir, "alert_accounts.csv")
    out_file = args.out if args.out else os.path.join(data_dir, "transactions_output.csv")

    if not os.path.isfile(alert_tx_file):
        logging.error("Arquivo obrigatório não encontrado: %s", alert_tx_file)
        sys.exit(1)
    if not os.path.isfile(accounts_file):
        logging.error("Arquivo obrigatório não encontrado: %s", accounts_file)
        sys.exit(1)

    logging.info("Lendo alert_transactions de: %s", alert_tx_file)
    alert_tx_df = load_csv_skip_comments(alert_tx_file)

    if not os.path.isfile(cash_tx_file):
        logging.warning("Arquivo cash_tx.csv não encontrado: %s", cash_tx_file)
        cash_tx = pd.DataFrame()
    else:
        logging.info("Lendo cash_tx de: %s", cash_tx_file)
        cash_tx = load_csv_skip_comments(cash_tx_file)

    logging.info("Lendo accounts de: %s", accounts_file)
    accounts_df = load_csv_skip_comments(accounts_file)

    alert_accounts_df = None
    if os.path.isfile(alert_accounts_file):
        logging.info("Lendo alert_accounts (opcional) de: %s", alert_accounts_file)
        try:
            alert_accounts_df = load_csv_skip_comments(alert_accounts_file)
        except Exception as e:
            logging.warning("Falha ao ler alert_accounts.csv: %s. Ignorando arquivo.", e)
            alert_accounts_df = None
    else:
        logging.info("alert_accounts.csv não encontrado; continuando sem ele.")

    accounts_lookup, alert_acct_lookup = build_lookup_tables(accounts_df=accounts_df, alert_accounts_df=alert_accounts_df)

    missing_cols = [c for c in ("orig_acct", "bene_acct", "base_amt", "tx_type") if c not in alert_tx_df.columns]
    if missing_cols:
        raise RuntimeError(f"Colunas necessárias ausentes em transactions.csv: {missing_cols}")

    logging.info("Construindo linhas de saída...")
    out_df = build_transaction_rows(alert_tx_df, cash_tx, accounts_lookup, alert_acct_lookup)

    logging.info("Gravando arquivo de saída: %s", out_file)
    out_df.to_csv(out_file, index=False, encoding="utf-8")
    logging.info("Concluído. Arquivo gerado em: %s", out_file)

if __name__ == "__main__":
    main()