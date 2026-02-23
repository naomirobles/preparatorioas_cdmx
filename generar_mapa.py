"""
generar_mapa.py
Genera un mapa HTML interactivo con filtros por alcaldía e institución.
Uso: python generar_mapa.py
Salida: mapa_prepas_cdmx.html
"""

import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping
import sys
import os

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
PREPAS_GPKG     = "capas_prepas/MEDIA_SUPERIOR_PUBLICA.gpkg"
PREPAS_LAYER    = "media_superior_publica"
PERIMETROS_GPKG = "capas_prepas/perimetros_prepas.gpkg"
PERIMETROS_LAYER= "perimetros_prepas"
TRANSPORTE_GPKG = "capas_auxiliares/todos_los_sistemas_de_transporte.gpkg"
TRANSPORTE_LAYER= "transporte"
RUTAS_GPKG      = "rutas_unidas_v2.gpkg"
RUTAS_LAYER     = "todas_las_rutas"
OUTPUT_HTML     = "mapa_prepas_cdmx.html"
# ──────────────────────────────────────────────────────────────────────────────

def load_layer(path, layer, target_crs="EPSG:4326"):
    print(f"  Cargando {layer}...")
    gdf = gpd.read_file(path, layer=layer)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf

def gdf_to_geojson(gdf, properties):
    """Convierte un GDF a dict GeoJSON incluyendo solo las columnas indicadas."""
    features = []
    for _, row in gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        props = {k: (str(row[k]) if pd.notna(row.get(k)) else "") for k in properties if k in row}
        features.append({
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": props
        })
    return {"type": "FeatureCollection", "features": features}

def main():
    print("Cargando capas...")

    prepas     = load_layer(PREPAS_GPKG,     PREPAS_LAYER)
    perimetros = load_layer(PERIMETROS_GPKG, PERIMETROS_LAYER)
    transporte = load_layer(TRANSPORTE_GPKG, TRANSPORTE_LAYER)
    rutas          = load_layer(RUTAS_GPKG,      RUTAS_LAYER)
    alcaldias_cdmx = load_layer("capas_auxiliares/ALCALDIAS.gpkg", "ALCALDIAS")

    # Conteo de transportes por prepa (para popup)
    conteo = rutas.groupby("prepa_id")["nombre_transporte"].nunique().reset_index()
    conteo.columns = ["ID-CARTO", "num_transportes"]
    prepas = prepas.merge(conteo, on="ID-CARTO", how="left")
    prepas["num_transportes"] = prepas["num_transportes"].fillna(0).astype(int)

    # Listas únicas para filtros
    alcaldias    = sorted(prepas["sector"].dropna().unique().tolist())
    instituciones = sorted(prepas["SUBCLACIFICACION"].dropna().unique().tolist())

    print("Serializando GeoJSON...")

    prepas_props     = ["ID-CARTO", "NOMBRE_POI", "sector", "SUBCLACIFICACION", "num_transportes"]
    perimetros_props = ["ID_CARTO", "NOMBRE_POI"]
    transporte_props = ["ID_CARTO", "NOMBRE_POI", "POI", "SUBCLACIFICACION", "ESPECIALID"]
    rutas_props      = ["prepa_id", "prepa_nombre", "nombre_transporte", "tipo_transporte", "distancia_m"]

    geojson_alcaldias_cdmx = json.dumps(gdf_to_geojson(alcaldias_cdmx, [alcaldias_cdmx.columns[0]]), ensure_ascii=False)
    geojson_prepas     = json.dumps(gdf_to_geojson(prepas,     prepas_props),     ensure_ascii=False)
    geojson_perimetros = json.dumps(gdf_to_geojson(perimetros, perimetros_props), ensure_ascii=False)
    geojson_transporte = json.dumps(gdf_to_geojson(transporte, transporte_props), ensure_ascii=False)
    geojson_rutas      = json.dumps(gdf_to_geojson(rutas,      rutas_props),      ensure_ascii=False)

    alcaldias_json     = json.dumps(alcaldias,     ensure_ascii=False)
    instituciones_json = json.dumps(instituciones, ensure_ascii=False)

    print("Generando HTML...")

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Preparatorias CDMX — C5</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {{
    --bg:        #0d0f14;
    --panel:     #13161e;
    --border:    #252a36;
    --accent:    #00e5ff;
    --accent2:   #ff4d6d;
    --accent3:   #b8ff57;
    --text:      #e8ecf4;
    --muted:     #6b7280;
    --panel-w:   300px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; display: flex; height: 100vh; overflow: hidden; }}

  /* ── PANEL LATERAL ── */
  #panel {{
    width: var(--panel-w);
    min-width: var(--panel-w);
    background: var(--panel);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 1000;
  }}

  #panel-header {{
    padding: 20px 18px 14px;
    border-bottom: 1px solid var(--border);
  }}
  #panel-header .logo {{
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    color: var(--accent);
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 6px;
  }}
  #panel-header h1 {{
    font-size: 16px;
    font-weight: 600;
    line-height: 1.3;
    color: var(--text);
  }}
  #panel-header .subtitle {{
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
  }}

  #panel-body {{ flex: 1; overflow-y: auto; padding: 16px 18px; }}
  #panel-body::-webkit-scrollbar {{ width: 4px; }}
  #panel-body::-webkit-scrollbar-track {{ background: transparent; }}
  #panel-body::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}

  .section-title {{
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--accent);
    margin: 18px 0 10px;
  }}
  .section-title:first-child {{ margin-top: 0; }}

  /* capas toggle */
  .layer-toggle {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 0;
    cursor: pointer;
    user-select: none;
    border-bottom: 1px solid var(--border);
  }}
  .layer-toggle:last-child {{ border-bottom: none; }}
  .layer-toggle input[type=checkbox] {{ display: none; }}
  .toggle-box {{
    width: 28px; height: 16px;
    border-radius: 8px;
    background: var(--border);
    position: relative;
    transition: background .2s;
    flex-shrink: 0;
  }}
  .toggle-box::after {{
    content: '';
    position: absolute;
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--muted);
    top: 3px; left: 3px;
    transition: transform .2s, background .2s;
  }}
  .layer-toggle input:checked + .toggle-box {{ background: var(--accent); }}
  .layer-toggle input:checked + .toggle-box::after {{ transform: translateX(12px); background: #fff; }}
  .toggle-swatch {{
    width: 10px; height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
  }}
  .toggle-label {{ font-size: 13px; color: var(--text); flex: 1; }}

  /* filtros */
  .filter-group {{ margin-bottom: 8px; }}
  .filter-group-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    padding: 6px 0;
  }}
  .filter-group-header span {{ font-size: 12px; color: var(--text); }}
  .filter-group-header .arrow {{
    font-size: 10px;
    color: var(--muted);
    transition: transform .2s;
  }}
  .filter-group-header.open .arrow {{ transform: rotate(180deg); }}
  .filter-items {{
    display: none;
    max-height: 200px;
    overflow-y: auto;
    padding: 4px 0 8px 4px;
  }}
  .filter-items.open {{ display: block; }}
  .filter-items::-webkit-scrollbar {{ width: 3px; }}
  .filter-items::-webkit-scrollbar-thumb {{ background: var(--border); }}
  .filter-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    cursor: pointer;
    font-size: 12px;
    color: var(--muted);
    transition: color .15s;
  }}
  .filter-item:hover {{ color: var(--text); }}
  .filter-item input[type=checkbox] {{ accent-color: var(--accent); width: 13px; height: 13px; cursor: pointer; }}
  .filter-item.active {{ color: var(--text); }}

  .select-all {{
    font-size: 10px;
    color: var(--accent);
    cursor: pointer;
    padding: 2px 0 6px;
    display: inline-block;
    font-family: 'Space Mono', monospace;
  }}

  /* transport groups */
  .transport-group {{
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 6px;
    overflow: hidden;
  }}
  .tg-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    cursor: pointer;
    user-select: none;
    background: rgba(255,255,255,.02);
    transition: background .15s;
  }}
  .tg-header:hover {{ background: rgba(255,255,255,.05); }}
  .tg-dot {{
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }}
  .tg-label {{ font-size: 12px; color: var(--text); }}
  .tg-arrow {{ font-size: 9px; color: var(--muted); transition: transform .2s; }}
  .tg-arrow.open {{ transform: rotate(180deg); }}
  .tg-body {{
    padding: 6px 10px 8px;
    border-top: 1px solid var(--border);
    max-height: 180px;
    overflow-y: auto;
  }}
  .tg-body::-webkit-scrollbar {{ width: 3px; }}
  .tg-body::-webkit-scrollbar-thumb {{ background: var(--border); }}
  .trans-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
    cursor: pointer;
    font-size: 11px;
    color: var(--muted);
    transition: color .15s;
  }}
  .trans-item:hover {{ color: var(--text); }}
  .trans-item input {{ accent-color: var(--accent); width: 12px; height: 12px; cursor: pointer; }}
  .trans-item.active {{ color: var(--text); }}
  .trans-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }}

  /* estadísticas */
  #stats {{
    padding: 14px 18px;
    border-top: 1px solid var(--border);
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }}
  .stat-box {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px;
  }}
  .stat-value {{
    font-family: 'Space Mono', monospace;
    font-size: 20px;
    color: var(--accent);
    font-weight: 700;
  }}
  .stat-label {{
    font-size: 10px;
    color: var(--muted);
    margin-top: 2px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  /* ── MAPA ── */
  #map {{ flex: 1; }}
  .leaflet-container {{ background: #0a0c10 !important; }}

  /* popup */
  .leaflet-popup-content-wrapper {{
    background: var(--panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,.6) !important;
    color: var(--text) !important;
  }}
  .leaflet-popup-tip {{ background: var(--panel) !important; }}
  .popup-title {{
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 10px;
    line-height: 1.4;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
  }}
  .popup-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 3px 0;
    font-size: 11px;
    gap: 12px;
  }}
  .popup-key {{ color: var(--muted); flex-shrink: 0; }}
  .popup-val {{ color: var(--text); text-align: right; font-weight: 500; }}
  .popup-badge {{
    display: inline-block;
    background: rgba(0,229,255,.15);
    color: var(--accent);
    border: 1px solid rgba(0,229,255,.3);
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 10px;
    font-family: 'Space Mono', monospace;
  }}
</style>
</head>
<body>

<div id="panel">
  <div id="panel-header">
    <div class="logo">C5 · CDMX</div>
    <h1>Preparatorias &amp;<br>Transporte Público</h1>
    <div class="subtitle">Sistema de análisis cartográfico</div>
  </div>

  <div id="panel-body">

    <!-- CAPAS -->
    <div class="section-title">Capas</div>

    <label class="layer-toggle">
      <input type="checkbox" id="tog-prepas" checked>
      <div class="toggle-box"></div>
      <div class="toggle-swatch" style="background:#ff4d6d"></div>
      <span class="toggle-label">Polígonos prepas</span>
    </label>
    <label class="layer-toggle">
      <input type="checkbox" id="tog-perimetros" checked>
      <div class="toggle-box"></div>
      <div class="toggle-swatch" style="background:#00e5ff;opacity:.6"></div>
      <span class="toggle-label">Perímetros 3 cuadras</span>
    </label>
    <label class="layer-toggle">
      <input type="checkbox" id="tog-alcaldias" checked>
      <div class="toggle-box"></div>
      <div class="toggle-swatch" style="background:#4a90d9;opacity:.7"></div>
      <span class="toggle-label">Límites alcaldías</span>
    </label>
    <label class="layer-toggle">
      <input type="checkbox" id="tog-rutas" checked>
      <div class="toggle-box"></div>
      <div class="toggle-swatch" style="background:#b8ff57"></div>
      <span class="toggle-label">Rutas transporte→prepa</span>
    </label>
    <label class="layer-toggle">
      <input type="checkbox" id="tog-transporte" checked>
      <div class="toggle-box"></div>
      <div class="toggle-swatch" style="background:#ffd166"></div>
      <span class="toggle-label">Puntos de transporte</span>
    </label>

    <!-- FILTRO TRANSPORTE -->
    <div class="section-title">Filtrar transporte</div>

    <div class="transport-group" id="tg-metro">
      <div class="tg-header" onclick="toggleTG('metro')">
        <div style="display:flex;align-items:center;gap:8px">
          <div class="tg-dot" style="background:#ffd166"></div>
          <span class="tg-label">Metro</span>
        </div>
        <span class="tg-arrow" id="arr-metro">▼</span>
      </div>
      <div class="tg-body" id="tgb-metro">
        <span class="select-all" onclick="toggleTransType('metro',true);event.stopPropagation()">TODO</span>
        <span class="select-all" onclick="toggleTransType('metro',false);event.stopPropagation()" style="color:var(--muted);margin-left:8px">NINGUNO</span>
        <div id="filter-metro"></div>
      </div>
    </div>

    <div class="transport-group" id="tg-metrobus">
      <div class="tg-header" onclick="toggleTG('metrobus')">
        <div style="display:flex;align-items:center;gap:8px">
          <div class="tg-dot" style="background:#d41818"></div>
          <span class="tg-label">Metrobús</span>
        </div>
        <span class="tg-arrow" id="arr-metrobus">▼</span>
      </div>
      <div class="tg-body" id="tgb-metrobus">
        <span class="select-all" onclick="toggleTransType('metrobus',true);event.stopPropagation()">TODO</span>
        <span class="select-all" onclick="toggleTransType('metrobus',false);event.stopPropagation()" style="color:var(--muted);margin-left:8px">NINGUNO</span>
        <div id="filter-metrobus"></div>
      </div>
    </div>

    <div class="transport-group" id="tg-trolebus">
      <div class="tg-header" onclick="toggleTG('trolebus')">
        <div style="display:flex;align-items:center;gap:8px">
          <div class="tg-dot" style="background:#67d1f7"></div>
          <span class="tg-label">Trolebús</span>
        </div>
        <span class="tg-arrow" id="arr-trolebus">▼</span>
      </div>
      <div class="tg-body" id="tgb-trolebus" style="display:none">
        <div id="filter-trolebus"></div>
      </div>
    </div>

    <div class="transport-group" id="tg-cetrams">
      <div class="tg-header" onclick="toggleTG('cetrams')">
        <div style="display:flex;align-items:center;gap:8px">
          <div class="tg-dot" style="background:#039b94"></div>
          <span class="tg-label">CETRAMS</span>
        </div>
        <span class="tg-arrow" id="arr-cetrams">▼</span>
      </div>
      <div class="tg-body" id="tgb-cetrams" style="display:none">
        <div id="filter-cetrams"></div>
      </div>
    </div>

    <div class="transport-group" id="tg-cablebus">
      <div class="tg-header" onclick="toggleTG('cablebus')">
        <div style="display:flex;align-items:center;gap:8px">
          <div style="font-size:13px;color:#b57bee;line-height:1">★</div>
          <span class="tg-label">Cablebús</span>
        </div>
        <span class="tg-arrow" id="arr-cablebus">▼</span>
      </div>
      <div class="tg-body" id="tgb-cablebus" style="display:none">
        <div id="filter-cablebus"></div>
      </div>
    </div>

    <!-- FILTRO ALCALDÍA -->
    <div class="section-title">Filtrar por alcaldía</div>
    <span class="select-all" onclick="toggleAll('alcaldia', true)">SELEC. TODO</span>
    <div id="filter-alcaldias"></div>

    <!-- FILTRO INSTITUCIÓN -->
    <div class="section-title">Filtrar por institución</div>
    <span class="select-all" onclick="toggleAll('institucion', true)">SELEC. TODO</span>
    <div id="filter-instituciones"></div>

  </div>

  <div id="stats">
    <div class="stat-box">
      <div class="stat-value" id="stat-prepas">0</div>
      <div class="stat-label">Prepas visibles</div>
    </div>
    <div class="stat-box">
      <div class="stat-value" id="stat-rutas">0</div>
      <div class="stat-label">Rutas activas</div>
    </div>
  </div>
</div>

<div id="map"></div>

<script>
// ── DATOS ──────────────────────────────────────────────────────────────────
const DATA_ALCALDIAS   = {geojson_alcaldias_cdmx};
const DATA_PREPAS      = {geojson_prepas};
const DATA_PERIMETROS  = {geojson_perimetros};
const DATA_TRANSPORTE  = {geojson_transporte};
const DATA_RUTAS       = {geojson_rutas};
const ALCALDIAS        = {alcaldias_json};
const INSTITUCIONES    = {instituciones_json};

// ── MAPA ───────────────────────────────────────────────────────────────────
const map = L.map('map', {{
  center: [19.42, -99.13],
  zoom: 11,
  zoomControl: false
}});

L.control.zoom({{ position: 'topright' }}).addTo(map);

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  maxZoom: 19
}}).addTo(map);

// ── CAPA ALCALDÍAS ────────────────────────────────────────────────────────
const styleAlcaldia = {{ color:'#4a90d9', weight:1.5, fillColor:'transparent', fillOpacity:0, opacity:.5, dashArray:'6 3' }};
const layerAlcaldias = L.geoJSON(DATA_ALCALDIAS, {{ style: styleAlcaldia }}).addTo(map);

// ── ESTILOS ────────────────────────────────────────────────────────────────
const stylePrepa     = {{ color:'#ff4d6d', weight:1.5, fillColor:'#ff4d6d', fillOpacity:.25 }};
const stylePerimetro = {{ color:'#00e5ff', weight:1,   fillColor:'#00e5ff', fillOpacity:.05, dashArray:'4 4' }};
const styleRuta      = {{ color:'#b8ff57', weight:2,   opacity:.7 }};

// ── COLORES POR LÍNEA ─────────────────────────────────────────────────────
const METRO_COLORS = {{
  '1':'#f93eab','2':'#4686fb','3':'#c6d951','4':'#1be5b5',
  '5':'#fbf64d','6':'#fc2222','7':'#e39c00','8':'#11bc59',
  '9':'#996a1b','A':'#ac22de','B':'#b8b8b8','12':'#bcb08f'
}};
const METROBUS_COLORS = {{
  '1':'#d41818','2':'#b912cd','3':'#99d54e','4':'#f9640d',
  '5':'#08249d','6':'#ff2a9a','7':'#0b9d67'
}};
const TROLEBUS_COLOR = '#67d1f7';
const CETRAM_COLOR   = '#039b94';

function getTransColor(nombre, poi, especialid) {{
  const p = (poi       || '').toUpperCase();
  const e = (especialid|| '').toUpperCase().trim();
  if (p.includes('CABLEBUS')) return '#b57bee';
  if (p.includes('TROLEBUS')) return TROLEBUS_COLOR;
  if (p.includes('CETRAM'))   return CETRAM_COLOR;
  if (p.includes('METROBUS')) {{
    const m = e.match(/(\d+)/);
    return m ? (METROBUS_COLORS[m[1]] || '#d41818') : '#d41818';
  }}
  if (p.includes('METRO')) {{
    // ESPECIALID = "LINEA 1", "LINEA 12", "LINEA A", "LINEA B"
    const m = e.match(/LINEA\s+(\d{{1,2}}|[AB])/);
    return m ? (METRO_COLORS[m[1]] || '#ffd166') : '#ffd166';
  }}
  return '#aaaaaa';
}}

function getTransTypeKey(nombre, poi, especialid) {{
  const p = (poi       || '').toUpperCase();
  const e = (especialid|| '').toUpperCase().trim();
  if (p.includes('CABLEBUS')) return 'cablebus';
  if (p.includes('TROLEBUS')) return 'trolebus';
  if (p.includes('CETRAM'))   return 'cetrams';
  if (p.includes('METROBUS')) {{
    const m = e.match(/(\d+)/);
    return m ? 'metrobus-' + m[1] : 'metrobus';
  }}
  if (p.includes('METRO')) {{
    const m = e.match(/LINEA\s+(\d{{1,2}}|[AB])/);
    return m ? 'metro-' + m[1] : 'metro';
  }}
  return 'otro';
}}

function makeIcon(color, shape) {{
  if (shape === 'star') {{
    return L.divIcon({{
      html: `<div style="font-size:14px;line-height:1;filter:drop-shadow(0 0 4px ${{color}});color:${{color}};margin-top:-2px">★</div>`,
      className: '',
      iconSize: [14,14],
      iconAnchor: [7,7]
    }});
  }}
  return L.divIcon({{
    html: `<div style="width:10px;height:10px;border-radius:50%;background:${{color}};border:2px solid rgba(255,255,255,.35);box-shadow:0 0 7px ${{color}}90"></div>`,
    className: '',
    iconSize: [10,10],
    iconAnchor: [5,5]
  }});
}}

// ── CAPAS LEAFLET ──────────────────────────────────────────────────────────
let layerPrepas     = L.featureGroup();
let layerPerimetros = L.featureGroup();
let layerRutas      = L.featureGroup();
let layerTransporte = L.featureGroup();

// Estado activo de filtros
let activoAlcaldias     = new Set(ALCALDIAS);
let activoInstituciones = new Set(INSTITUCIONES);
let activoTransporte    = new Set();  // se llena al construir filtros

function buildPopup(p) {{
  return `<div class="popup-title">${{p.NOMBRE_POI || ''}}</div>
    <div class="popup-row"><span class="popup-key">Alcaldía</span><span class="popup-val">${{p.sector || '—'}}</span></div>
    <div class="popup-row"><span class="popup-key">Institución</span><span class="popup-val popup-badge">${{p.SUBCLACIFICACION || '—'}}</span></div>
    <div class="popup-row"><span class="popup-key">Transportes cercanos</span><span class="popup-val">${{p.num_transportes || 0}}</span></div>`;
}}

function renderAll() {{
  layerPrepas.clearLayers();
  layerPerimetros.clearLayers();
  layerRutas.clearLayers();

  const prepasVisibles = new Set();

  // Prepas filtradas
  DATA_PREPAS.features.forEach(f => {{
    const p = f.properties;
    if (!activoAlcaldias.has(p.sector)) return;
    if (!activoInstituciones.has(p.SUBCLACIFICACION)) return;
    prepasVisibles.add(p['ID-CARTO']);
    const layer = L.geoJSON(f, {{ style: stylePrepa }})
      .bindPopup(buildPopup(p), {{ maxWidth: 260 }});
    layerPrepas.addLayer(layer);
  }});

  // Perímetros — solo de prepas visibles
  DATA_PERIMETROS.features.forEach(f => {{
    if (!prepasVisibles.has(f.properties.ID_CARTO)) return;
    layerPerimetros.addLayer(L.geoJSON(f, {{ style: stylePerimetro }}));
  }});

  // Rutas — solo de prepas visibles
  let numRutas = 0;
  DATA_RUTAS.features.forEach(f => {{
    if (!prepasVisibles.has(f.properties.prepa_id)) return;
    layerRutas.addLayer(L.geoJSON(f, {{ style: styleRuta }}));
    numRutas++;
  }});

  document.getElementById('stat-prepas').textContent = prepasVisibles.size;
  document.getElementById('stat-rutas').textContent  = numRutas;
}}

// Transporte — marcadores con color por línea, filtrados por tipo activo
const transMarkers = [];  // {{typeKey, marker}} para re-filtrar
DATA_TRANSPORTE.features.forEach(f => {{
  const p = f.properties;
  const coords = f.geometry.coordinates;
  const color   = getTransColor(p.NOMBRE_POI, p.POI, p.ESPECIALID);
  const typeKey = getTransTypeKey(p.NOMBRE_POI, p.POI, p.ESPECIALID);
  const shape   = typeKey === 'cablebus' ? 'star' : 'circle';
  const marker  = L.marker([coords[1], coords[0]], {{ icon: makeIcon(color, shape) }})
    .bindPopup(`<div class="popup-title">${{p.NOMBRE_POI || ''}}</div>
      <div class="popup-row"><span class="popup-key">Tipo</span><span class="popup-val popup-badge" style="color:${{color}};border-color:${{color}}40">${{p.POI || ''}}</span></div>`, {{ maxWidth: 220 }});
  transMarkers.push({{ typeKey, marker }});
}});

function renderTransporte() {{
  layerTransporte.clearLayers();
  transMarkers.forEach(({{typeKey, marker}}) => {{
    if (activoTransporte.has(typeKey)) layerTransporte.addLayer(marker);
  }});
}}

// Agregar al mapa
layerPerimetros.addTo(map);
layerRutas.addTo(map);
layerTransporte.addTo(map);
layerPrepas.addTo(map);

renderAll();

// ── TOGGLES DE CAPAS ──────────────────────────────────────────────────────
function bindToggle(id, layer) {{
  document.getElementById(id).addEventListener('change', function() {{
    this.checked ? layer.addTo(map) : map.removeLayer(layer);
  }});
}}
bindToggle('tog-alcaldias',  layerAlcaldias);
bindToggle('tog-prepas',     layerPrepas);
bindToggle('tog-perimetros', layerPerimetros);
bindToggle('tog-rutas',      layerRutas);
bindToggle('tog-transporte', layerTransporte);

// ── FILTROS ────────────────────────────────────────────────────────────────
function buildFilterGroup(containerId, items, activeSet, onChange) {{
  const container = document.getElementById(containerId);
  items.forEach(item => {{
    const label = document.createElement('label');
    label.className = 'filter-item active';
    label.innerHTML = `<input type="checkbox" checked value="${{item}}"> ${{item}}`;
    const cb = label.querySelector('input');
    cb.addEventListener('change', function() {{
      this.checked ? activeSet.add(item) : activeSet.delete(item);
      label.classList.toggle('active', this.checked);
      onChange();
    }});
    container.appendChild(label);
  }});
}}

buildFilterGroup('filter-alcaldias',     ALCALDIAS,     activoAlcaldias,     renderAll);
buildFilterGroup('filter-instituciones', INSTITUCIONES, activoInstituciones, renderAll);

function toggleAll(tipo, state) {{
  const containerId = tipo === 'alcaldia' ? 'filter-alcaldias' : 'filter-instituciones';
  const activeSet   = tipo === 'alcaldia' ? activoAlcaldias    : activoInstituciones;
  const items       = tipo === 'alcaldia' ? ALCALDIAS          : INSTITUCIONES;
  document.querySelectorAll(`#${{containerId}} input`).forEach(cb => {{
    cb.checked = state;
    state ? activeSet.add(cb.value) : activeSet.delete(cb.value);
    cb.closest('label').classList.toggle('active', state);
  }});
  renderAll();
}}

// ── FILTROS DE TRANSPORTE ─────────────────────────────────────────────────
const METRO_LINES    = ['1','2','3','4','5','6','7','8','9','A','B','12'];
const METROBUS_LINES = ['1','2','3','4','5','6','7'];

const METRO_COLS    = {{'1':'#f93eab','2':'#4686fb','3':'#c6d951','4':'#1be5b5','5':'#fbf64d','6':'#fc2222','7':'#e39c00','8':'#11bc59','9':'#996a1b','A':'#ac22de','B':'#b8b8b8','12':'#bcb08f'}};
const METROBUS_COLS = {{'1':'#d41818','2':'#b912cd','3':'#99d54e','4':'#f9640d','5':'#08249d','6':'#ff2a9a','7':'#0b9d67'}};

function buildTransFilterGroup(containerId, items, keyPrefix, colorMap) {{
  const container = document.getElementById(containerId);
  items.forEach(line => {{
    const key   = keyPrefix + line;
    const color = colorMap[line] || '#aaa';
    activoTransporte.add(key);
    const label = document.createElement('label');
    label.className = 'trans-item active';
    label.innerHTML = `<input type="checkbox" checked value="${{key}}">
      <div class="trans-dot" style="background:${{color}}"></div>
      Línea ${{line}}`;
    label.querySelector('input').addEventListener('change', function() {{
      this.checked ? activoTransporte.add(key) : activoTransporte.delete(key);
      label.classList.toggle('active', this.checked);
      renderTransporte();
    }});
    container.appendChild(label);
  }});
}}

function buildSingleFilter(containerId, key, color, labelText) {{
  activoTransporte.add(key);
  const container = document.getElementById(containerId);
  const label = document.createElement('label');
  label.className = 'trans-item active';
  label.innerHTML = `<input type="checkbox" checked value="${{key}}">
    <div class="trans-dot" style="background:${{color}}"></div>
    ${{labelText}}`;
  label.querySelector('input').addEventListener('change', function() {{
    this.checked ? activoTransporte.add(key) : activoTransporte.delete(key);
    label.classList.toggle('active', this.checked);
    renderTransporte();
  }});
  container.appendChild(label);
}}

buildTransFilterGroup('filter-metro',    METRO_LINES,    'metro-',    METRO_COLS);
buildTransFilterGroup('filter-metrobus', METROBUS_LINES, 'metrobus-', METROBUS_COLS);
buildSingleFilter('filter-trolebus', 'trolebus', '#67d1f7', 'Trolebús');
buildSingleFilter('filter-cetrams',  'cetrams',  '#039b94', 'CETRAMS');
buildSingleFilter('filter-cablebus', 'cablebus', '#b57bee', 'Cablebús');

// Inicializar marcadores de transporte (activoTransporte ya está lleno)
renderTransporte();

// Toggle desplegables de transporte
function toggleTG(id) {{
  const body  = document.getElementById('tgb-' + id);
  const arrow = document.getElementById('arr-' + id);
  const open  = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  arrow.classList.toggle('open', !open);
}}

function toggleTransType(prefix, state) {{
  const containerId = prefix === 'metro' ? 'filter-metro' : 'filter-metrobus';
  document.querySelectorAll(`#${{containerId}} input`).forEach(cb => {{
    cb.checked = state;
    state ? activoTransporte.add(cb.value) : activoTransporte.delete(cb.value);
    cb.closest('label').classList.toggle('active', state);
  }});
  renderTransporte();
}}
</script>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✓ Mapa generado: {OUTPUT_HTML}")
    print(f"  Abre el archivo en cualquier navegador.")

if __name__ == "__main__":
    main()
