import requests
import networkx as nx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def approx_meters(a, b):
    (lat1, lon1), (lat2, lon2) = a, b
    dlat = (lat2 - lat1) * 111_000
    dlon = (lon2 - lon1) * 85_000
    return (dlat**2 + dlon**2) ** 0.5

def fetch_walkways_overpass(bbox: str):
    s, w, n, e = bbox.split(",")
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"~"footway|path|pedestrian|steps"]({s},{w},{n},{e});
    );
    out geom;
    """
    r = requests.post(OVERPASS_URL, data=query, timeout=35)
    r.raise_for_status()
    return r.json()

def fetch_buildings_and_entrances_overpass(bbox: str):
        """Fetch building footprints (ways/relations) and entrance nodes within bbox."""
        s, w, n, e = bbox.split(",")
        query = f"""
        [out:json][timeout:25];
        (
            way["building"]({s},{w},{n},{e});
            relation["building"]({s},{w},{n},{e});
            node["entrance"]({s},{w},{n},{e});
            node["door"]({s},{w},{n},{e});
        );
        out geom;
        """
        r = requests.post(OVERPASS_URL, data=query, timeout=35)
        r.raise_for_status()
        return r.json()

def build_graph_from_overpass(data):
    G = nx.Graph()
    for el in data.get("elements", []):
        if el.get("type") != "way":
            continue
        geom = el.get("geometry", [])
        for i in range(len(geom) - 1):
            a = (geom[i]["lat"], geom[i]["lon"])
            b = (geom[i+1]["lat"], geom[i+1]["lon"])
            dist = approx_meters(a, b)
            G.add_node(a)
            G.add_node(b)
            G.add_edge(a, b, meters=dist, outdoors=True)
    return G

def fallback_demo_graph():
    G = nx.Graph()
    pts = [
        (40.8202, -96.7009),  # Union
        (40.8197, -96.7020),  # Love
        (40.8194, -96.7026),  # Hawks
        (40.8187, -96.7008),  # Kauffman
    ]
    for p in pts:
        G.add_node(p)
    edges = [(pts[0], pts[1]), (pts[1], pts[2]), (pts[0], pts[3]), (pts[3], pts[2])]
    for a, b in edges:
        G.add_edge(a, b, meters=approx_meters(a, b), outdoors=True)
    return G