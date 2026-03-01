import networkx as nx
from app.services.osm_graph import approx_meters

def nearest_node(G, lat, lon):
    target = (lat, lon)
    best = None
    best_d = 1e18
    for node in G.nodes:
        d = approx_meters(node, target)
        if d < best_d:
            best_d = d
            best = node
    return best

def compute_route(G, start_lat, start_lon, end_lat, end_lon, outdoor_penalty=1.0):
    s = nearest_node(G, start_lat, start_lon)
    t = nearest_node(G, end_lat, end_lon)

    def weight(u, v, attrs):
        meters = attrs.get("meters", 1.0)
        outdoors = attrs.get("outdoors", True)
        return meters * outdoor_penalty if outdoors else meters

    path = nx.astar_path(G, s, t, heuristic=lambda a, b: approx_meters(a, b), weight=weight)

    total_m = 0.0
    outdoor_m = 0.0
    coords = []
    for i in range(len(path)):
        coords.append({"lat": path[i][0], "lon": path[i][1]})
        if i < len(path) - 1:
            attrs = G.get_edge_data(path[i], path[i+1])
            meters = attrs.get("meters", 0.0)
            total_m += meters
            if attrs.get("outdoors", True):
                outdoor_m += meters

    return {"coords": coords, "total_meters": total_m, "outdoor_meters": outdoor_m}