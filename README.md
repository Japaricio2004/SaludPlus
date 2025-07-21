# SaludPlus

SaludPlus es una aplicación web desarrollada en Flask para el seguimiento y gestión de métricas personales de bienestar, como peso, sueño, hábitos, actividad física y más. Permite a los usuarios registrar, visualizar y analizar su progreso de manera sencilla y visual.

## Características principales

- Registro de métricas personalizadas (peso, agua, sueño, etc.)
- Visualización de métricas en tablas y gráficas
- Gestión de categorías personalizadas
- Objetivos y alertas automáticas
- Exportación e importación de datos (CSV, Excel)
- Filtros y búsqueda avanzada
- Accesibilidad: modo oscuro, alto contraste, ajuste de fuente
- Guía interactiva de uso ("¿Cómo funciona?")
- Autenticación de usuarios y gestión de sesiones

## Instalación y requisitos

### Requisitos previos
- Python 3.8+
- pip

### Instalación local
1. Clona el repositorio:
   ```bash
   git clone https://github.com/tuusuario/SaludPlus.git
   cd SaludPlus
   ```
2. (Opcional) Crea y activa un entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Ejecuta la aplicación:
   ```bash
   python run.py
   ```
5. Abre tu navegador en [http://localhost:5000](http://localhost:5000)

## Despliegue en PythonAnywhere
1. Sube el proyecto a tu cuenta de PythonAnywhere.
2. Crea y activa un entorno virtual, instala dependencias.
3. Configura la app web apuntando a `run.py`.
4. Edita el archivo WSGI según la ruta de tu usuario.
5. Recarga la web desde el panel.

## Despliegue en Render
1. Sube el proyecto a GitHub.
2. Crea un nuevo servicio web en Render y conecta el repo.
3. Usa el comando de inicio:
   ```bash
   gunicorn run:app
   ```
4. Render detectará automáticamente las dependencias desde `requirements.txt`.

## Estructura del proyecto

```
SaludPlus/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   └── ...
├── static/ (si aplica)
├── run.py
├── config.py
├── requirements.txt
├── README.md
└── ...
```

## Créditos
Desarrollado por Japaricio2004.

## Licencia
Este proyecto está bajo la licencia MIT. Puedes modificarlo y usarlo libremente.
