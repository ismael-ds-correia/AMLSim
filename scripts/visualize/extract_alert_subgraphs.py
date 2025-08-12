import os
import sys
import csv
import json
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict

def extract_alert_subgraphs(alert_accounts_csv, alert_transactions_csv):
    """
    Extrai subgrafos de operações suspeitas a partir dos arquivos alert_accounts.csv e alert_transactions.csv.
    Para cada alert_id, retorna um subgrafo contendo apenas os nós e arestas relacionados àquele alerta.
    """
    # Mapeia alert_id para contas envolvidas
    alert_accounts = defaultdict(set)
    with open(alert_accounts_csv, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        alert_id_idx = header.index("alert_id")
        acct_id_idx = header.index("acct_id")
        for row in reader:
            # Ignora linhas vazias ou incompletas
            if not row or len(row) <= max(alert_id_idx, acct_id_idx):
                continue
            alert_id = row[alert_id_idx]
            acct_id = row[acct_id_idx]
            alert_accounts[alert_id].add(acct_id)

    # Mapeia alert_id para transações (arestas)
    alert_edges = defaultdict(list)
    with open(alert_transactions_csv, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        alert_id_idx = header.index("alert_id")
        orig_idx = header.index("orig_acct")
        dest_idx = header.index("bene_acct")
        amount_idx = header.index("base_amt")
        date_idx = header.index("tran_timestamp")
        for row in reader:
            # Ignora linhas vazias ou incompletas
            if not row or len(row) <= max(alert_id_idx, orig_idx, dest_idx, amount_idx, date_idx):
                continue
            alert_id = row[alert_id_idx]
            orig = row[orig_idx]
            dest = row[dest_idx]
            amount = float(row[amount_idx])
            date = row[date_idx].split("T")[0] if "T" in row[date_idx] else row[date_idx]
            alert_edges[alert_id].append((orig, dest, {"amount": amount, "date": date}))

    # Cria um subgrafo para cada alerta
    alert_subgraphs = dict()
    for alert_id in alert_accounts:
        G = nx.DiGraph()
        # Adiciona nós
        for acct_id in alert_accounts[alert_id]:
            G.add_node(acct_id)
        # Adiciona arestas
        for orig, dest, attrs in alert_edges.get(alert_id, []):
            if orig in G.nodes and dest in G.nodes:
                G.add_edge(orig, dest, **attrs)
        alert_subgraphs[alert_id] = G

    return alert_subgraphs

def annotate_nodes_with_stats(G):
    """
    Para cada nó, calcula o número de transações e lista os valores.
    Adiciona essas informações como atributos do nó.
    """
    for node in G.nodes():
        tx_count = 0
        values = []
        # Transações de entrada
        for _, _, data in G.in_edges(node, data=True):
            tx_count += 1
            values.append(data.get("amount", 0))
        # Transações de saída
        for _, _, data in G.out_edges(node, data=True):
            tx_count += 1
            values.append(data.get("amount", 0))
        G.nodes[node]["tx_count"] = tx_count
        G.nodes[node]["values"] = values

def plot_alert_subgraph(G, alert_id, output_dir):
    """
    Plota e salva a imagem do subgrafo de um alerta.
    Os nós mostram o número de transações e os valores.
    As arestas mostram valor e data.
    """
    annotate_nodes_with_stats(G)
    pos = nx.spring_layout(G, seed=42)
    plt.figure(figsize=(10, 7))
    plt.axis('off')

    # Nós: rótulo com id, número de transações e valores
    node_labels = {n: f"{n}\nTxs:{G.nodes[n]['tx_count']}\nVals:{G.nodes[n]['values']}" for n in G.nodes()}
    node_sizes = [300 + 50 * G.nodes[n]['tx_count'] for n in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color="#FFD700", edgecolors="black", linewidths=1.5)
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)

    # Arestas: rótulo com valor e data
    amounts = [d.get("amount", 0) for _, _, d in G.edges(data=True)]
    max_amount = max(amounts) if amounts else 1
    edge_widths = [1 + 2 * d.get("amount", 0) / max_amount for _, _, d in G.edges(data=True)]
    edge_labels = {(u, v): f"{d.get('amount', 0)}\n{d.get('date', '')}" for u, v, d in G.edges(data=True)}

    nx.draw_networkx_edges(G, pos, arrows=True, width=edge_widths, arrowstyle='-|>', arrowsize=15)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)

    # Legenda manual
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Conta (tamanho ∝ nº transações)', markerfacecolor='#FFD700', markersize=10, markeredgecolor='black'),
        Line2D([0], [0], color='gray', lw=2, label='Aresta (espessura ∝ valor da transação)')
    ]
    plt.legend(handles=legend_elements, loc='upper left', fontsize=9)

    plt.title(f"Alert {alert_id} - Suspicious Subgraph")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"alert_{alert_id}.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()

def annotate_nodes_with_stats(G):
    """
    Para cada nó, calcula o número de transações em que está envolvido (origem ou destino)
    e lista todos os valores das transações associadas a esse nó.
    Adiciona essas informações como atributos do nó.
    """
    for node in G.nodes():
        tx_count = 0
        values = []
        # Transações de entrada (como destino)
        for _, _, data in G.in_edges(node, data=True):
            tx_count += 1
            values.append(data.get("amount", 0))
        # Transações de saída (como origem)
        for _, _, data in G.out_edges(node, data=True):
            tx_count += 1
            values.append(data.get("amount", 0))
        G.nodes[node]["tx_count"] = tx_count
        G.nodes[node]["values"] = values

def prepare_subgraph_data(G):
    """
    Prepara uma estrutura de dados para visualização do subgrafo suspeito.
    Retorna um dicionário com:
      - 'nodes': lista de dicionários com estatísticas de cada nó (ID, número de transações, lista de valores)
      - 'edges': lista de dicionários com atributos relevantes de cada aresta (origem, destino, valor, data, tipo)
    """
    # Certifica que os nós estão anotados com estatísticas
    annotate_nodes_with_stats(G)

    # Lista de nós com estatísticas
    nodes_data = []
    for node in G.nodes():
        node_info = {
            "id": node,
            "tx_count": G.nodes[node].get("tx_count", 0),
            "values": G.nodes[node].get("values", [])
        }
        nodes_data.append(node_info)

    # Lista de arestas com atributos relevantes
    edges_data = []
    for u, v, data in G.edges(data=True):
        edge_info = {
            "orig": u,
            "dest": v,
            "amount": data.get("amount", 0),
            "date": data.get("date", None),
            "type": data.get("type", None)
        }
        edges_data.append(edge_info)

    return {
        "nodes": nodes_data,
        "edges": edges_data
    }

def plot_alert_subgraph(G, alert_id, output_dir):
    """
    Plota e salva a imagem do subgrafo de um alerta.
    Layout: spring_layout (bom para grafos pequenos).
    Estilo dos nós: cor dourada, tamanho proporcional ao número de transações.
    Estilo das arestas: espessura proporcional ao valor da transação.
    Rótulos: cada nó mostra id, número de transações e valores; cada aresta mostra o valor.
    Legenda: explicando cores e tamanhos.
    """
    annotate_nodes_with_stats(G)
    pos = nx.spring_layout(G, seed=42)  # Layout fixo para reprodutibilidade
    plt.figure(figsize=(10, 7))
    plt.axis('off')

    # Estilo dos nós: tamanho proporcional ao número de transações
    node_sizes = [300 + 50 * G.nodes[n]['tx_count'] for n in G.nodes()]
    node_colors = "#FFD700"  # Dourado

    # Rótulo dos nós: id, número de transações, valores
    node_labels = {n: f"{n}\nTxs:{G.nodes[n]['tx_count']}\nVals:{G.nodes[n]['values']}" for n in G.nodes()}

    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, edgecolors="black", linewidths=1.5)
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)

    # Estilo das arestas: espessura proporcional ao valor
    edge_widths = [1 + 2 * d.get("amount", 0) / max(1, max([d.get("amount", 0) for _, _, d in G.edges(data=True)])) for _, _, d in G.edges(data=True)]
    edge_labels = {(u, v): f"{d.get('amount', 0)}" for u, v, d in G.edges(data=True)}

    nx.draw_networkx_edges(G, pos, arrows=True, width=edge_widths, arrowstyle='-|>', arrowsize=15)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)

    # Legenda manual
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Conta (tamanho ∝ nº transações)', markerfacecolor='#FFD700', markersize=10, markeredgecolor='black'),
        Line2D([0], [0], color='gray', lw=2, label='Aresta (espessura ∝ valor da transação)')
    ]
    plt.legend(handles=legend_elements, loc='upper left', fontsize=9)

    plt.title(f"Alert {alert_id} - Suspicious Subgraph")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"alert_{alert_id}.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()

def plot_alert_subgraph(G, alert_id, output_dir):
    """
    Para cada subgrafo suspeito, gera uma imagem (PNG) que mostra:
    - Os nós com rótulos informando o número de transações e os valores
    - As arestas conectando os nós, com rótulos de valor e data
    - Uma legenda explicando os elementos visuais
    Salva cada imagem com um nome identificando o alerta (ex: alert_123.png)
    """
    annotate_nodes_with_stats(G)
    pos = nx.spring_layout(G, seed=42)  # Layout fixo para reprodutibilidade
    plt.figure(figsize=(10, 7))
    plt.axis('off')

    # Estilo dos nós: tamanho proporcional ao número de transações
    node_sizes = [300 + 50 * G.nodes[n]['tx_count'] for n in G.nodes()]
    node_colors = "#FFD700"  # Dourado

    # Rótulo dos nós: id, número de transações, valores
    node_labels = {n: f"{n}\nTxs:{G.nodes[n]['tx_count']}\nVals:{G.nodes[n]['values']}" for n in G.nodes()}

    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, edgecolors="black", linewidths=1.5)
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)

    # Estilo das arestas: espessura proporcional ao valor
    amounts = [d.get("amount", 0) for _, _, d in G.edges(data=True)]
    max_amount = max(amounts) if amounts else 1
    edge_widths = [1 + 2 * d.get("amount", 0) / max_amount for _, _, d in G.edges(data=True)]
    edge_labels = {(u, v): f"{d.get('amount', 0)}\n{d.get('date', '')}" for u, v, d in G.edges(data=True)}

    nx.draw_networkx_edges(G, pos, arrows=True, width=edge_widths, arrowstyle='-|>', arrowsize=15)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)

    # Legenda manual
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Conta (tamanho ∝ nº transações)', markerfacecolor='#FFD700', markersize=10, markeredgecolor='black'),
        Line2D([0], [0], color='gray', lw=2, label='Aresta (espessura ∝ valor da transação)')
    ]
    plt.legend(handles=legend_elements, loc='upper left', fontsize=9)

    plt.title(f"Alert {alert_id} - Suspicious Subgraph")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"alert_{alert_id}.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()

def process_all_alerts(conf_json):
    """
    Automatiza o processo para todos os alertas:
    - Extrai subgrafos suspeitos
    - Calcula estatísticas dos nós
    - Gera visualização e salva imagem para cada alerta
    """
    # Carrega caminhos dos arquivos a partir do JSON de configuração
    with open(conf_json, "r") as rf:
        conf = json.load(rf)
    sim_name = conf["general"]["simulation_name"]
    out_dir = os.path.join(conf["output"]["directory"], sim_name)
    alert_members_csv = os.path.join(out_dir, conf["output"]["alert_members"])
    alert_transactions_csv = os.path.join(out_dir, conf["output"]["alert_transactions"])
    subgraph_dir = os.path.join(out_dir, "alert_subgraphs")

    print("Extraindo subgrafos de alertas suspeitos...")
    alert_subgraphs = extract_alert_subgraphs(alert_members_csv, alert_transactions_csv)
    print(f"Total de alertas encontrados: {len(alert_subgraphs)}")

    for alert_id, G in alert_subgraphs.items():
        print(f"Processando alerta {alert_id}: {G.number_of_nodes()} nós, {G.number_of_edges()} arestas")
        annotate_nodes_with_stats(G)
        plot_alert_subgraph(G, alert_id, subgraph_dir)
    print(f"Imagens salvas em: {subgraph_dir}")

def main(conf_json):
    # Carrega caminhos dos arquivos a partir do JSON de configuração
    with open(conf_json, "r") as rf:
        conf = json.load(rf)
    sim_name = conf["general"]["simulation_name"]
    out_dir = os.path.join(conf["output"]["directory"], sim_name)
    alert_members_csv = os.path.join(out_dir, conf["output"]["alert_members"])
    alert_transactions_csv = os.path.join(out_dir, conf["output"]["alert_transactions"])
    subgraph_dir = os.path.join(out_dir, "alert_subgraphs")

    print("Extraindo subgrafos de alertas suspeitos...")
    alert_subgraphs = extract_alert_subgraphs(alert_members_csv, alert_transactions_csv)
    print(f"Total de alertas encontrados: {len(alert_subgraphs)}")

    for alert_id, G in alert_subgraphs.items():
        print(f"Gerando imagem para alerta {alert_id} com {G.number_of_nodes()} nós e {G.number_of_edges()} arestas...")
        plot_alert_subgraph(G, alert_id, subgraph_dir)
    print(f"Imagens salvas em: {subgraph_dir}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python extract_alert_subgraphs.py [ConfJSON]")
        sys.exit(1)
    process_all_alerts(sys.argv[1])