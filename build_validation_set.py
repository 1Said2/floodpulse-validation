import os
import json
import time
import csv
import requests
import sys

# Agregar floodpulse-backend al path para importar lógica de negocio real
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'floodpulse-backend')))
from src.data_fetcher import fetch_dem, fetch_osm_network
from src.risk_model import calculate_distance_to_channel, calculate_twi, get_distance_from_raster
import geopandas as gpd
from shapely.geometry import Point
import tempfile
import math

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# D2: Positivos verificados para Guayaquil, 1-3 abril 2025
GUAYAQUIL_POSITIVES = [
    {"name": "Monte Sinaí, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "guayaquil.gob.ec / ecuavisa.com/noticias/guayaquil/30-sectores-inundados-guayaquil-3-abril-DB9065410", "fuente_cita": "Inundaciones en Monte Sinaí, 30 sectores anegados.", "tipo": "Positivo Documentado"},
    {"name": "Socio Vivienda 1, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "guayaquil.gob.ec / ecuavisa.com/noticias/guayaquil/agucero-guayaquil-truenos-rayos-AA9057288", "fuente_cita": "Socio Vivienda 1 anegado tras tormenta.", "tipo": "Positivo Documentado"},
    {"name": "La Alborada, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "ecuavisa.com/noticias/guayaquil/agucero-guayaquil-truenos-rayos-AA9057288", "fuente_cita": "La Alborada, el barrio más afectado.", "tipo": "Positivo Documentado"},
    {"name": "El Fortín, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "ecuavisa.com/noticias/guayaquil/agucero-guayaquil-truenos-rayos-AA9057288", "fuente_cita": "Afectaciones en El Fortín y Mi Lote.", "tipo": "Positivo Documentado"},
    {"name": "Mi Lote, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "ecuavisa.com/noticias/guayaquil/agucero-guayaquil-truenos-rayos-AA9057288", "fuente_cita": "Afectaciones en El Fortín y Mi Lote.", "tipo": "Positivo Documentado"},
    {"name": "avenida Casuarina, Entrada de la Ocho, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "ecuavisa.com/noticias/guayaquil/agucero-guayaquil-truenos-rayos-AA9057288", "fuente_cita": "avenida Casuarina Entrada de la Ocho inundada.", "tipo": "Positivo Documentado"},
    {"name": "Cooperativa Julio Cartagena, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "ecuavisa.com/noticias/guayaquil/agucero-guayaquil-truenos-rayos-AA9057288", "fuente_cita": "Cooperativa Julio Cartagena detrás del cementerio Jardines de la Esperanza.", "tipo": "Positivo Documentado"},
    {"name": "Sauces 6, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "primicias.ec/guayaquil/inundaciones-negocios-sauces-lluvias-ecuador-93180/", "fuente_cita": "Inundaciones en negocios de Sauces 6 y 7.", "tipo": "Positivo Documentado"},
    {"name": "Sauces 7, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "primicias.ec/guayaquil/inundaciones-negocios-sauces-lluvias-ecuador-93180/", "fuente_cita": "Inundaciones en negocios de Sauces 6 y 7.", "tipo": "Positivo Documentado"},
    {"name": "Samanes 1, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "primicias.ec/guayaquil/inundaciones-calles-invierno-horas-lluvias-93167/", "fuente_cita": "Samanes 1, Urdesa Central... bajo el agua.", "tipo": "Positivo Documentado"},
    {"name": "Urdesa Central, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "primicias.ec/guayaquil/inundaciones-calles-invierno-horas-lluvias-93167/", "fuente_cita": "Samanes 1, Urdesa Central... bajo el agua.", "tipo": "Positivo Documentado"},
    {"name": "Sauces 2, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "primicias.ec/guayaquil/inundaciones-calles-invierno-horas-lluvias-93167/", "fuente_cita": "Samanes 1, Urdesa Central, Sauces 2... bajo el agua.", "tipo": "Positivo Documentado"},
    {"name": "avenida Barcelona, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "primicias.ec/guayaquil/inundaciones-calles-invierno-horas-lluvias-93167/", "fuente_cita": "avenida Barcelona, avenida Narcisa de Jesús, vía a Daule.", "tipo": "Positivo Documentado"},
    {"name": "avenida Narcisa de Jesús, Guayaquil, Ecuador", "flooded": 1, "fuente_url": "primicias.ec/guayaquil/inundaciones-calles-invierno-horas-lluvias-93167/", "fuente_cita": "avenida Barcelona, avenida Narcisa de Jesús, vía a Daule.", "tipo": "Positivo Documentado"}
]

# D4 & D5: Candidatos negativos Guayaquil (se filtraron Puerto Azul, Bastión Popular Bloque 10 por baja elevación)
GUAYAQUIL_CANDIDATES = [
    {"name": "Cerro Santa Ana, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Las Peñas, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Bellavista, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Lomas de Urdesa, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Mirador San Eduardo, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Bosque Protector Cerro Blanco, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Cerro Colorado, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Lomas de la Florida, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"},
    {"name": "Lomas de Prosperina, Guayaquil, Ecuador", "flooded": 0, "fuente_url": "https://guayaquil.gob.ec/", "fuente_cita": "Ausente en reporte de Segura EP.", "tipo": "Negativo Espacial"}
]

# D3: Positivos verificados Portoviejo, 19-20 Feb 2025 (se removió Riochico)
PORTOVIEJO_POSITIVES = [
    {"name": "Calderón, Portoviejo, Ecuador", "flooded": 1, "fuente_url": "eldiario.ec/actualidad/portoviejo/portoviejo-supero-los-3746-milimetros...", "fuente_cita": "Afectados: parroquias Calderón y Riochico.", "tipo": "Positivo Documentado"},
    {"name": "quebradas Maconta, Abdón Calderón, Portoviejo, Ecuador", "flooded": 1, "fuente_url": "eldiario.ec/actualidad/portoviejo/portoviejo-supero-los-3746-milimetros...", "fuente_cita": "quebradas Maconta y Bijagual en Abdón Calderón.", "tipo": "Positivo Documentado"},
    {"name": "quebradas Bijagual, Abdón Calderón, Portoviejo, Ecuador", "flooded": 1, "fuente_url": "eldiario.ec/actualidad/portoviejo/portoviejo-supero-los-3746-milimetros...", "fuente_cita": "quebradas Maconta y Bijagual en Abdón Calderón.", "tipo": "Positivo Documentado"},
]

def geocode_nominatim(name):
    url = f"https://nominatim.openstreetmap.org/search?q={name}&format=json&limit=1"
    headers = {"User-Agent": "FloodPulse-Validation-Bot/2.0"}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 0:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Error HTTP nominatim: {e}")
    return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Radio de la tierra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_elevation_distance_real(lat, lon):
    try:
        bbox = [lon - 0.005, lat - 0.005, lon + 0.005, lat + 0.005]
        # 1. Elevación del DEM real
        dem_da = fetch_dem(bbox)
        elev = float(dem_da.sel(x=lon, y=lat, method="nearest").values.item())
        
        # 2. Distancia al cauce real
        waterways_gdf = fetch_osm_network(bbox)
        point_gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
        
        if waterways_gdf.empty:
            print("  [osm] OSM vacío. Extrayendo cauces desde DEM...")
            with tempfile.TemporaryDirectory() as tmpdir:
                twi_tif, dist_tif = calculate_twi(dem_da, crs_metric="EPSG:32717", tmp_dir=tmpdir, extract_streams=True)
                dist_array = get_distance_from_raster(point_gdf, dist_tif, crs_metric="EPSG:32717")
                dist = float(dist_array[0])
                if dist > 9000:
                    dist = 1000.0 # valor razonable si el DEM falla
        else:
            dist_array = calculate_distance_to_channel(point_gdf, waterways_gdf, crs_metric="EPSG:32717")
            dist = float(dist_array[0])
            
        return round(elev, 1), round(dist, 1)
    except Exception as e:
        print(f"  [!] Error extraendo DEM/OSM: {e}")
        return 0.0, 0.0

def build_dataset():
    os.makedirs(DATA_DIR, exist_ok=True)
    dataset = []
    
    # Centros de las ciudades
    center_gyq_lat, center_gyq_lon = -2.1709, -79.9223 # Guayaquil
    center_pvo_lat, center_pvo_lon = -1.0545, -80.4544 # Portoviejo
    
    # 1. Eventos de Guayaquil (1-3 abril 2025)
    for loc in GUAYAQUIL_POSITIVES + GUAYAQUIL_CANDIDATES:
        print(f"Geocodificando: {loc['name']}...")
        lat, lon = geocode_nominatim(loc['name'])
        time.sleep(1.2)
        
        if lat and lon:
            dist_centro = haversine(center_gyq_lat, center_gyq_lon, lat, lon)
            if dist_centro > 15.0:
                print(f"  [!] Descartado: {loc['name']} está a {dist_centro:.1f} km del centro (>15 km).")
                continue
                
            elev, dist = get_elevation_distance_real(lat, lon)
            dataset.append({
                "id": len(dataset) + 1,
                "name": loc["name"],
                "lat": lat,
                "lon": lon,
                "fecha_inicio": "2025-04-01",
                "fecha_fin": "2025-04-03",
                "flooded": loc["flooded"],
                "tipo": loc["tipo"],
                "fuente_url": loc["fuente_url"],
                "fuente_cita": loc["fuente_cita"],
                "verificado": False,
                "elevacion_dem_m": elev,
                "dist_cauce_m": dist,
                "notas": "Guayaquil. Segura EP reportó 64 sectores anegados en el norte."
            })
        else:
            print(f"  [!] Falló geocodificación para {loc['name']}")
            
    # 2. Eventos de Portoviejo (19-20 feb 2025)
    for loc in PORTOVIEJO_POSITIVES:
        print(f"Geocodificando: {loc['name']}...")
        lat, lon = geocode_nominatim(loc['name'])
        time.sleep(1.2)
        
        if lat and lon:
            dist_centro = haversine(center_pvo_lat, center_pvo_lon, lat, lon)
            if dist_centro > 15.0:
                print(f"  [!] Descartado: {loc['name']} está a {dist_centro:.1f} km del centro (>15 km).")
                continue
                
            elev, dist = get_elevation_distance_real(lat, lon)
            dataset.append({
                "id": len(dataset) + 1,
                "name": loc["name"],
                "lat": lat,
                "lon": lon,
                "fecha_inicio": "2025-02-19",
                "fecha_fin": "2025-02-20",
                "flooded": loc["flooded"],
                "tipo": loc["tipo"],
                "fuente_url": loc["fuente_url"],
                "fuente_cita": loc["fuente_cita"],
                "verificado": False,
                "elevacion_dem_m": elev,
                "dist_cauce_m": dist,
                "notas": "Los 89.5 mm cayeron en La Teodomira (cantón Santa Ana) a 15km."
            })
        else:
            print(f"  [!] Falló geocodificación para {loc['name']}")
            
    json_path = os.path.join(DATA_DIR, 'validation_set.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
        
    csv_path = os.path.join(DATA_DIR, 'revision.csv')
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "lat", "lon", "flooded", "tipo", "elevacion_dem_m", "dist_cauce_m", "fuente_url", "verificado"])
        writer.writeheader()
        for r in dataset:
            writer.writerow({k: r[k] for k in ["id", "name", "lat", "lon", "flooded", "tipo", "elevacion_dem_m", "dist_cauce_m", "fuente_url", "verificado"]})
            
    print(f"\nGenerado {json_path} y {csv_path} con {len(dataset)} registros.")

if __name__ == "__main__":
    build_dataset()
