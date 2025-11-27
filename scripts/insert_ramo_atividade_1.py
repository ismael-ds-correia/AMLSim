import numpy as np

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