import ee
import os
from datetime import datetime, timedelta, timezone

def run_diag():
    project_id = os.environ.get("EE_PROJECT") or "gen-lang-client-0564385440"
    try:
        ee.Initialize(project=project_id)
        print(f"GEE Inicializado con proyecto: {project_id}")
    except Exception as e:
        print(f"Error inicializando GEE: {e}")
        return

    # Bbox Malacatos
    lat = -3.994537
    lon = -79.205415
    offset = 0.005
    bbox = [lon - offset, lat - offset, lon + offset, lat + offset]
    geom = ee.Geometry.Rectangle(bbox)

    now = datetime.now(timezone.utc)
    recent_start = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    recent_end = now.strftime("%Y-%m-%d")

    # Fechas con +1 día para que filterDate sea inclusivo del día final
    def run_case(name, col_id, start, end, is_chirps=False):
        print(f"--- Caso {name} ---")
        print(f"Colección: {col_id}")
        print(f"Ventana (consulta): {start} a {end}")
        
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        
        # filterDate in GEE is exclusive for end_date, add 1 day
        end_gee = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        
        col = ee.ImageCollection(col_id).filterDate(start, end_gee)
        
        try:
            size = col.size().getInfo()
            print(f"Tamaño de colección: {size} imágenes")
            if size == 0:
                print("Lluvia (mm): 0.0 (Colección vacía)")
                return
            
            if is_chirps:
                col = col.select('precipitation')
                # CHIRPS es diario, en mm/día. Sumamos directo.
                def calc_mm_chirps(image):
                    return image.copyProperties(image, ["system:time_start"])
                total_img = col.map(calc_mm_chirps).sum()
            else:
                # GPM_L3/IMERG_V06 usa 'precipitationCal', V07 usa 'precipitation'
                band_name = 'precipitation'
                if 'V06' in col_id:
                    band_name = 'precipitationCal'
                
                col = col.select(band_name)
                # GPM es media hora en mm/hr, multiplicamos por 0.5
                def calc_mm_gpm(image):
                    return image.multiply(0.5).copyProperties(image, ["system:time_start"])
                total_img = col.map(calc_mm_gpm).sum()

            stats = total_img.reduceRegion(
                reducer=ee.Reducer.max(),
                geometry=geom,
                scale=1000,
                maxPixels=1e9
            )
            val = stats.getInfo()
            mm_val = list(val.values())[0] if val else 0.0
            print(f"Lluvia (mm): {mm_val}")
        except Exception as e:
            print(f"Error: {e}")
            
    print("\nIniciando diagnóstico GEE...\n")
    
    run_case("A (Reciente, V06)", "NASA/GPM_L3/IMERG_V06", recent_start, recent_end)
    run_case("B (Reciente, V07)", "NASA/GPM_L3/IMERG_V07", recent_start, recent_end)
    
    # Historicos
    run_case("C (Malacatos histórico, V07)", "NASA/GPM_L3/IMERG_V07", "2025-03-10", "2025-03-11")
    run_case("D (Guayaquil histórico, V07)", "NASA/GPM_L3/IMERG_V07", "2026-06-07", "2026-06-09")
    
    # CHIRPS
    run_case("E (Malacatos histórico, CHIRPS)", "UCSB-CHG/CHIRPS/DAILY", "2025-03-10", "2025-03-11", True)
    run_case("F (Reciente, CHIRPS)", "UCSB-CHG/CHIRPS/DAILY", recent_start, recent_end, True)

if __name__ == "__main__":
    run_diag()
