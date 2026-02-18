import numpy as np
import matplotlib.pyplot as plt
import imageio
import pandas as pd

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
            r[j-1] = 1.0 / m
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

def gerar_gif_dinamico_vies(
    csv_path="sintetic_v0_5.csv",
    n_ramos=7,
    ramo_alvo=1,
    gif_path="vies_dinamico.gif"
):
    df = pd.read_csv(csv_path)

    # Garante tipos consistentes (evita map falhar por int vs str)
    df["NUMERO_CONTA"] = df["NUMERO_CONTA"].astype(str)

    frames = []
    v_values = np.linspace(0, 1, 51)

    for v in v_values:
        # Group size bias (1 ramo-alvo + v)
        conta2ramo = assign_ramo_atividade_group_size(
            df,
            n_ramos=n_ramos,
            target_ramo=ramo_alvo,
            v=v,
            seed=42
        )

        # Mapeia ramo por conta (chave é str)
        df["RAMO_ATIVIDADE_1"] = df["NUMERO_CONTA"].map(conta2ramo)

        # ---- AGORA: agrupar POR CONTA (não por transação) ----
        # Fraude por conta = existe ao menos uma transação com I-d==1 ou I-e==1
        acct = (
            df.groupby("NUMERO_CONTA", as_index=False)
              .agg(
                  RAMO_ATIVIDADE_1=("RAMO_ATIVIDADE_1", "first"),
                  any_d=("I-d", "max"),
                  any_e=("I-e", "max"),
              )
        )
        acct["Tipologia"] = np.where((acct["any_d"] == 1) | (acct["any_e"] == 1), "Fraude", "Normal")

        counts = (
            acct.groupby(["RAMO_ATIVIDADE_1", "Tipologia"])
                .size()
                .unstack(fill_value=0)
        )

        # Garante linhas 1..n_ramos e colunas fixas (e numéricas)
        counts = counts.reindex(index=range(1, n_ramos + 1), fill_value=0)
        counts = counts.reindex(columns=["Fraude", "Normal"], fill_value=0)
        counts = counts.apply(pd.to_numeric, errors="coerce").fillna(0)

        fig, ax = plt.subplots(figsize=(10, 5))
        counts.plot(kind="bar", stacked=False, ax=ax, color=["orange", "green"])
        ax.set_xlabel("Ramo Atividade 1")
        ax.set_ylabel("Quantidade de Contas")
        ax.set_title(
            f"Distribuição de Tipologias por RAMO_ATIVIDADE_1 (por conta)\n"
            f"Group size bias: v = {v:.2f} | Ramo alvo = {ramo_alvo}"
        )
        ax.legend(title="Tipologia")
        fig.tight_layout()

        fig.canvas.draw()
        image = np.frombuffer(fig.canvas.tostring_rgb(), dtype="uint8")
        image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        frames.append(image)
        plt.close(fig)

    total_duration = 10
    duration = total_duration / len(frames)
    imageio.mimsave(gif_path, frames, duration=duration)
    print(f"GIF salvo em: {gif_path}")

gerar_gif_dinamico_vies(
    csv_path="outputs/my_simulation2/sintetic_v0_5.csv",
    n_ramos=7,
    ramo_alvo=1,
    gif_path="vies_dinamico.gif"
)