import pandas as pd
import matplotlib.pyplot as plt

csv_file = '../outputs/my_simulation2/transactions_output.csv'

df = pd.read_csv(csv_file)

# Converte a coluna de data para datetime
df['DATA_LANCAMENTO'] = pd.to_datetime(df['DATA_LANCAMENTO'])

# Conta o número de transações por conta por dia
tx_counts = df.groupby(['DATA_LANCAMENTO', 'NUMERO_CONTA']).size()

plt.figure(figsize=(10,6))
plt.hist(tx_counts, bins=range(1, tx_counts.max()+2), alpha=0.7, color='blue', rwidth=0.8)
plt.xlabel('Quantidade de transações por conta por dia')
plt.ylabel('Número de contas')
plt.title('Distribuição da quantidade de transações por conta diariamente')
plt.xticks(range(1, tx_counts.max()+2))
plt.tight_layout()
plt.show()