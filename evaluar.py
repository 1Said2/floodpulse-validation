import json
import os
import time
import datetime
from typing import List, Dict

import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc
import numpy as np

# Añadir el path para importar src
import sys
sys.path.append(r"C:\Users\micha\Documents\floodpulse-backend")

from src.main import evaluate_risk

DATA_FILE = r"C:\Users\micha\Documents\floodpulse-validation\data\validation_set.json"
DOCS_DIR = r"C:\Users\micha\Documents\floodpulse-validation"

import subprocess

def run_evaluation():
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        dataset_full = json.load(f)
        
    dataset = [d for d in dataset_full if d.get('verificado') is True]
    
    y_true = []
    y_scores = []
    rain_values = []
    
    print(f"Evaluando {len(dataset)} ubicaciones (con aislamiento de subprocesos)...")
    
    # Escribir un script temporal esclavo para correr 1 sola evaluación
    slave_code = """import sys, json, datetime
sys.path.append(r'C:\\Users\\micha\\Documents\\floodpulse-backend')
from src.main import evaluate_risk
try:
    start_date = sys.argv[3]
    end_date = sys.argv[4]
    # Usar lluvia fija por ciudad/evento para aislar susceptibilidad y evitar ruido del píxel IMERG
    res = evaluate_risk(lat=float(sys.argv[1]), lon=float(sys.argv[2]), bbox_offset_deg=0.005, rainfall_mm=113.2, event_start=start_date, event_end=end_date, fallback_waterway_coords=None)
    print(json.dumps({"risk_score": res.risk_score, "rainfall_mm": res.components['rainfall_mm']}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""
    slave_path = os.path.join(DOCS_DIR, "eval_slave.py")
    with open(slave_path, "w", encoding="utf-8") as f:
        f.write(slave_code)
        
    for item in dataset:
        print(f"-> Evaluando {item['name']}...")
        try:
            # Correr en un proceso totalmente separado para que si se cuelga Whitebox, el timeout lo mate limpio
            proc = subprocess.run([sys.executable, slave_path, str(item['lat']), str(item['lon']), item['fecha_inicio'], item['fecha_fin']], 
                                  capture_output=True, text=True, timeout=40)
            
            # Buscar el JSON en la salida
            import re
            match = re.search(r'(\{.*\})', proc.stdout, re.DOTALL)
            try:
                if match:
                    result = json.loads(match.group(1))
                else:
                    result = json.loads(proc.stdout.strip())
            except json.JSONDecodeError as e:
                print(f"   [ERROR] Falló parseo de JSON en {item['name']}: {e}")
                print(f"   --- STDOUT ---\n{proc.stdout}\n   --- STDERR ---\n{proc.stderr}\n   -------------")
                continue
            
            if "error" in result:
                print(f"   [ERROR] Falló {item['name']}: {result['error']}")
                continue
                
            y_true.append(item['flooded'])
            y_scores.append(result['risk_score'])
            rain_values.append(result['rainfall_mm'])
            print(f"   [OK] Riesgo: {result['risk_score']:.2f}, Lluvia extraída: {result['rainfall_mm']:.1f} mm")
            
        except subprocess.TimeoutExpired:
            print(f"   [ERROR] Timeout al evaluar {item['name']} (WhiteboxTools tomó más de 40s y fue abortado)")
        except Exception as e:
            print(f"   [ERROR] Excepción {item['name']}: {e}")
            
    # Limpiar esclavo
    if os.path.exists(slave_path): os.remove(slave_path)

            
    if not y_true:
        print("No hay datos evaluados.")
        return
        
    y_true = np.array(y_true)
    y_scores = np.array(y_scores)
    
    # Calcular ROC
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    roc_auc = auc(fpr, tpr)
    
    # Encontrar umbral óptimo (Youden's J statistic)
    J = tpr - fpr
    optimal_idx = np.argmax(J)
    optimal_threshold = thresholds[optimal_idx]
    
    print(f"\n--- Resultados de Evaluación ---")
    print(f"AUC: {roc_auc:.3f}")
    print(f"Umbral Óptimo Sugerido: {optimal_threshold:.2f}")
    print(f"TPR (Sensibilidad) en Óptimo: {tpr[optimal_idx]:.3f}")
    print(f"FPR en Óptimo: {fpr[optimal_idx]:.3f}")
    
    # Graficar
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.scatter([fpr[optimal_idx]], [tpr[optimal_idx]], color='red', marker='o', s=100, label=f'Optimal Threshold ({optimal_threshold:.1f})')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC - Susceptibilidad Topográfica')
    plt.legend(loc="lower right")
    plt.grid(True, alpha=0.3)
    
    out_png = os.path.join(DOCS_DIR, 'roc_curve.png')
    plt.savefig(out_png, dpi=300, bbox_inches='tight')
    print(f"\nCurva ROC guardada en {out_png}")
    
    # Guardar reporte
    with open(os.path.join(DOCS_DIR, 'eval_report.txt'), 'w', encoding='utf-8') as f:
        f.write(f"AUC: {roc_auc:.3f}\n")
        f.write(f"Umbral Optimo: {optimal_threshold:.2f}\n")
        f.write(f"Total Evaluados: {len(y_true)}\n")

if __name__ == "__main__":
    run_evaluation()
