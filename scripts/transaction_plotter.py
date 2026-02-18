import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter

csv_file = 'outputs/my_simulation2/sintetic_v0.csv'

df = pd.read_csv(csv_file)

# Converte a coluna de data para datetime
df['DATA_LANCAMENTO'] = pd.to_datetime(df['DATA_LANCAMENTO'])

# Conta o número de transações por conta por dia
tx_counts = df.groupby(['DATA_LANCAMENTO', 'NUMERO_CONTA']).size()

# Calcula a frequência de cada número de transações
freq = Counter(tx_counts)

# Separa x (número de transações) e y (frequência)
x = sorted(freq.keys())
y = [freq[k] for k in x]

plt.figure(figsize=(10, 6))
plt.loglog(x, y, 'bo', markersize=4)  # log-log com pontos azuis
plt.xlabel('Number of daily transactions per account')
plt.ylabel('Frequency')
plt.title('Daily Transaction Frequency Distribution')
plt.grid(True, which="both", ls="--", alpha=0.3)
plt.tight_layout()
plt.savefig('outputs/daily_tx_frequency.png', dpi=150)
plt.show()