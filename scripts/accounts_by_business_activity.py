import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def load_csv_skip_slash_comments(csv_path: Path) -> pd.DataFrame:
    # Seu CSV pode ter linhas começando com "//", então tratamos linhas iniciando com "/" como comentário.
    return pd.read_csv(csv_path, comment="/", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Plot: number of accounts per business activity (RAMO_ATIVIDADE_1) split by fraud flag (any I-d/I-e)."
    )
    parser.add_argument(
        "--csv",
        default=str(Path("outputs") / "my_simulation2" / "sintetic_v1.csv"),
        help="Path to the synthetic CSV (default: outputs/my_simulation2/sintetic_v0.csv)",
    )
    parser.add_argument("--show", action="store_true", help="Show the plot window.")
    parser.add_argument(
        "--out",
        default=str(Path("outputs") / "accounts_by_business_activity.png"),
        help="Output image path (default: outputs/accounts_by_business_activity.png)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = load_csv_skip_slash_comments(csv_path)

    required = {"NUMERO_CONTA", "RAMO_ATIVIDADE_1", "I-d", "I-e"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in CSV: {sorted(missing)}")

    # Tipagem defensiva
    df["NUMERO_CONTA"] = df["NUMERO_CONTA"].astype(str)
    df["RAMO_ATIVIDADE_1"] = pd.to_numeric(df["RAMO_ATIVIDADE_1"], errors="coerce")
    df["I-d"] = pd.to_numeric(df["I-d"], errors="coerce").fillna(0).astype(int)
    df["I-e"] = pd.to_numeric(df["I-e"], errors="coerce").fillna(0).astype(int)

    # Agrupar POR CONTA: fraude se teve ao menos uma transação com I-d==1 ou I-e==1
    acct = (
        df.groupby("NUMERO_CONTA", as_index=False)
          .agg(
              RAMO_ATIVIDADE_1=("RAMO_ATIVIDADE_1", "first"),
              any_d=("I-d", "max"),
              any_e=("I-e", "max"),
          )
    )
    acct["Has_I-d_or_I-e"] = ((acct["any_d"] == 1) | (acct["any_e"] == 1))
    acct["Tipologia"] = acct["Has_I-d_or_I-e"].map({False: "No I-d/I-e", True: "Any I-d/I-e"})

    # Contar contas por ramo e tipologia
    counts = (
        acct.groupby(["RAMO_ATIVIDADE_1", "Tipologia"])
            .size()
            .unstack(fill_value=0)
            .reindex(columns=["No I-d/I-e", "Any I-d/I-e"], fill_value=0)
    )

    # Eixo x ordenado por ramo (1..N)
    counts = counts.sort_index()
    counts.index = counts.index.astype(int)

    ax = counts.plot(kind="bar", figsize=(12, 6), width=0.85, color=["green", "orange"])
    ax.set_xlabel("RAMO_ATIVIDADE_1")
    ax.set_ylabel("Number of accounts")
    ax.set_title("Accounts per business activity (by account): No I-d/I-e vs Any I-d/I-e")
    plt.xticks(rotation=0)
    plt.tight_layout()

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    print(f"Saved plot to: {out_path}")

    if args.show:
        plt.show()
    else:
        plt.close()


if __name__ == "__main__":
    main()