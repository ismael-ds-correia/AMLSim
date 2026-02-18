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
import numpy as np

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

        titular_acct = orig_acct if orig_acct else bene_acct
        acct_info = enrich_account_info(titular_acct, accounts_lookup, alert_acct_lookup)
        if acct_info:
            cpf_cnpj_titular = safe_str(acct_info.get("ssn", ""))
            fn = safe_str(acct_info.get("first_name", ""))
            ln = safe_str(acct_info.get("last_name", ""))
            if not (fn or ln):
                acct_name = safe_str(acct_info.get("acct_name", ""))
                nome_titular = acct_name if acct_name else ""
            else:
                nome_titular = (fn + " " + ln).strip()

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

def assign_ramo_atividade_empirical(
    df,
    n_ramos=7,
    v=0.7,
    a=1.0,
    b=2.0,
    q0=None,
    q1_d=None,
    q1_e=None,
    seed=42
):
    """
    Atribui um ramo_atividade para cada conta, com viés diferente para I-d e I-e.
    Parâmetros:
        df: DataFrame de transações (já com I-d e I-e)
        n_ramos: número de ramos possíveis (ex: 7)
        v: intensidade do viés [0,1]
        a, b: smoothing para tilde_p
        q0: distribuição base
        q1_d: distribuição fraude para I-d
        q1_e: distribuição fraude para I-e
        seed: semente para reprodutibilidade
    Retorna:
        dict: {conta: ramo_atividade}
    """
    rng = np.random.default_rng(seed)

    q0 = np.array(q0, dtype=float)
    q0 = q0 / q0.sum()
    q1_d = np.array(q1_d, dtype=float)
    q1_d = q1_d / q1_d.sum()
    q1_e = np.array(q1_e, dtype=float)
    q1_e = q1_e / q1_e.sum()

    df = df.copy()
    df["_y_d"] = (df["I-d"] == 1).astype(int)
    df["_y_e"] = (df["I-e"] == 1).astype(int)

    conta2tx = df.groupby("NUMERO_CONTA")[["_y_d", "_y_e"]].agg(["sum", "count"])
    conta2ramo = {}
    for conta, row in conta2tx.iterrows():
        F_d = row[("_y_d", "sum")]
        F_e = row[("_y_e", "sum")]
        N = row[("_y_d", "count")]

        tilde_p_d = (F_d + a) / (N + b)
        tilde_p_e = (F_e + a) / (N + b)

        if tilde_p_d > tilde_p_e:
            w = v * tilde_p_d
            q1 = q1_d
        elif tilde_p_e > tilde_p_d:
            w = v * tilde_p_e
            q1 = q1_e
        else:
            w = v * tilde_p_d
            q1 = 0.5 * (q1_d + q1_e)

        P = (1 - w) * q0 + w * q1
        P = np.clip(P, 0, None)
        sumP = P.sum()
        if sumP == 0:
            P = q0.copy()
        else:
            P = P / sumP

        ramo = rng.choice(np.arange(1, n_ramos+1), p=P)
        conta2ramo[conta] = ramo

    return conta2ramo

def assign_ramo_atividade_targets(
    df,
    n_ramos=7,
    target_norm=None,
    target_d=None,
    target_e=None,
    a=1.0,
    b=2.0,
    seed=42,
    p_fixed_norm=None,
    p_fixed_d=None,
    p_fixed_e=None,
    return_df=False
):
    """
    Atribui ramo_atividade por conta, misturando uniforme e concentração em ramos-alvo.
    Parâmetros:
        df: DataFrame de transações (com colunas NUMERO_CONTA, I-d, I-e)
        n_ramos: número de ramos possíveis (N)
        target_norm, target_d, target_e: listas de ramos-alvo (valores 1..N) para cada tipo
        a, b: smoothing para tilde_p
        seed: semente RNG
        p_fixed_norm/e/d: valor fixo para p_t do tipo correspondente (obrigatório)
        return_df: se True, retorna também df com coluna 'ramo_atividade'
    Retorna:
        conta2ramo: dict {NUMERO_CONTA -> ramo_atividade (1..N)}
        (opcional) df atualizado
    """
    rng = np.random.default_rng(seed)
    df = df.copy()
    df["_y_d"] = (df["I-d"] == 1).astype(int)
    df["_y_e"] = (df["I-e"] == 1).astype(int)

    # Validação e preparação dos targets
    def clean_targets(target, n_ramos):
        if target is None:
            return []
        return [int(k) for k in target if isinstance(k, (int, np.integer)) and 1 <= int(k) <= n_ramos]

    target_norm = clean_targets(target_norm, n_ramos)
    target_d = clean_targets(target_d, n_ramos)
    target_e = clean_targets(target_e, n_ramos)

    # Função para criar vetor r_t
    def make_r_vector(target_list, n_ramos):
        if not target_list:
            return np.full(n_ramos, 1.0 / n_ramos)
        r = np.zeros(n_ramos)
        m = len(target_list)
        for j in target_list:
            r[j-1] = 1.0 / m  # j é 1-based
        return r

    r_norm = make_r_vector(target_norm, n_ramos)
    r_d = make_r_vector(target_d, n_ramos)
    r_e = make_r_vector(target_e, n_ramos)

    conta2tx = df.groupby("NUMERO_CONTA")[["_y_d", "_y_e"]].agg(["sum", "count"])
    conta2ramo = {}
    for conta, row in conta2tx.iterrows():
        F_d = row[("_y_d", "sum")]
        F_e = row[("_y_e", "sum")]
        N_c = row[("_y_d", "count")]

        # Determinar tipo predominante
        if F_d + F_e == 0:
            t = "norm"
            r = r_norm
            p_fixed = p_fixed_norm
        elif F_d > F_e:
            t = "d"
            r = r_d
            p_fixed = p_fixed_d
        elif F_e > F_d:
            t = "e"
            r = r_e
            p_fixed = p_fixed_e
        else:
            t = "norm"
            r = r_norm
            p_fixed = p_fixed_norm

        # Calcular p_t (obrigatório)
        if p_fixed is None:
            raise ValueError(f"Parâmetro p_fixed_{t} deve ser fornecido.")
        p_t = float(p_fixed)
        p_t = min(max(p_t, 0), 1)

        # Construir vetor de probabilidades
        uniform_prob = 1.0 / n_ramos
        P = (1 - p_t) * np.full(n_ramos, uniform_prob) + p_t * r

        # Normalizar
        S = P.sum()
        if S == 0:
            P = np.full(n_ramos, 1.0 / n_ramos)
        else:
            P = P / S

        ramo = rng.choice(np.arange(1, n_ramos+1), p=P)
        conta2ramo[conta] = ramo

    if return_df:
        df["ramo_atividade"] = df["NUMERO_CONTA"].map(conta2ramo)
        return conta2ramo, df
    else:
        return conta2ramo

def assign_ramo_atividade_group_size(
    df,
    n_ramos=7,
    target_ramo=1,
    v=0.0,
    seed=42,
    return_df=False
):
    """
    Group size bias (marginal) controlado com 1 ramo-alvo.

    Interpretação de v:
      - v=0   -> uniforme (1/n_ramos para cada ramo)
      - v=1   -> 100% das contas no ramo-alvo
      - 0<v<1 -> mistura: q_eff = (1-v)*uniforme + v*delta_alvo

    Atribui por CONTA (não por transação) e controla proporções globais via contagens
    (com aleatoriedade apenas no embaralhamento final).
    """
    if "NUMERO_CONTA" not in df.columns:
        raise ValueError("df deve conter a coluna 'NUMERO_CONTA'.")

    rng = np.random.default_rng(seed)

    target_ramo = int(target_ramo)
    if not (1 <= target_ramo <= n_ramos):
        raise ValueError(f"target_ramo deve estar em 1..{n_ramos}.")

    v = float(v)
    v = min(max(v, 0.0), 1.0)

    # Distribuição efetiva: (1-v)*uniforme + v*delta_alvo
    uniform = np.full(n_ramos, 1.0 / n_ramos, dtype=float)
    delta = np.zeros(n_ramos, dtype=float)
    delta[target_ramo - 1] = 1.0
    q_eff = (1.0 - v) * uniform + v * delta
    q_eff = q_eff / q_eff.sum()

    # Universo de contas (por conta, não por transação)
    contas = pd.Series(df["NUMERO_CONTA"]).dropna().astype(str).unique()
    n = len(contas)
    if n == 0:
        return ({}, df.copy()) if return_df else {}

    # Contagens globais com ajuste por "maiores restos"
    raw = q_eff * n
    counts = np.floor(raw).astype(int)
    rem = n - counts.sum()
    if rem > 0:
        frac = raw - np.floor(raw)
        order = np.argsort(-frac)
        for idx in order[:rem]:
            counts[idx] += 1

    labels = np.concatenate([np.full(counts[k], k + 1, dtype=int) for k in range(n_ramos)])
    rng.shuffle(labels)

    conta2ramo = {conta: int(ramo) for conta, ramo in zip(contas, labels)}

    if return_df:
        out = df.copy()
        out["ramo_atividade"] = out["NUMERO_CONTA"].astype(str).map(conta2ramo)
        return conta2ramo, out
    return conta2ramo

def main():
    parser = argparse.ArgumentParser(description="Transforma dados do AMLSim em CSV de transações.")
    parser.add_argument(
        "-d", "--data-dir",
        help="Pasta contendo alert_transactions.csv, accounts.csv, cash_tx.csv (padrão: %(default)s)"
    )
    parser.add_argument(
        "-o", "--out",
        default=None,
        help="Arquivo de saída CSV (padrão: <data-dir>/sintetic_v0.csv)"
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
    out_file = args.out if args.out else os.path.join(data_dir, "sintetic_v0.csv")

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
    # Atribui ramo_atividade enviesado por contapython3 scripts/convert_logs.py conf.json
    
    conta2ramo = assign_ramo_atividade_targets(
        out_df,
        n_ramos=7,
        p_fixed_d=0,         # viés fixo para I-d
        p_fixed_norm=0,      # viés fixo para normais
        p_fixed_e=0,         # viés fixo para I-e (opcional)
        target_norm=[1],
        target_d=[4],
        target_e=[7],
        a=1.0,
        b=2.0,
        seed=192
    )

    """
    # Group size bias (1 ramo-alvo + v)
    conta2ramo = assign_ramo_atividade_group_size(
        out_df,
        n_ramos=7,
        target_ramo=1,  # ramo-alvo
        v=1,          # 0=uniforme, 1=sempre alvo
        seed=99
    )
    """
    out_df["RAMO_ATIVIDADE_1"] = out_df["NUMERO_CONTA"].map(conta2ramo)

    logging.info("Gravando arquivo de saída: %s", out_file)
    out_df.to_csv(out_file, index=False, encoding="utf-8")
    logging.info("Concluído. Arquivo gerado em: %s", out_file)

if __name__ == "__main__":
    main()