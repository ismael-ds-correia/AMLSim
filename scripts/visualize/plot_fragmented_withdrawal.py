import pandas as pd
import matplotlib.pyplot as plt
import os
from matplotlib import font_manager

# Caminhos dos arquivos
OUTPUT_DIR = "outputs/my_simulation2"
CHARTS_DIR = os.path.join(OUTPUT_DIR, "fragmented_withdrawal_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

ALERT_ACCOUNTS = os.path.join(OUTPUT_DIR, "alert_accounts.csv")
ALERT_TRANSACTIONS = os.path.join(OUTPUT_DIR, "alert_transactions.csv")

# Carrega os alertas do tipo fragmented_withdrawal
alert_accts = pd.read_csv(ALERT_ACCOUNTS)
frag_alerts = alert_accts[alert_accts['alert_type'] == 'fragmented_withdrawal']['alert_id'].unique()

# Carrega as transações de alerta
alert_txs = pd.read_csv(ALERT_TRANSACTIONS)

# Filtra apenas transações fragmented_withdrawal
frag_txs = alert_txs[alert_txs['alert_type'] == 'fragmented_withdrawal']

# Para cada conta que realizou saques fragmentados
for acct_id in frag_txs['orig_acct'].unique():
    txs = frag_txs[frag_txs['orig_acct'] == acct_id]
    if txs.empty:
        continue

    txs = txs.sort_values('tran_timestamp')
    txs = txs.reset_index(drop=True)
    txs['Saque'] = txs.index + 1
    txs['cum_sum'] = txs['base_amt'].cumsum()
    total = txs['base_amt'].sum()
    txs['% do Total'] = txs['base_amt'] / total * 100

    # Extrai a data (assumindo que todos saques são no mesmo dia)
    if not txs.empty and pd.notnull(txs['tran_timestamp'].iloc[0]):
        data_unica = pd.to_datetime(txs['tran_timestamp'].iloc[0])
        if pd.notnull(data_unica):
            data_unica = data_unica.strftime('%Y-%m-%d')
        else:
            data_unica = "DATA_INVÁLIDA"
    else:
        data_unica = "DATA_INVÁLIDA"

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(txs['Saque'], txs['base_amt'], color='orange', alpha=0.7)
    ax.plot(txs['Saque'], txs['cum_sum'], color='black', marker='o', label='Acumulado')
    ax.axhline(50000, color='red', linestyle='--', label='Limite de Notificação (R$50.000)')
    ax.set_title(f"Timeline de Saques Fragmentados - Conta {acct_id} - Data {data_unica}")
    ax.set_ylabel("Valor (R$)")
    ax.set_xlabel("Saque")
    ax.set_xticks(txs['Saque'])

    for bar, value in zip(bars, txs['base_amt']):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"R${value:,.2f}",
                ha='center', va='bottom', fontsize=9)

    ax.legend()

    # Monta a tabela de informações (sem horário)
    table_data = []
    for idx, row in txs.iterrows():
        table_data.append([
            int(row['Saque']),
            f"R${row['base_amt']:.2f}",
            f"{row['% do Total']:.1f}%",
            f"R${row['cum_sum']:.2f}"
        ])

    # Linha de total: "TOTAL" na primeira coluna
    table_data.append([
        'TOTAL', f"R${total:.2f}", "100%", f"R${total:.2f}"
    ])
    col_labels = ['#', 'Valor', '% do Total', 'Acumulado']

    # Ajusta espaço e tamanho da tabela para melhor leitura
    plt.subplots_adjust(bottom=0.48)
    table = plt.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc='center',
        loc='bottom',
        bbox=[0.0, -0.75, 1, 0.5]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(13)

    # Define largura, altura e fonte fina para cada célula
    cell_width = 0.2
    cell_height = 0.1
    font_props = font_manager.FontProperties(weight='light', size=12)
    for key, cell in table.get_celld().items():
        cell.set_width(cell_width)
        cell.set_height(cell_height)
        cell.set_linewidth(0.2)
        cell.set_fontsize(12)
        cell.FONTPROPERTIES = font_props  # fonte fina para cada célula

    plt.tight_layout()
    # Salva o gráfico na subpasta
    filename = os.path.join(CHARTS_DIR, f"fragmented_withdrawal_{acct_id}.png")
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)