import pandas as pd
import matplotlib.pyplot as plt
import os
from matplotlib import font_manager
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

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

    txs = txs.sort_values('tran_timestamp').reset_index(drop=True)
    txs['Depósito'] = txs.index + 1
    txs['cum_sum'] = txs['base_amt'].cumsum()
    total = txs['base_amt'].sum()
    txs['% do Total'] = txs['base_amt'] / total * 100

    # Nova coluna para tipo CNAB
    def cnab_label(row):
        if row['tx_type'] == 'CHECK-DEPOSIT':
            return "201"
        elif row['tx_type'] == 'CASH-DEPOSIT':
            return "220"
        else:
            return row['tx_type']
    txs['Tipo CNAB'] = txs.apply(cnab_label, axis=1)

    # Extrai a data (assumindo que todos depósitos são no mesmo dia)
    if not txs.empty and pd.notnull(txs['tran_timestamp'].iloc[0]):
        data_unica = pd.to_datetime(txs['tran_timestamp'].iloc[0])
        if pd.notnull(data_unica):
            data_unica = data_unica.strftime('%Y-%m-%d')
        else:
            data_unica = "DATA_INVÁLIDA"
    else:
        data_unica = "DATA_INVÁLIDA"

    fig, ax = plt.subplots(figsize=(12, 7))

    # Define cores por tipo
    bar_colors = txs['tx_type'].map({
        'CHECK-DEPOSIT': 'green',
        'CASH-DEPOSIT': 'blue'
    }).fillna('gray')

    bars = ax.bar(txs['Depósito'], txs['base_amt'], color=bar_colors, alpha=0.7)
    ax.plot(txs['Depósito'], txs['cum_sum'], color='black', marker='o', label='Acumulado')
    ax.axhline(50000, color='red', linestyle='--', label='Limite de Notificação (R$50.000)')
    ax.set_title(f"Timeline de Depósitos Fragmentados - Conta {acct_id} - Data {data_unica}")
    ax.set_ylabel("Valor (R$)")
    ax.set_xlabel("Depósito")
    ax.set_xticks(txs['Depósito'])

    for bar, value in zip(bars, txs['base_amt']):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"R${value:,.2f}",
                ha='center', va='bottom', fontsize=9)

    # Legenda customizada para tipos CNAB
    legend_elements = [
        Patch(facecolor='green', label='201'),
        Patch(facecolor='blue', label='220'),
        Line2D([0], [0], color='black', marker='o', label='Acumulado', linewidth=2),
        Line2D([0], [0], color='red', linestyle='--', label='Limite de Notificação (R$50.000)', linewidth=2)
    ]
    ax.legend(handles=legend_elements, loc='upper left')

    # Monta a tabela de informações (inclui tipo CNAB)
    table_data = []
    for idx, row in txs.iterrows():
        table_data.append([
            int(row['Depósito']),
            f"R${row['base_amt']:.2f}",
            f"{row['% do Total']:.1f}%",
            f"R${row['cum_sum']:.2f}",
            row['Tipo CNAB']
        ])
    table_data.append([
        'TOTAL', f"R${total:.2f}", "100%", f"R${total:.2f}", ""
    ])
    col_labels = ['#', 'Valor', '% do Total', 'Acumulado', 'Tipo CNAB']

    plt.subplots_adjust(bottom=0.48)
    table = plt.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc='center',
        loc='bottom',
        bbox=[0.0, -0.85, 1, 0.6]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(13)

    # Defina font_props aqui
    font_props = font_manager.FontProperties(weight='light', size=12)

    # Ajuste dinâmico das larguras das colunas conforme o conteúdo
    import numpy as np
    renderer = fig.canvas.get_renderer()
    col_widths = []
    for col in range(len(col_labels)):
        max_len = max([len(str(row[col])) for row in table_data] + [len(col_labels[col])])
        col_widths.append(0.0125 * max_len)
    col_widths = np.array(col_widths)
    col_widths = col_widths / col_widths.sum()

    for (row, col), cell in table.get_celld().items():
        if col < len(col_widths):
            cell.set_width(col_widths[col])
        cell.set_linewidth(0.2)
        cell.set_fontsize(12)
        cell.FONTPROPERTIES = font_props

    plt.tight_layout()
    filename = os.path.join(CHARTS_DIR, f"fragmented_deposit_{acct_id}.png")
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)