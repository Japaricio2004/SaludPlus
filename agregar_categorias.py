from app import create_app, db
from app.models import Categoria

CATEGORIAS = [
    'Salud', 'Deporte', 'Estudio', 'Trabajo', 'Alimentación', 'Sueño',
    'Finanzas', 'Hábitos', 'Tiempo libre', 'Familia', 'Social',
    'Creatividad', 'Lectura', 'Meditación', 'Proyectos', 'Viajes'
]

app = create_app()

with app.app_context():
    for nombre in CATEGORIAS:
        if not Categoria.query.filter_by(nombre=nombre).first():
            db.session.add(Categoria(nombre=nombre))
    db.session.commit()
    print("Categorías agregadas correctamente.")
