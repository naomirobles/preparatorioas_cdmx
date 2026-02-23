import geopandas as gpd
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree
# Construir grafo y verificar
from script_python_crear_rutas import calles_to_graph, build_kdtree, nearest_node  # ajusta el import

# Cargar y reproyectar
calles = gpd.read_file("capas_auxiliares/CALLES.gpkg", layer="calles").to_crs(epsg=6369)
prepas = gpd.read_file("capas_prepas/MEDIA_SUPERIOR_PUBLICA.gpkg", layer="media_superior_publica")  # ya en 6369
transporte = gpd.read_file("capas_auxiliares/todos_los_sistemas_de_transporte.gpkg", layer="transporte").to_crs(epsg=6369)
perimetros = gpd.read_file("capas_prepas/perimetros_prepas.gpkg", layer="perimetros_prepas").to_crs(epsg=6369)

# Tomar UN solo perímetro para prueba
perim = perimetros.iloc[0]
print("Perímetro ID:", perim["ID_CARTO"])
print("Perímetro bounds:", perim.geometry.bounds)

# Buscar prepa correspondiente
match = prepas[prepas["ID-CARTO"].str.strip() == perim["ID_CARTO"].strip()]
print("\nPrepa encontrada:", len(match), "resultados")
if match.empty:
    print("IDs en perimetros:", perimetros["ID_CARTO"].head(5).tolist())
    print("IDs en prepas:", prepas["ID-CARTO"].head(5).tolist())
else:
    prepa = match.iloc[0]
    print("Centroide prepa:", prepa.geometry.centroid)

# Transportes dentro del perímetro
transportes_cercanos = transporte[transporte.within(perim.geometry)]
print("\nTransportes dentro del perímetro:", len(transportes_cercanos))
if transportes_cercanos.empty:
    # Ver cuántos hay cerca aunque no estén dentro
    buffer_grande = perim.geometry.buffer(1000)
    transportes_buffer = transporte[transporte.within(buffer_grande)]
    print("Transportes en buffer 1km:", len(transportes_buffer))

# Calles que intersectan el perímetro extendido
area_extendida = perim.geometry.buffer(500)
calles_clip = calles[calles.intersects(area_extendida)].copy()
calles_clip = calles_clip.explode(index_parts=False).reset_index(drop=True)
print("\nCalles en el área:", len(calles_clip))
print("Bounds del área:", area_extendida.bounds)



G = calles_to_graph(calles_clip)
print("\nNodos en grafo:", G.number_of_nodes())
print("Aristas en grafo:", G.number_of_edges())
componentes = nx.number_connected_components(G)
print("Componentes conexas:", componentes)

# Ver si prepa y transporte caen cerca de algún nodo
if not match.empty and G.number_of_nodes() > 0:
    tree, nodes = build_kdtree(G)
    centroide_prepa = prepa.geometry.centroid
    nodo_dest = nearest_node(G, centroide_prepa, tree, nodes)
    print("\nNodo más cercano a prepa:", nodo_dest)
    dist_prepa = centroide_prepa.distance(gpd.GeoSeries([gpd.points_from_xy([nodo_dest[0]], [nodo_dest[1]])[0]], crs=calles.crs).iloc[0])
    print("Distancia prepa → nodo más cercano (m):", dist_prepa)

    if not transportes_cercanos.empty:
        punto = transportes_cercanos.iloc[0]
        nodo_orig = nearest_node(G, punto.geometry.centroid, tree, nodes)
        print("Nodo más cercano a transporte:", nodo_orig)
        
        print("\n¿Existe ruta?", nx.has_path(G, nodo_orig, nodo_dest))
        try:
            path = nx.shortest_path(G, nodo_orig, nodo_dest, weight="length")
            print("Ruta encontrada con", len(path), "nodos")
        except nx.NetworkXNoPath:
            print("SIN RUTA - nodos en distintas componentes")
            comp_orig = None
            comp_dest = None
            for i, comp in enumerate(nx.connected_components(G)):
                if nodo_orig in comp:
                    comp_orig = i
                if nodo_dest in comp:
                    comp_dest = i
            print(f"  Transporte en componente: {comp_orig}")
            print(f"  Prepa en componente: {comp_dest}")