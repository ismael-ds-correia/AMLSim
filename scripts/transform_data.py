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
import yaml
from pydantic import BaseModel, ValidationError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from amlsim_config import BiasConfig as SharedBiasConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class TransformDataConfig(BaseModel):
    bias: SharedBiasConfig

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
    g_priv=None,
    g_despriv=None,
    v_priv=0.0,
    v_despriv=0.0,
    seed=42,
    return_df=False,
    n=None,
    target_despriv=None,
    v=None,
):
    """
    Viés de prevalência com dois grupos:
    - Contas suspeitas (ao menos um I-d=1 ou I-e=1) recebem mistura convexa entre a distribuição uniforme global e a distribuição uniforme do grupo desprivilegiado.
    - Contas não suspeitas recebem mistura convexa entre a distribuição uniforme global e a distribuição uniforme do grupo privilegiado.
    Parâmetros:
        df: DataFrame de transações (com colunas NUMERO_CONTA, I-d, I-e)
        n / n_ramos: número de ramos possíveis (N)
        g_priv: lista de ramos do grupo privilegiado
        g_despriv: lista de ramos do grupo desprivilegiado
        v_priv: intensidade do viés para contas não suspeitas [0,1]
        v_despriv: intensidade do viés para contas suspeitas [0,1]
        seed: semente RNG
        return_df: se True, retorna também df com coluna 'ramo_atividade'
    Retorna:
        conta2ramo: dict {NUMERO_CONTA -> ramo_atividade (1..N)}
        (opcional) df atualizado
    """
    n_ramos = n if n is not None else n_ramos

    # Compatibilidade retroativa com a chamada atual do pipeline.
    # Se o chamador ainda passar target_despriv/v, convertemos para o novo mecanismo.
    if g_despriv is None and target_despriv is not None:
        g_despriv = target_despriv
    if g_priv is None and g_despriv is not None:
        g_priv = [ramo for ramo in range(1, n_ramos + 1) if ramo not in set(g_despriv)]
    if g_priv is None:
        g_priv = list(range(1, n_ramos + 1))
    if g_despriv is None:
        g_despriv = list(range(1, n_ramos + 1))

    if v is not None:
        v_priv = v if v_priv == 0.0 else v_priv
        v_despriv = v if v_despriv == 0.0 else v_despriv

    if not (1 <= int(n_ramos)):
        raise ValueError("n_ramos deve ser positivo.")

    def _normalize_probabilities(group_ramos):
        group = sorted({int(ramo) for ramo in group_ramos})
        if not group:
            raise ValueError("Os grupos de ramos não podem ser vazios.")
        for ramo in group:
            if ramo < 1 or ramo > n_ramos:
                raise ValueError(f"Cada ramo deve estar em 1..{n_ramos}.")
        vector = np.zeros(n_ramos, dtype=float)
        vector[np.array(group, dtype=int) - 1] = 1.0 / len(group)
        return vector

    def _mix_with_uniform(base_uniform, group_uniform, intensity):
        intensity = float(intensity)
        intensity = min(max(intensity, 0.0), 1.0)
        return (1.0 - intensity) * base_uniform + intensity * group_uniform

    rng = np.random.default_rng(seed)
    df = df.copy()
    # Etapa determinística: identificar suspeita por conta.
    conta2suspeita = df.groupby("NUMERO_CONTA").apply(
        lambda x: ((x["I-d"] == 1) | (x["I-e"] == 1)).any()
    )

    # Etapa determinística: construir os vetores de probabilidade.
    q0 = np.full(n_ramos, 1.0 / n_ramos, dtype=float)
    q_priv = _normalize_probabilities(g_priv)
    q_despriv = _normalize_probabilities(g_despriv)

    # Etapa determinística: definir a distribuição efetiva por conta.
    contas = df["NUMERO_CONTA"].unique()
    conta2ramo = {}

    for conta in contas:
        suspeita = conta2suspeita.get(conta, False)
        if suspeita:
            P = _mix_with_uniform(q0, q_despriv, v_despriv)
        else:
            P = _mix_with_uniform(q0, q_priv, v_priv)

        # Etapa de amostragem: normaliza e sorteia o ramo final.
        P = np.clip(P, 0.0, None)
        sumP = P.sum()
        if sumP <= 0.0:
            P = q0.copy()
        else:
            P = P / sumP

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
    Group size bias (marginal) controlado com 1 ou mais ramos-alvo.

    Interpretação de v:
      - v=0   -> uniforme (1/n_ramos para cada ramo)
      - v=1   -> 100% das contas nos ramos-alvo (uniforme entre eles)
      - 0<v<1 -> mistura: q_eff = (1-v)*q0 + v*q1
    Onde:
      - q0: uniforme global
      - q1: uniforme nos ramos-alvo (lista ou int)

    Atribui por CONTA (não por transação) e controla proporções globais via contagens
    (com aleatoriedade apenas no embaralhamento final).
    """
    if "NUMERO_CONTA" not in df.columns:
        raise ValueError("df deve conter a coluna 'NUMERO_CONTA'.")

    rng = np.random.default_rng(seed)

    # Permitir target_ramo ser int ou lista
    if isinstance(target_ramo, int):
        target_ramos = [target_ramo]
    elif isinstance(target_ramo, (list, tuple, np.ndarray)):
        target_ramos = list(target_ramo)
    else:
        raise ValueError("target_ramo deve ser int ou lista de int.")

    # Validação dos ramos
    for ramo in target_ramos:
        if not (1 <= int(ramo) <= n_ramos):
            raise ValueError(f"Cada target_ramo deve estar em 1..{n_ramos}.")

    v = float(v)
    v = min(max(v, 0.0), 1.0)

    # q0: uniforme global
    q0 = np.full(n_ramos, 1.0 / n_ramos, dtype=float)
    # q1: uniforme nos ramos-alvo
    q1 = np.zeros(n_ramos, dtype=float)
    m = len(target_ramos)
    for j in target_ramos:
        q1[j-1] = 1.0 / m

    # Distribuição efetiva: (1-v)*q0 + v*q1
    q_eff = (1.0 - v) * q0 + v * q1
    q_eff = q_eff / q_eff.sum()

    # Universo de contas (por conta, não por transação)
    contas = pd.Series(df["NUMERO_CONTA"]).dropna().astype(str).unique()
    n = len(contas)
    if n == 0:
        return ({}, df.copy()) if return_df else {}

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
        required=True,
        help="Pasta contendo alert_transactions.csv, accounts.csv, cash_tx.csv (padrão: %(default)s)"
    )
    parser.add_argument(
        "-o", "--out",
        default=None,
        help="Arquivo de saída CSV (padrão: <data-dir>/sintetic_v0.csv)"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Arquivo de configuração YAML (padrão: config.yaml na raiz)"
    )

    args = parser.parse_args()

    # Carrega parâmetros do YAML
    config_path = os.path.abspath(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        logging.error("Invalid YAML configuration: expected a mapping at root (%s)", config_path)
        sys.exit(1)

    try:
        validated_config = TransformDataConfig.model_validate(config)
    except ValidationError as exc:
        logging.error("Invalid YAML configuration in %s:\n%s", config_path, exc)
        sys.exit(1)

    bias_cfg = validated_config.bias
    bias_common = bias_cfg.common
    n_ramos = bias_common.n_ramos
    bias_method = bias_common.method
    bias_seed = bias_common.seed

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        logging.error("Diretório de dados não encontrado: %s", data_dir)
        sys.exit(1)

    alert_tx_file = os.path.join(data_dir, "transactions.csv")
    cash_tx_file = os.path.join(data_dir, "cash_tx.csv")
    accounts_file = os.path.join(data_dir, "accounts.csv")
    alert_accounts_file = os.path.join(data_dir, "alert_accounts.csv")

    # Novo: lê nome do arquivo de saída do config.yaml, se existir
    out_file = None
    files_cfg = config.get("files", {})
    output_file_from_yaml = files_cfg.get("output_file")
    if args.out:
        out_file = args.out
    elif output_file_from_yaml:
        out_file = output_file_from_yaml
    else:
        out_file = os.path.join(data_dir, "sintetic_v0.csv")

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
    # Atribui ramo_atividade enviesado por conta
    

    # Seleciona método de viés
    if bias_method == "group_size":
        group_cfg = bias_cfg.group_size
        if group_cfg is None:
            raise ValueError("bias.group_size is required when bias.common.method is 'group_size'")
        conta2ramo = assign_ramo_atividade_group_size(
            out_df,
            n_ramos=n_ramos,
            target_ramo=group_cfg.target_ramo,
            v=group_cfg.v,
            seed=bias_seed
        )
    elif bias_method == "prevalency_disparity":
        prev_cfg = bias_cfg.prevalency_disparity
        if prev_cfg is None:
            raise ValueError("bias.prevalency_disparity is required when bias.common.method is 'prevalency_disparity'")
        conta2ramo = assign_ramo_atividade_targets(
            out_df,
            n=n_ramos,
            g_priv=prev_cfg.g_priv,
            g_despriv=prev_cfg.g_despriv,
            v_priv=prev_cfg.v_priv,
            v_despriv=prev_cfg.v_despriv,
            seed=bias_seed
        )
    else:
        raise ValueError(f"Método de viés desconhecido: {bias_method}")

    out_df["RAMO_ATIVIDADE_1"] = out_df["NUMERO_CONTA"].map(conta2ramo)

    logging.info("Gravando arquivo de saída: %s", out_file)
    out_df.to_csv(out_file, index=False, encoding="utf-8")
    logging.info("Concluído. Arquivo gerado em: %s", out_file)

if __name__ == "__main__":
    main()