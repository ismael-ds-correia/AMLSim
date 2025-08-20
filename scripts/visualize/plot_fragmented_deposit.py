import pandas as pd
import matplotlib.pyplot as plt
import os

# Caminhos dos arquivos
OUTPUT_DIR = "outputs/my_simulation2"
CHARTS_DIR = os.path.join(OUTPUT_DIR, "fragmented_deposit_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

ALERT_ACCOUNTS = os.path.join(OUTPUT_DIR, "alert_accounts.csv")
ALERT_TRANSACTIONS = os.path.join(OUTPUT_DIR, "alert_transactions.csv")

# Carrega os alertas do tipo fragmented_deposit
alert_accts = pd.read_csv(ALERT_ACCOUNTS)
frag_alerts = alert_accts[alert_accts['alert_type'] == 'fragmented_deposit']['alert_id'].unique()

# Carrega as transações de alerta
alert_txs = pd.read_csv(ALERT_TRANSACTIONS)

# Filtra apenas transações fragmented_deposit
frag_txs = alert_txs[alert_txs['alert_type'] == 'fragmented_deposit']

# Para cada conta beneficiária em depósitos fragmentados
for acct_id in frag_txs['bene_acct'].unique():
    txs = frag_txs[frag_txs['bene_acct'] == acct_id]
    if txs.empty:
        continue

    txs = txs.sort_values('tran_timestamp')
    txs = txs.reset_index(drop=True)
    txs['Depósito'] = txs.index + 1
    txs['cum_sum'] = txs['base_amt'].cumsum()
    total = txs['base_amt'].sum()
    txs['% do Total'] = txs['base_amt'] / total * 100

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(txs['Depósito'], txs['base_amt'], color='green', alpha=0.7)
    ax.plot(txs['Depósito'], txs['cum_sum'], color='black', marker='o', label='Acumulado')
    ax.axhline(50000, color='red', linestyle='--', label='Limite de Notificação (R$50.000)')
    ax.set_title(f"Timeline de Depósitos Fragmentados - Conta {acct_id}")
    ax.set_ylabel("Valor (R$)")
    ax.set_xlabel("Depósito")
    ax.set_xticks(txs['Depósito'])

    # Adiciona rótulos de valor e data acima das barras
    for bar, value, date in zip(bars, txs['base_amt'], txs['tran_timestamp']):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"R${value:,.2f}\n{date[:10]}",
                ha='center', va='bottom', fontsize=9)

    ax.legend()

    # Monta a tabela de informações
    table_data = []
    for idx, row in txs.iterrows():
        table_data.append([
            int(row['Depósito']),
            row['tran_timestamp'][:10],
            f"R${row['base_amt']:.2f}",
            f"{row['% do Total']:.1f}%",
            f"R${row['cum_sum']:.2f}"
        ])
    col_labels = ['#', 'Data', 'Valor', '% do Total', 'Acumulado']

    # Adiciona a tabela abaixo do gráfico (ajustada para mais espaço)
    plt.subplots_adjust(bottom=0.42)
    table = plt.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc='center',
        loc='bottom',
        bbox=[0.0, -0.60, 1, 0.45]  # aumenta a altura da tabela
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)  # aumenta o tamanho da fonte

    plt.tight_layout()
    # Salva o gráfico na subpasta
    filename = os.path.join(CHARTS_DIR, f"fragmented_deposit_{acct_id}.png")
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)