"""
Plot statistical distributions from the transaction graph.
"""

import os
import sys
import csv
import json
from collections import Counter, defaultdict
import networkx as nx
import powerlaw
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
import matplotlib
import matplotlib.pyplot as plt
import warnings

import warnings
category = UserWarning
warnings.filterwarnings('ignore', category=category)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning)


def get_date_list(_g):
    all_dates = list(nx.get_edge_attributes(_g, "date").values())
    start_date = min(all_dates)
    end_date = max(all_dates)
    days = (end_date - start_date).days + 1
    date_list = [start_date + timedelta(days=n) for n in range(days)]
    return date_list


def construct_graph(_acct_csv, _tx_csv, _schema):
    """Load transaction CSV file and construct Graph
    :param _acct_csv: Account CSV file (e.g. output/accounts.csv)
    :param _tx_csv: Transaction CSV file (e.g. output/transactions.csv)
    :param _schema: Dict for schema from JSON file
    :return: Transaction Graph
    :rtype: nx.MultiDiGraph
    """
    _g = nx.MultiDiGraph()

    id_idx = None
    bank_idx = None
    sar_idx = None

    acct_schema = _schema["account"]
    for i, col in enumerate(acct_schema):
        data_type = col.get("dataType")
        if data_type == "account_id":
            id_idx = i
        elif data_type == "bank_id":
            bank_idx = i
        elif data_type == "sar_flag":
            sar_idx = i

    orig_idx = None
    bene_idx = None
    type_idx = None
    amt_idx = None
    date_idx = None

    with open(_acct_csv, "r") as _rf:
        reader = csv.reader(_rf)
        next(reader)  # Skip header

        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue  # Ignora linhas vazias ou só com espaços
            acct_id = row[id_idx]
            bank_id = row[bank_idx]
            is_sar = row[sar_idx].lower() == "true"
            _g.add_node(acct_id, bank_id=bank_id, is_sar=is_sar)

    tx_schema = _schema["transaction"]
    for i, col in enumerate(tx_schema):
        data_type = col.get("dataType")
        if data_type == "orig_id":
            orig_idx = i
        elif data_type == "dest_id":
            bene_idx = i
        elif data_type == "transaction_type":
            type_idx = i
        elif data_type == "amount":
            amt_idx = i
        elif data_type == "timestamp":
            date_idx = i
        elif data_type == "sar_flag":
            sar_idx = i

    with open(_tx_csv, "r") as _rf:
        reader = csv.reader(_rf)
        next(reader)  # Skip header

        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue  # Ignora linhas vazias ou só com espaços
            orig = row[orig_idx]
            bene = row[bene_idx]
            tx_type = row[type_idx]
            amount = float(row[amt_idx])
            date_str = row[date_idx].split("T")[0]
            date = datetime.strptime(date_str, "%Y-%m-%d")
            is_sar = row[sar_idx].lower() == "true"
            _g.add_edge(orig, bene, amount=amount, date=date, type=tx_type, is_sar=is_sar)

    return _g

def create_weighted_graphs(_g):
    """Create weighted graphs from the transaction graph
    :param _g: Transaction graph
    :return: Two dictionaries representing transaction count and amount weighted edges
    """
    edge_counts = {}
    edge_amounts = {}
    
    # Group transactions by source-destination pairs
    for src, dst, attr in _g.edges(data=True):
        edge = (src, dst)
        amount = float(attr.get("amount", 0))
        if edge in edge_counts:
            edge_counts[edge] += 1
            edge_amounts[edge] += amount
        else:
            edge_counts[edge] = 1
            edge_amounts[edge] = amount
    
    return edge_counts, edge_amounts

import numpy as np
import matplotlib.pyplot as plt

def plot_strength_distributions(_g, _plot_img):
    """
    Plota as distribuições CCDF de in-strength e out-strength para grafos ponderados por número de transações e por volume.
    :param _g: grafo de transações (MultiDiGraph)
    :param _plot_img: caminho do arquivo de saída da imagem
    """
    # Cria os grafos ponderados
    edge_counts, edge_amounts = create_weighted_graphs(_g)

    # Inicializa dicionários para força de entrada/saída
    in_strength_count = {n: 0 for n in _g.nodes()}
    out_strength_count = {n: 0 for n in _g.nodes()}
    in_strength_amount = {n: 0 for n in _g.nodes()}
    out_strength_amount = {n: 0 for n in _g.nodes()}

    # Calcula as forças para cada nó
    for (src, dst), w in edge_counts.items():
        out_strength_count[src] += w
        in_strength_count[dst] += w
    for (src, dst), w in edge_amounts.items():
        out_strength_amount[src] += w
        in_strength_amount[dst] += w

    # Função para calcular CCDF
    def ccdf(strengths):
        strengths = np.array(list(strengths.values()))
        strengths = strengths[strengths > 0]
        strengths_sorted = np.sort(strengths)
        ccdf_y = 1.0 - np.arange(1, len(strengths_sorted)+1) / len(strengths_sorted)
        return strengths_sorted, ccdf_y

    # Calcula CCDFs
    x_in_count, y_in_count = ccdf(in_strength_count)
    x_out_count, y_out_count = ccdf(out_strength_count)
    x_in_amount, y_in_amount = ccdf(in_strength_amount)
    x_out_amount, y_out_amount = ccdf(out_strength_amount)

    # Plota
    plt.figure(figsize=(10, 5))
    plt.loglog(x_in_count, y_in_count, 'r.', label='In-strength $G^T$')
    plt.loglog(x_out_count, y_out_count, 'b.', label='Out-strength $G^T$')
    plt.loglog(x_in_amount, y_in_amount, 'g*', label='In-strength $G^N$')
    plt.loglog(x_out_amount, y_out_amount, 'm.', label='Out-strength $G^N$')
    plt.xlabel("Strength (s)")
    plt.ylabel("$P_{>}(s)$")
    plt.legend()
    plt.tight_layout()
    plt.savefig(_plot_img)
    plt.close()

def plot_clustering_vs_degree(_g, _plot_img):
    """
    Plota o coeficiente de agrupamento médio em função do grau para diferentes grafos ponderados.
    :param _g: grafo de transações (MultiDiGraph)
    :param _plot_img: caminho do arquivo de saída da imagem
    """
    # Cria grafos ponderados
    edge_counts, edge_amounts = create_weighted_graphs(_g)

    # Grafo por número de transações (G^T)
    G_T = nx.DiGraph()
    for (src, dst), w in edge_counts.items():
        G_T.add_edge(src, dst, weight=w)
    # Grafo por volume (G^N)
    G_N = nx.DiGraph()
    for (src, dst), w in edge_amounts.items():
        G_N.add_edge(src, dst, weight=w)

    # Função para calcular clustering médio por grau
    def clustering_by_degree(G):
        # Se for MultiGraph/MultiDiGraph, converte para Graph
        if isinstance(G, (nx.MultiGraph, nx.MultiDiGraph)):
            G_simple = nx.Graph()
            for u, v, data in G.edges(data=True):
                # Soma os pesos das arestas múltiplas
                w = data.get('weight', 1)
                if G_simple.has_edge(u, v):
                    G_simple[u][v]['weight'] += w
                else:
                    G_simple.add_edge(u, v, weight=w)
        else:
            G_simple = G.to_undirected()

        degrees = dict(G_simple.degree())
        clustering = nx.clustering(G_simple, weight='weight')
        degs = []
        clusts = []
        for n in G_simple.nodes():
            degs.append(degrees[n])
            clusts.append(clustering[n])
        return np.array(degs), np.array(clusts)

    # Calcula para cada grafo
    deg_T, clust_T = clustering_by_degree(G_T)
    deg_N, clust_N = clustering_by_degree(G_N)
    deg_base, clust_base = clustering_by_degree(_g)

    # Plota
    plt.figure(figsize=(10, 6))
    plt.scatter(deg_base, clust_base, s=8, c='r', label='G')
    plt.scatter(deg_T, clust_T, s=8, c='b', label='G$^T$')
    plt.scatter(deg_N, clust_N, s=8, c='g', label='G$^N$')
    plt.xscale('log')
    plt.yscale('log')
    plt.xlabel("Degree (k)")
    plt.ylabel("Clustering Coefficient")
    plt.legend()
    plt.tight_layout()
    plt.savefig(_plot_img)
    plt.close()

def calculate_transaction_correlation(edge_counts, edge_amounts):
    """Calculate Spearman correlation between transaction count and amount
    :param edge_counts: Dictionary with edges as keys and transaction counts as values
    :param edge_amounts: Dictionary with edges as keys and transaction amounts as values
    :return: Correlation coefficient, p-value, and formatted correlation text
    """
    from scipy import stats
    
    # Extract edge weights for correlation
    edges = list(edge_counts.keys())
    tx_counts = [edge_counts[edge] for edge in edges]
    tx_amounts = [edge_amounts[edge] for edge in edges]
    
    # Calculate Spearman correlation
    try:
        correlation, p_value = stats.spearmanr(tx_counts, tx_amounts)
        corr_text = f"Spearman correlation: {correlation:.4f} (p-value: {p_value:.4e})"
    except Exception as e:
        print(f"Error calculating correlation: {e}")
        correlation, p_value = None, None
        corr_text = "Correlation calculation failed"
    
    return correlation, p_value, corr_text, tx_counts, tx_amounts

def plot_transaction_correlation(_g, _plot_img):
    """Plot correlation between transaction count and transaction amount
    :param _g: Transaction graph
    :param _plot_img: Output image file path
    :return: Spearman correlation coefficient and p-value
    """
    # Create weighted graphs
    edge_counts, edge_amounts = create_weighted_graphs(_g)
    
    # Calculate correlation
    correlation, p_value, corr_text, tx_counts, tx_amounts = calculate_transaction_correlation(
        edge_counts, edge_amounts
    )
    
    # Create log-log scatter plot
    plt.figure(figsize=(12, 10))
    plt.loglog(tx_counts, tx_amounts, 'bo', alpha=0.5, markersize=4)
    plt.title(f"Transaction Count vs Total Amount\n{corr_text}")
    plt.xlabel("Number of Transactions (log scale)")
    plt.ylabel("Total Transaction Amount (log scale)")
    plt.grid(True, which="both", ls="--", alpha=0.3)
    plt.tight_layout()
    plt.savefig(_plot_img)
    
    print(f"Transaction correlation: {corr_text}")
    return correlation, p_value

def plot_degree_distribution(_g, _conf, _plot_img, log_log_plot_img=None):
    """Plot degree distribution for accounts (vertices)
    :param _g: Transaction graph
    :param _conf: Configuration object
    :param _plot_img: Degree distribution image (normal plot)
    :param log_log_plot_img: Degree distribution image (log-log plot)
    :return:
    """
    # Load parameter files
    _input_conf = _conf["input"]
    _input_dir = _input_conf["directory"]
    _input_acct = _input_conf["accounts"]
    _input_deg = _input_conf["degree"]
    input_acct_path = os.path.join(_input_dir, _input_acct)
    input_deg_path = os.path.join(_input_dir, _input_deg)

    if not os.path.isfile(input_acct_path):
        print("Account parameter file %s is not found." % input_acct_path)
        return

    total_num_accts = 0
    with open(input_acct_path, "r") as _rf:
        reader = csv.reader(_rf)
        header = next(reader)
        count_idx = None
        for i, col in enumerate(header):
            if col == "count":
                count_idx = i
                break
        for row in reader:
            total_num_accts += int(row[count_idx])

    if not os.path.isfile(input_deg_path):
        print("Degree parameter file %s is not found." % input_deg_path)
        return

    deg_num_accts = 0
    in_degrees = list()
    in_deg_seq = list()
    in_deg_hist = list()
    out_degrees = list()
    out_deg_seq = list()
    out_deg_hist = list()
    with open(input_deg_path, "r") as _rf:
        reader = csv.reader(_rf)
        next(reader)
        for row in reader:
            deg = int(row[0])
            in_num = int(row[1])
            out_num = int(row[2])
            if in_num > 0:
                in_degrees.extend([deg] * in_num)
                in_deg_seq.append(deg)
                in_deg_hist.append(in_num)
                deg_num_accts += in_num
            if out_num > 0:
                out_degrees.extend([deg] * out_num)
                out_deg_seq.append(deg)
                out_deg_hist.append(out_num)

    multiplier = total_num_accts // deg_num_accts
    in_degrees = [d * multiplier for d in in_degrees]
    in_deg_hist = [d * multiplier for d in in_deg_hist]
    out_degrees = [d * multiplier for d in out_degrees]
    out_deg_hist = [d * multiplier for d in out_deg_hist]

    # Generate normal plot
    plt.clf()
    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    ax1, ax2, ax3, ax4 = axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1]

    pw_result = powerlaw.Fit(in_degrees, verbose=False)
    alpha = pw_result.power_law.alpha
    alpha_text = "alpha = %.2f" % alpha
    ax1.plot(in_deg_seq, in_deg_hist, "bo-")
    ax1.set_title("Expected in-degree distribution")
    plt.text(0.75, 0.9, alpha_text, transform=ax1.transAxes)
    ax1.set_xlabel("In-degree")
    ax1.set_ylabel("Number of account vertices")

    pw_result = powerlaw.Fit(out_degrees, verbose=False)
    alpha = pw_result.power_law.alpha
    alpha_text = "alpha = %.2f" % alpha
    ax2.plot(out_deg_seq, out_deg_hist, "ro-")
    ax2.set_title("Expected out-degree distribution")
    plt.text(0.75, 0.9, alpha_text, transform=ax2.transAxes)
    ax2.set_xlabel("Out-degree")
    ax2.set_ylabel("Number of account vertices")

    in_degrees = [len(_g.pred[n].keys()) for n in _g.nodes()]
    in_deg_seq = sorted(set(in_degrees))
    in_deg_hist = [in_degrees.count(x) for x in in_deg_seq]
    pw_result = powerlaw.Fit(in_degrees, verbose=False)
    alpha = pw_result.power_law.alpha
    alpha_text = "alpha = %.2f" % alpha
    ax3.plot(in_deg_seq, in_deg_hist, "bo-")
    ax3.set_title("Output in-degree distribution")
    plt.text(0.75, 0.9, alpha_text, transform=ax3.transAxes)
    ax3.set_xlabel("In-degree")
    ax3.set_ylabel("Number of account vertices")

    out_degrees = [len(_g.succ[n].keys()) for n in _g.nodes()]
    out_deg_seq = sorted(set(out_degrees))
    out_deg_hist = [out_degrees.count(x) for x in out_deg_seq]
    pw_result = powerlaw.Fit(out_degrees, verbose=False)
    alpha = pw_result.power_law.alpha
    alpha_text = "alpha = %.2f" % alpha
    ax4.plot(out_deg_seq, out_deg_hist, "ro-")
    ax4.set_title("Output out-degree distribution")
    plt.text(0.75, 0.9, alpha_text, transform=ax4.transAxes)
    ax4.set_xlabel("Out-degree")
    ax4.set_ylabel("Number of account vertices")

    plt.savefig(_plot_img)

    # Generate log-log plot if specified
    if log_log_plot_img:
        plt.clf()
        fig, axs = plt.subplots(2, 2, figsize=(16, 12))
        ax1, ax2, ax3, ax4 = axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1]

        ax1.loglog(in_deg_seq, in_deg_hist, "bo-")
        ax1.set_title("Expected in-degree distribution (Log-Log)")
        ax1.set_xlabel("In-degree")
        ax1.set_ylabel("Number of account vertices")

        ax2.loglog(out_deg_seq, out_deg_hist, "ro-")
        ax2.set_title("Expected out-degree distribution (Log-Log)")
        ax2.set_xlabel("Out-degree")
        ax2.set_ylabel("Number of account vertices")

        ax3.loglog(in_deg_seq, in_deg_hist, "bo-")
        ax3.set_title("Output in-degree distribution (Log-Log)")
        ax3.set_xlabel("In-degree")
        ax3.set_ylabel("Number of account vertices")

        ax4.loglog(out_deg_seq, out_deg_hist, "ro-")
        ax4.set_title("Output out-degree distribution (Log-Log)")
        ax4.set_xlabel("Out-degree")
        ax4.set_ylabel("Number of account vertices")

        plt.tight_layout()
        plt.savefig(log_log_plot_img)


def plot_wcc_distribution(_g, _plot_img):
    """Plot weakly connected components size distributions
    :param _g: Transaction graph
    :param _plot_img: WCC size distribution image (log-log plot)
    :return:
    """
    all_wcc = nx.weakly_connected_components(_g)
    wcc_sizes = Counter([len(wcc) for wcc in all_wcc])
    size_seq = sorted(wcc_sizes.keys())
    size_hist = [wcc_sizes[x] for x in size_seq]

    plt.figure(figsize=(16, 12))
    plt.clf()
    plt.loglog(size_seq, size_hist, 'ro-')
    plt.title("WCC Size Distribution")
    plt.xlabel("Size")
    plt.ylabel("Number of WCCs")
    plt.savefig(_plot_img)


def plot_alert_stat(_alert_acct_csv, _alert_tx_csv, _schema, _plot_img):
    from collections import Counter, defaultdict
    import numpy as np
    import matplotlib.pyplot as plt
    from datetime import datetime

    alert_member_count = Counter()
    alert_tx_count = Counter()
    alert_init_amount = dict()  # Initial amount
    alert_amount_list = defaultdict(list)  # All amount list
    alert_dates = defaultdict(list)
    alert_sar_flag = defaultdict(bool)
    alert_types = dict()
    label_alerts = defaultdict(list)  # label -> alert IDs

    alert_idx = None
    amt_idx = None
    date_idx = None
    type_idx = None
    sar_idx = None

    acct_schema = _schema["alert_member"]
    for i, col in enumerate(acct_schema):
        data_type = col.get("dataType")
        if data_type == "alert_id":
            alert_idx = i
        elif data_type == "alert_type":
            type_idx = i
        elif data_type == "sar_flag":
            sar_idx = i

    # Lê alert_accounts.csv
    with open(_alert_acct_csv, "r") as _rf:
        reader = csv.reader(_rf)
        header = next(reader)
        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue  # Ignora linhas vazias
            if len(row) < len(header):
                continue  # Ignora linhas incompletas
            alert_id = row[alert_idx]
            alert_type = row[type_idx]
            is_sar = row[sar_idx].lower() == "true"
            alert_member_count[alert_id] += 1
            alert_sar_flag[alert_id] = is_sar
            alert_types[alert_id] = alert_type
            label = ("SAR" if is_sar else "Normal") + ":" + alert_type
            label_alerts[label].append(alert_id)

    tx_schema = _schema["alert_tx"]
    for i, col in enumerate(tx_schema):
        data_type = col.get("dataType")
        if data_type == "alert_id":
            alert_idx = i
        elif data_type == "amount":
            amt_idx = i
        elif data_type == "timestamp":
            date_idx = i

    # Lê alert_transactions.csv
    with open(_alert_tx_csv, "r") as _rf:
        reader = csv.reader(_rf)
        header = next(reader)
        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue  # Ignora linhas vazias
            if len(row) < len(header):
                continue  # Ignora linhas incompletas
            alert_id = row[alert_idx]
            amount = float(row[amt_idx])
            date_str = row[date_idx].split("T")[0]
            date = datetime.strptime(date_str, "%Y-%m-%d")
            alert_tx_count[alert_id] += 1
            if alert_id not in alert_init_amount:
                alert_init_amount[alert_id] = amount
            alert_amount_list[alert_id].append(amount)
            alert_dates[alert_id].append(date)

    # Scatter plot para todos os alerts (apenas os que têm transação)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 12))
    cmap = plt.get_cmap("tab10")
    for i, (label, alerts) in enumerate(label_alerts.items()):
        color = cmap(i)
        # Só inclui alertas que têm transação registrada
        valid_alerts = [a for a in alerts if a in alert_init_amount and a in alert_tx_count and a in alert_dates]
        if not valid_alerts:
            continue
        x = [alert_member_count[a] for a in valid_alerts]
        y_init = np.array([alert_init_amount[a] for a in valid_alerts])
        ax1.scatter(x, y_init, s=50, color=color, label=label, edgecolors="none")
        for j, alert_id in enumerate(valid_alerts):
            ax1.annotate(alert_id, (x[j], y_init[j]))
        x2 = [alert_tx_count[a] for a in valid_alerts]
        y_period = [(max(alert_dates[a]) - min(alert_dates[a])).days + 1 for a in valid_alerts]
        ax2.scatter(x2, y_period, s=100, color=color, label=label, edgecolors="none")
        for j, alert_id in enumerate(valid_alerts):
            ax2.annotate(alert_id, (x2[j], y_period[j]))

    ax1.set_xlabel("Number of accounts per alert")
    ax1.set_ylabel("Initial transaction amount")
    ax1.legend()
    ax2.set_xlabel("Number of transactions per alert")
    ax2.set_ylabel("Transaction period")
    ax2.legend()
    plt.savefig(_plot_img)


def plot_aml_rule(aml_csv, _plot_img):
    """Plot the number of AML typologies
    :param aml_csv: AML typology pattern parameter CSV file
    :param _plot_img: Output image file (bar plot)
    """
    aml_types = Counter()
    num_idx = None
    type_idx = None

    if not os.path.isfile(aml_csv):
        print("AML typology file %s is not found." % aml_csv)
        return

    with open(aml_csv, "r") as _rf:
        reader = csv.reader(_rf)
        header = next(reader)
        for i, k in enumerate(header):
            if k == "count":
                num_idx = i
            elif k == "type":
                type_idx = i

        for row in reader:
            if "#" in row[0]:
                continue
            num = int(row[num_idx])
            aml_type = row[type_idx]
            aml_types[aml_type] += num

    x = list()
    y = list()
    for aml_type, num in aml_types.items():
        x.append(aml_type)
        y.append(num)

    plt.figure(figsize=(16, 12))
    plt.clf()
    plt.bar(range(len(x)), y, tick_label=x)
    plt.title("AML typologies")
    plt.xlabel("Typology name")
    plt.ylabel("Number of patterns")
    plt.savefig(_plot_img)


def plot_tx_count(_g, _plot_img):
    """Plot the number of normal and SAR transactions
    :param _g: Transaction graph
    :param _plot_img: Output image file path
    """
    date_list = get_date_list(_g)
    normal_tx_count = Counter()
    sar_tx_count = Counter()

    for _, _, attr in _g.edges(data=True):
        is_sar = attr["is_sar"]
        date = attr["date"]
        if is_sar:
            sar_tx_count[date] += 1
        else:
            normal_tx_count[date] += 1

    normal_tx_list = [normal_tx_count[d] for d in date_list]
    sar_tx_list = [sar_tx_count[d] for d in date_list]

    plt.figure(figsize=(16, 12))
    plt.clf()
    p_n = plt.plot(date_list, normal_tx_list, "b")
    p_f = plt.plot(date_list, sar_tx_list, "r")
    plt.yscale('log')
    plt.legend((p_n[0], p_f[0]), ("Normal", "SAR"))
    plt.title("Number of transactions per step")
    plt.xlabel("Simulation step")
    plt.ylabel("Number of transactions")
    plt.savefig(_plot_img)


def plot_clustering_coefficient(_g, _plot_img, interval=30):
    """Plot the clustering coefficient transition
    :param _g: Transaction graph
    :param _plot_img: Output image file
    :param interval: Simulation step interval for plotting
    (it takes too much time to compute clustering coefficient)
    :return:
    """
    date_list = get_date_list(_g)

    gg = nx.Graph()
    edges = defaultdict(list)
    for k, v in nx.get_edge_attributes(_g, "date").items():
        e = (k[0], k[1])
        edges[v].append(e)

    sample_dates = list()
    values = list()
    for i, t in enumerate(date_list):
        gg.add_edges_from(edges[t])
        if i % interval == 0:
            v = nx.average_clustering(gg) if gg.number_of_nodes() else 0.0
            sample_dates.append(t)
            values.append(v)
            print("Clustering coefficient at %s: %f" % (str(t), v))

    plt.figure(figsize=(16, 12))
    plt.clf()
    plt.plot(sample_dates, values, 'bo-')
    plt.title("Clustering Coefficient Transition")
    plt.xlabel("date")
    plt.ylabel("Clustering Coefficient")
    plt.savefig(_plot_img)


def plot_diameter(dia_csv, _plot_img):
    """Plot the diameter and the average of largest distance transitions
    :param dia_csv: Diameter transition CSV file
    :param _plot_img: Output image file
    :return:
    """
    x = list()
    dia = list()
    aver = list()

    with open(dia_csv, "r") as _rf:
        reader = csv.reader(_rf)
        next(reader)
        for row in reader:
            step = int(row[0])
            d = float(row[1])
            a = float(row[2])
            x.append(step)
            dia.append(d)
            aver.append(a)

    plt.figure(figsize=(16, 12))
    plt.clf()
    plt.ylim(0, max(dia) + 1)
    p_d = plt.plot(x, dia, "r")
    p_a = plt.plot(x, aver, "b")
    plt.legend((p_d[0], p_a[0]), ("Diameter", "Average"))
    plt.title("Diameter and Average Distance")
    plt.xlabel("Simulation step")
    plt.ylabel("Distance")
    plt.savefig(_plot_img)


def plot_bank2bank_count(_g: nx.MultiDiGraph, _plot_img: str):
    acct_bank = nx.get_node_attributes(_g, "bank_id")
    bank_list = sorted(set(acct_bank.values()))
    bank2bank_all = Counter()
    bank2bank_sar = Counter()

    for orig, bene, attr in _g.edges(data=True):
        orig_bank = acct_bank[orig]
        bene_bank = acct_bank[bene]
        is_sar = attr["is_sar"]
        bank_pair = (orig_bank, bene_bank)
        bank2bank_all[bank_pair] += 1
        if is_sar:
            bank2bank_sar[bank_pair] += 1

    total_num = _g.number_of_edges()
    internal_num = sum([num for pair, num in bank2bank_all.items() if pair[0] == pair[1]])
    external_num = total_num - internal_num
    internal_ratio = internal_num / total_num * 100
    external_ratio = external_num / total_num * 100
    internal_sar_num = sum([num for pair, num in bank2bank_sar.items() if pair[0] == pair[1]])
    external_sar_num = sum([num for pair, num in bank2bank_sar.items() if pair[0] != pair[1]])

    all_count_data = list()
    sar_count_data = list()
    for orig_bank in bank_list:
        all_count_row = [bank2bank_all[(orig_bank, bene_bank)] for bene_bank in bank_list]
        all_count_total = sum(all_count_row)
        all_count_data.append(all_count_row + [all_count_total])
        sar_count_row = [bank2bank_sar[(orig_bank, bene_bank)] for bene_bank in bank_list]
        sar_count_total = sum(sar_count_row)
        sar_count_data.append(sar_count_row + [sar_count_total])

    all_count_total = list()
    sar_count_total = list()
    for bene_bank in bank_list:
        all_count_total.append(sum([bank2bank_all[(orig_bank, bene_bank)] for orig_bank in bank_list]))
        sar_count_total.append(sum([bank2bank_sar[(orig_bank, bene_bank)] for orig_bank in bank_list]))
    all_count_total.append(sum(all_count_total))
    sar_count_total.append(sum(sar_count_total))

    all_count_data.append(all_count_total)
    sar_count_data.append(sar_count_total)

    all_count_csv = list()
    sar_count_csv = list()
    for row in all_count_data:
        all_count_csv.append(["{:,}".format(num) for num in row])
    for row in sar_count_data:
        sar_count_csv.append(["{:,}".format(num) for num in row])

    cols = ["To: %s" % bank for bank in bank_list] + ["Total"]
    rows = ["From: %s" % bank for bank in bank_list] + ["Total"]

    fig, (ax1, ax2) = plt.subplots(nrows=2, figsize=(9, 6))
    table_attr = {"rowLabels": rows, "colLabels": cols, "colWidths": [0.15 for _ in cols],
                  "loc": "center", "bbox": [0.15, 0.3, 0.75, 0.6]}
    ax1.axis("off")
    ax1.table(cellText=all_count_csv, **table_attr)
    ax1.set_title("Number of all bank-to-bank transactions")

    ax2.axis("off")
    ax2.table(cellText=sar_count_csv, **table_attr)
    ax2.set_title("Number of SAR bank-to-bank transactions")

    fig.suptitle("Internal bank transactions: Total = {:,} ({:.2f}%), SAR = {:,}".
                 format(internal_num, internal_ratio, internal_sar_num) + "\n" +
                 "External bank transactions: Total = {:,} ({:.2f}%), SAR = {:,}"
                 .format(external_num, external_ratio, external_sar_num),
                 y=0.1)
    plt.tight_layout()
    fig.savefig(_plot_img)


if __name__ == "__main__":
    argv = sys.argv

    if len(argv) < 2:
        print("Usage: python3 %s [ConfJSON]" % argv[0])
        exit(1)

    conf_json = argv[1]
    with open(conf_json, "r") as rf:
        conf = json.load(rf)

    input_dir = conf["input"]["directory"]
    schema_json = conf["input"]["schema"]
    schema_path = os.path.join(input_dir, schema_json)

    with open(schema_path, "r") as rf:
        schema = json.load(rf)

    sim_name = argv[2] if len(argv) >= 3 else conf["general"]["simulation_name"]
    work_dir = os.path.join(conf["output"]["directory"], sim_name)
    acct_csv = conf["output"]["accounts"]
    tx_csv = conf["output"]["transactions"]
    acct_path = os.path.join(work_dir, acct_csv)
    tx_path = os.path.join(work_dir, tx_csv)

    tmp_dir = conf["temporal"]["directory"]
    output_dir = conf["output"]["directory"]
    if not os.path.exists(tx_path):
        print("Transaction list CSV file %s not found." % tx_path)
        exit(1)

    print("Constructing transaction graph")
    g = construct_graph(acct_path, tx_path, schema)

    v_conf = conf["visualizer"]
    deg_plot = v_conf["degree"]
    wcc_plot = v_conf["wcc"]
    alert_plot = v_conf["alert"]
    count_plot = v_conf["count"]
    cc_plot = v_conf["clustering"]
    dia_plot = v_conf["diameter"]
    b2b_plot = "bank2bank.png"

    print("Plot degree distributions")
    plot_degree_distribution(
        g, 
        conf, 
        os.path.join(work_dir, deg_plot), 
        log_log_plot_img=os.path.join(work_dir, "log_log_degree_distribution.png")
    )

    print("Plot weakly connected component size distribution")
    plot_wcc_distribution(g, os.path.join(work_dir, wcc_plot))

    param_dir = conf["input"]["directory"]
    alert_param_file = conf["input"]["alert_patterns"]
    param_path = os.path.join(param_dir, alert_param_file)
    plot_path = os.path.join(work_dir, alert_plot)
    print("Plot AML typology count")
    plot_aml_rule(param_path, plot_path)

    alert_acct_csv = conf["output"]["alert_members"]
    alert_tx_csv = conf["output"]["alert_transactions"]
    alert_acct_path = os.path.join(work_dir, alert_acct_csv)
    alert_tx_path = os.path.join(work_dir, alert_tx_csv)

    print("Plot alert attribute distributions")
    plot_alert_stat(alert_acct_path, alert_tx_path, schema, os.path.join(work_dir, "alert_dist.png"))

    print("Plot transaction count per date")
    plot_tx_count(g, os.path.join(work_dir, count_plot))

    #print("Plot clustering coefficient of the transaction graph")
    #plot_clustering_coefficient(g, os.path.join(work_dir, cc_plot))

    dia_log = conf["output"]["diameter_log"]
    dia_path = os.path.join(work_dir, dia_log)
    if os.path.exists(dia_path):
        plot_img = os.path.join(work_dir, dia_plot)
        print("Plot diameter of the transaction graph")
        plot_diameter(dia_path, plot_img)
    else:
        print("Diameter log file %s not found." % dia_path)

    print("Plot bank-to-bank transaction counts")
    plot_bank2bank_count(g, os.path.join(work_dir, b2b_plot))

    print("Plot transaction amount vs count correlation")
    tx_corr_plot = "tx_correlation.png"
    plot_transaction_correlation(g, os.path.join(work_dir, tx_corr_plot))

    plot_strength_distributions(g, os.path.join(work_dir, "strength_ccdf.png"))

    plot_clustering_vs_degree(g, os.path.join(work_dir, "clustering_vs_degree.png"))