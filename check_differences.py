from database import get_db
from models import Media
from sqlalchemy.orm import Session
from sqlalchemy import text

def check_different_values():
    db = next(get_db())
    
    # Encontrar registros donde estado != status
    result = db.execute(text("""
        SELECT id, titulo, estado, status
        FROM media 
        WHERE estado IS NOT NULL 
        AND status IS NOT NULL 
        AND estado != status
        ORDER BY id
    """))
    
    print("=== REGISTROS CON VALORES DIFERENTES ===")
    print(f"{'ID':<5} {'Título':<40} {'estado':<20} {'status':<20}")
    print("-" * 90)
    
    different_records = []
    for row in result:
        titulo = (row[1][:37] + "...") if len(row[1]) > 40 else row[1]
        print(f"{row[0]:<5} {titulo:<40} {row[2]:<20} {row[3]:<20}")
        different_records.append(row)
    
    print(f"\nTotal de registros diferentes: {len(different_records)}")
    
    if len(different_records) > 0:
        print("\n¿Qué hacer?")
        print("1. Actualizar 'estado' para que coincida con 'status' (recomendado)")
        print("2. Actualizar 'status' para que coincida con 'estado'")
        print("3. Revisar manualmente cada caso")
        
        # Mostrar análisis de los valores
        print("\n=== ANÁLISIS DE VALORES ===")
        estado_values = [r[2] for r in different_records]
        status_values = [r[3] for r in different_records]
        
        print(f"Valores en 'estado': {set(estado_values)}")
        print(f"Valores en 'status': {set(status_values)}")
    
    db.close()
    return different_records

if __name__ == "__main__":
    check_different_values()
