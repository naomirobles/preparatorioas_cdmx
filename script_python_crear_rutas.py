import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge
from scipy.spatial import cKDTree
import numpy as np

def calles_to_graph(calles_gdf):
    G = nx.Graph()
    for idx, row in calles_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == 'MultiLineString':
            segmentos = list(geom.geoms)
        elif geom.geom_type == 'LineString':
            segmentos = [geom]
        else:
            continue
        for segmento in segmentos:
            coords = list(segmento.coords)
            start = coords[0]
            end = coords[-1]
            length = segmento.length
            G.add_node(start, x=start[0], y=start[1])
            G.add_node(end, x=end[0], y=end[1])
            G.add_edge(start, end, weight=length, length=length, geometry=segmento, edge_id=idx)
    return G

def build_kdtree(G):
    nodes = list(G.nodes())
    coords = np.array([(x, y) for x, y in nodes])
    tree = cKDTree(coords)
    return tree, nodes

def nearest_node(G, point, tree=None, nodes=None):
    if tree is None:
        tree, nodes = build_kdtree(G)
    coord = np.array([[point.x, point.y]])
    _, idx = tree.query(coord)
    return nodes[idx[0]]



if __name__ == "__main__":
    calles    = gpd.read_file("capas_auxiliares/CALLES.gpkg", layer="CALLES").to_crs(epsg=6369)
    prepas    = gpd.read_file("capas_prepas/MEDIA_SUPERIOR_PUBLICA.gpkg", layer="media_superior_publica")
    transporte = gpd.read_file("capas_auxiliares/todos_los_sistemas_de_transporte.gpkg", layer="transporte").to_crs(epsg=6369)
    perimetros = gpd.read_file("capas_prepas/buffers_800m.gpkg", layer="buffers").to_crs(epsg=6369)

    output_path = r"C:/Users/naomi/proyectos/c5/preparatorioas_cdmx/rutas_output.gpkg"
    total_rutas = 0
    todas_las_rutas = []

    for idx, perim in perimetros.iterrows():
        match = prepas[prepas["ID-CARTO"] == perim["ID-CARTO"]]
        if match.empty:
            print(f"Sin prepa para perímetro: {perim['ID-CARTO']}")
            continue
        prepa = match.iloc[0]

        transportes_cercanos = transporte[transporte.within(perim.geometry)]
        if transportes_cercanos.empty:
            continue

        area_extendida = perim.geometry.buffer(1000)
        calles_clip = calles[calles.intersects(area_extendida)].copy()
        calles_clip = calles_clip.explode(index_parts=False).reset_index(drop=True)

        G = calles_to_graph(calles_clip)
        if G.number_of_nodes() == 0:
            print(f"Grafo vacío: {perim['ID-CARTO']}")
            continue

        tree, nodes = build_kdtree(G)
        nodo_destino = nearest_node(G, prepa.geometry.centroid, tree, nodes)
        rutas = []

        for _, punto in transportes_cercanos.iterrows():
            nodo_origen = nearest_node(G, punto.geometry.centroid, tree, nodes)
            try:
                path = nx.shortest_path(G, nodo_origen, nodo_destino, weight="length")
                lineas = [G[path[i]][path[i+1]]['geometry'] for i in range(len(path)-1)]
                ruta_geom = linemerge(lineas)
                rutas.append({
                    "prepa_id":         perim["ID-CARTO"],
                    "prepa_nombre":     prepa["NOMBRE_POI"],
                    "institucion":      prepa["SUBCLACIFICACION"],
                    "transporte_id":    punto["ID_CARTO"],
                    "tipo_transporte":  punto["POI"],
                    "nombre_transporte": punto["NOMBRE_POI"],
                    "distancia_m":      sum(G[path[i]][path[i+1]]['length'] for i in range(len(path)-1)),
                    "geometry":         ruta_geom
                })
            except nx.NetworkXNoPath:
                print(f"Sin ruta: {punto['NOMBRE_POI']} → {perim['NOMBRE_POI']}")

        # ✅ DENTRO del loop — guardar por prepa
        if rutas:
            todas_las_rutas.extend(rutas)
            print(f"[{idx+1}/{len(perimetros)}] {perim['ID-CARTO']}: {len(rutas)} rutas")
            

    # ✅ FUERA del loop — guardar TODO junto
    # Después del loop
    if todas_las_rutas:
        gdf_final = gpd.GeoDataFrame(todas_las_rutas, crs=calles.crs)
        gdf_final.to_file(
            r"C:/Users/naomi/proyectos/c5/preparatorioas_cdmx/rutas_unidas_v2.gpkg",
            layer="todas_las_rutas",
            driver="GPKG"
        )
        print(f"\nTerminado. Total rutas guardadas: {len(gdf_final)}")

