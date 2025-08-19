from database import get_db
from models import Media
from sqlalchemy.orm import Session
from sqlalchemy import func

def check_estado_vs_status():
    db = next(get_db())
    
    # Obtener algunos ejemplos de ambos campos
    medias = db.query(Media).limit(10).all()
    
    print("=== COMPARACIÓN DE CAMPOS estado vs status ===")
    print(f"{'ID':<5} {'Título':<30} {'estado':<15} {'status':<15}")
    print("-" * 70)
    
    for media in medias:
        titulo = (media.titulo[:27] + "...") if len(media.titulo) > 30 else media.titulo
        estado = media.estado or "NULL"
        status = media.status or "NULL"
        print(f"{media.id:<5} {titulo:<30} {estado:<15} {status:<15}")
    
    print("\n=== VALORES ÚNICOS EN CAMPO 'estado' ===")
    estados_unicos = db.query(func.distinct(Media.estado)).all()
    for estado in estados_unicos:
        if estado[0]:
            count = db.query(Media).filter(Media.estado == estado[0]).count()
            print(f"- '{estado[0]}': {count} registros")
    
    print("\n=== VALORES ÚNICOS EN CAMPO 'status' ===")
    status_unicos = db.query(func.distinct(Media.status)).all()
    for status in status_unicos:
        if status[0]:
            count = db.query(Media).filter(Media.status == status[0]).count()
            print(f"- '{status[0]}': {count} registros")
    
    db.close()

if __name__ == "__main__":
    check_estado_vs_status()
