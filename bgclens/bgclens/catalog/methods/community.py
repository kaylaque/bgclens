"""Louvain community detection for GCF networks."""
from typing import Any
from bgclens.model import NetworkEdgeList


def run(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    try:
        import networkx as nx
        import community as community_louvain
    except ImportError:
        return {
            "error": "networkx and python-louvain are required. Install with: pip install 'bgclens[network]'"
        }

    net: NetworkEdgeList = inputs["network"]
    resolution: float = float(params.get("resolution", 1.0))
    seed: int = int(params.get("seed", 42))

    G = nx.Graph()
    G.add_nodes_from(net.nodes)
    for src, dst, w in net.edges:
        G.add_edge(src, dst, weight=w)

    partition = community_louvain.best_partition(G, resolution=resolution, random_state=seed)
    modularity = community_louvain.modularity(partition, G)

    n_communities = len(set(partition.values()))
    community_sizes: dict[int, int] = {}
    for node, comm in partition.items():
        community_sizes[comm] = community_sizes.get(comm, 0) + 1

    return {
        "method": "louvain_community",
        "n_nodes": len(net.nodes),
        "n_edges": len(net.edges),
        "n_communities": n_communities,
        "modularity": float(modularity),
        "partition": partition,
        "community_sizes": community_sizes,
        "resolution": resolution,
    }


def check_assumptions(inputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
    warnings = []
    net: NetworkEdgeList | None = inputs.get("network")
    if net is None:
        warnings.append("No NetworkEdgeList provided.")
        return warnings
    if len(net.nodes) < 4:
        warnings.append(f"Only {len(net.nodes)} nodes — community detection is trivial.")
    if not net.edges:
        warnings.append(
            "Network has no edges — community detection will produce isolated singletons."
        )
    return warnings


def cost(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    net: NetworkEdgeList | None = inputs.get("network")
    if net is None:
        return {"class": "Safe", "reason": "No data", "estimated_mb": 0.0}
    n = len(net.nodes)
    e = len(net.edges)
    mb = (n + e) * 16 / 1e6
    cls = "Safe" if n <= 5000 else "Heavy"
    return {
        "class": cls,
        "reason": f"N={n} nodes, {e} edges ({mb:.1f} MB)",
        "estimated_mb": mb,
    }
