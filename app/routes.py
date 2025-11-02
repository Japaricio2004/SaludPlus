from flask import render_template, redirect, url_for, flash, request, Blueprint, session
from flask_login import login_user, current_user, login_required, logout_user
from werkzeug.security import check_password_hash
from app import db
from app.models import Usuario, Metrica
from datetime import date
import pandas as pd
import io
from flask import send_file
main = Blueprint('main', __name__)
import json
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

@main.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():
    from app.models import Categoria, Objetivo
    # Guardar/actualizar objetivos
    if request.method == 'POST' and 'objetivo_metrica' in request.form:
        nombre_metrica = request.form['objetivo_metrica']
        valor_inicial = request.form.get('valor_inicial', '')
        valor_objetivo = request.form['valor_objetivo']
        unidad = request.form.get('unidad_objetivo', '')
        direccion = request.form.get('direccion_objetivo', 'aumentar')  # Obtener dirección
        
        if nombre_metrica and valor_objetivo:
            obj = Objetivo.query.filter_by(usuario_id=current_user.id, nombre_metrica=nombre_metrica).first()
            if obj:
                if valor_inicial:
                    obj.valor_inicial = float(valor_inicial)
                obj.valor_objetivo = valor_objetivo
                obj.unidad = unidad
                obj.direccion = direccion  # Actualizar dirección
            else:
                obj = Objetivo(
                    usuario_id=current_user.id, 
                    nombre_metrica=nombre_metrica,
                    valor_inicial=float(valor_inicial) if valor_inicial else None,
                    valor_objetivo=valor_objetivo, 
                    unidad=unidad, 
                    direccion=direccion
                )
                db.session.add(obj)
            db.session.commit()
            flash(f'Objetivo para "{nombre_metrica}" actualizado.', 'success')
        return redirect(url_for('main.dashboard'))

    # Filtros
    q = request.args.get('q', '').strip()
    fecha_inicio = request.args.get('fecha_inicio', '').strip()
    fecha_fin = request.args.get('fecha_fin', '').strip()
    filtros = [Metrica.usuario_id == current_user.id]
    if q:
        filtros.append(Metrica.nombre.ilike(f'%{q}%'))
    if fecha_inicio:
        filtros.append(Metrica.fecha >= fecha_inicio)
    if fecha_fin:
        filtros.append(Metrica.fecha <= fecha_fin)
    metricas = Metrica.query.options(joinedload(Metrica.categoria)).filter(and_(*filtros)).order_by(Metrica.fecha.asc()).all()
    metricas_json = json.dumps([
        {
            'nombre': m.nombre,
            'valor': m.valor,
            'fecha': m.fecha.isoformat() if m.fecha else None,
            'categoria': m.categoria.nombre if m.categoria else None
        } for m in metricas
    ])
    total_categorias = Categoria.query.count()

    
    # Calcular estadísticas por tipo de métrica
    stats = {}
    for m in metricas:
        if m.nombre not in stats:
            stats[m.nombre] = {'valores': [], 'unidad': m.unidad or '', 'fechas': []}
        stats[m.nombre]['valores'].append(m.valor)
        stats[m.nombre]['fechas'].append(m.fecha)
    for nombre, data in stats.items():
        valores = data['valores']
        fechas = data['fechas']
        data['promedio'] = round(sum(valores) / len(valores), 2) if valores else 0
        data['maximo'] = max(valores) if valores else 0
        data['minimo'] = min(valores) if valores else 0
        # Agregar el valor más reciente (última medición)
        if valores and fechas:
            # Ordenar por fecha y obtener el valor más reciente
            valores_ordenados = [v for _, v in sorted(zip(fechas, valores), key=lambda x: x[0])]
            data['actual'] = valores_ordenados[-1]  # Último valor (más reciente)
        else:
            data['actual'] = 0

    # Leer objetivos del usuario
    objetivos = {o.nombre_metrica: o for o in Objetivo.query.filter_by(usuario_id=current_user.id).all()}

    # Calcular tendencias y alertas
    tendencias = {}
    alertas = {}
    for nombre, data in stats.items():
        valores = data['valores']
        fechas = data['fechas']
        tendencia = ""
        if len(valores) >= 4:
            # Compara el promedio de la mitad más reciente vs la mitad anterior
            mitad = len(valores) // 2
            prom_ant = sum(valores[:mitad]) / len(valores[:mitad])
            prom_rec = sum(valores[mitad:]) / len(valores[mitad:])
            if prom_rec > prom_ant * 1.05:
                tendencia = "¡Vas mejorando tu promedio de {}!".format(nombre)
            elif prom_rec < prom_ant * 0.95:
                tendencia = "Atención: tu promedio de {} está bajando.".format(nombre)
            else:
                tendencia = "Tu promedio de {} se mantiene estable.".format(nombre)
        tendencias[nombre] = tendencia

        # Alertas: si hay objetivo, compara promedio con objetivo
        objetivo = objetivos.get(nombre)
        alerta = ""
        if objetivo:
            try:
                objetivo_val = float(objetivo.valor_objetivo)
                promedio = data['promedio']
                # Si la métrica es "más es mejor" (ej: pasos), alerta si promedio < 80% objetivo
                # Si es "menos es mejor" (ej: peso, presión), alerta si promedio > 120% objetivo
                # Aquí puedes personalizar según el tipo de métrica
                if nombre.lower() in ["pasos", "agua", "ejercicio", "actividad"]:
                    if promedio < objetivo_val * 0.8:
                        alerta = "¡Alerta! Tu promedio de {} está por debajo del rango saludable.".format(nombre)
                else:
                    if promedio > objetivo_val * 1.2:
                        alerta = "¡Alerta! Tu promedio de {} está por encima del rango saludable.".format(nombre)
            except Exception:
                pass
        alertas[nombre] = alerta

    # Calcular métricas de hoy independientemente de los filtros (rango robusto)
    from datetime import datetime, timedelta
    today = date.today()
    tomorrow = today + timedelta(days=1)
    metricas_hoy = Metrica.query.filter(
        Metrica.usuario_id == current_user.id,
        Metrica.fecha >= today,
        Metrica.fecha < tomorrow
    ).count()
    
    # Obtener rangos saludables basados en el perfil del usuario
    from app.models import PerfilUsuario
    perfil = PerfilUsuario.query.filter_by(usuario_id=current_user.id).first()
    rangos_saludables = None
    if perfil and perfil.altura:
        rangos_saludables = calcular_rangos_saludables(perfil)
    
    return render_template('dashboard.html', metricas=metricas, metricas_json=metricas_json, total_categorias=total_categorias, stats=stats, objetivos=objetivos, tendencias=tendencias, alertas=alertas, metricas_hoy=metricas_hoy, date=date, rangos_saludables=rangos_saludables, perfil=perfil)

# Ruta para login
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        correo = request.form['correo']
        contraseña = request.form['contraseña']
        usuario = Usuario.query.filter_by(email=correo).first()
        # Aquí debes comparar la contraseña correctamente, dependiendo de cómo la guardes
        if usuario and usuario.password == contraseña:
            login_user(usuario)
            session['show_intro'] = True
            flash('¡Has iniciado sesión exitosamente!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Correo o contraseña incorrectos', 'danger')
    return render_template('login.html')

# Ruta para registro
@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        correo = request.form['correo'].strip()
        contraseña = request.form['contraseña']
        confirmar_contraseña = request.form['confirmar_contraseña']
        # Check if username or email already exists
        if Usuario.query.filter_by(username=nombre).first():
            flash('El nombre de usuario ya está en uso. Elige otro.', 'danger')
            return render_template('register.html')
        if Usuario.query.filter_by(email=correo).first():
            flash('El correo electrónico ya está en uso. Elige otro.', 'danger')
            return render_template('register.html')
        if contraseña == confirmar_contraseña:
            usuario = Usuario(username=nombre, email=correo)
            usuario.password = contraseña  # O usa usuario.set_password(contraseña) si tienes hashing
            db.session.add(usuario)
            db.session.commit()
            flash('¡Te has registrado exitosamente! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('main.login'))
        else:
            flash('Las contraseñas no coinciden', 'danger')
    return render_template('register.html')

# Ruta para agregar nueva métrica
@main.route('/agregar_metrica', methods=['GET', 'POST'])
@login_required
def agregar_metrica():
    from app.models import Categoria
    categorias = Categoria.query.order_by(Categoria.nombre).all()
    if request.method == 'POST':
        tipo = request.form['tipo']
        valor = request.form['valor']
        unidad = request.form.get('unidad', '')
        nota = request.form.get('nota', '')
        categoria_id = request.form.get('categoria_id')
        fecha_str = request.form.get('fecha')
        try:
            fecha_real = date.fromisoformat(fecha_str) if fecha_str else date.today()
        except Exception:
            fecha_real = date.today()
        metrica = Metrica(usuario_id=current_user.id, nombre=tipo, valor=valor, unidad=unidad, nota=nota, categoria_id=categoria_id, fecha=fecha_real)
        db.session.add(metrica)
        db.session.commit()
        flash('¡Métrica agregada exitosamente!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('agregar_metrica.html', categorias=categorias)

# Editar métrica
@main.route('/editar_metrica/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_metrica(id):
    from app.models import Categoria
    metrica = Metrica.query.get_or_404(id)
    categorias = Categoria.query.order_by(Categoria.nombre).all()
    if metrica.usuario_id != current_user.id:
        flash('No tienes permiso para editar esta métrica.', 'danger')
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        metrica.nombre = request.form['tipo']
        metrica.valor = request.form['valor']
        metrica.unidad = request.form.get('unidad', '')
        metrica.nota = request.form.get('nota', '')
        metrica.categoria_id = request.form.get('categoria_id')
        db.session.commit()
        flash('Métrica actualizada exitosamente.', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('editar_metrica.html', metrica=metrica, categorias=categorias)

# Eliminar métrica
@main.route('/eliminar_metrica/<int:id>', methods=['POST'])
@login_required
def eliminar_metrica(id):
    metrica = Metrica.query.get_or_404(id)
    if metrica.usuario_id != current_user.id:
        flash('No tienes permiso para eliminar esta métrica.', 'danger')
        return redirect(url_for('main.dashboard'))
    db.session.delete(metrica)
    db.session.commit()
    flash('Métrica eliminada exitosamente.', 'success')
    return redirect(url_for('main.dashboard'))

# Ruta para cerrar sesión
@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión', 'danger')
    return redirect(url_for('main.login'))

# ----------------------
# CRUD de Categorías
# ----------------------
from app.models import Categoria

@main.route('/categorias')
@login_required
def categories():
    categorias = Categoria.query.order_by(Categoria.nombre).all()
    return render_template('categories.html', categorias=categorias)

@main.route('/categorias/add', methods=['POST'])
@login_required
def add_category():
    nombre = request.form['nombre'].strip()
    if not nombre:
        flash('El nombre de la categoría no puede estar vacío.', 'danger')
        return redirect(url_for('main.categories'))
    if Categoria.query.filter_by(nombre=nombre).first():
        flash('Ya existe una categoría con ese nombre.', 'danger')
        return redirect(url_for('main.categories'))
    categoria = Categoria(nombre=nombre)
    db.session.add(categoria)
    db.session.commit()
    flash('Categoría agregada exitosamente.', 'success')
    return redirect(url_for('main.categories'))

@main.route('/categorias/edit/<int:id>', methods=['POST'])
@login_required
def edit_category(id):
    categoria = Categoria.query.get_or_404(id)
    nuevo_nombre = request.form['nuevo_nombre'].strip()
    if not nuevo_nombre:
        flash('El nombre no puede estar vacío.', 'danger')
        return redirect(url_for('main.categories'))
    if Categoria.query.filter(Categoria.nombre==nuevo_nombre, Categoria.id!=id).first():
        flash('Ya existe otra categoría con ese nombre.', 'danger')
        return redirect(url_for('main.categories'))
    categoria.nombre = nuevo_nombre
    db.session.commit()
    flash('Categoría actualizada.', 'success')
    return redirect(url_for('main.categories'))

@main.route('/categorias/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    categoria = Categoria.query.get_or_404(id)
    db.session.delete(categoria)
    db.session.commit()
    flash('Categoría eliminada.', 'success')
    return redirect(url_for('main.categories'))

@main.route('/exportar_metricas/<formato>')
@login_required
def exportar_metricas(formato):
    metricas = Metrica.query.filter_by(usuario_id=current_user.id).all()
    data = []
    for m in metricas:
        data.append({
            'Nombre': m.nombre,
            'Valor': m.valor,
            'Unidad': m.unidad,
            'Categoría': m.categoria.nombre if m.categoria else '',
            'Nota': m.nota,
            'Fecha': m.fecha.strftime('%Y-%m-%d') if m.fecha else ''
        })
    df = pd.DataFrame(data)
    if formato == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='metricas.csv'
        )
    elif formato == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Métricas')
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='metricas.xlsx'
        )
    else:
        flash('Formato no soportado', 'danger')
        return redirect(url_for('main.dashboard'))

@main.route('/importar_metricas', methods=['POST'])
@login_required
def importar_metricas():
    from app.models import Categoria
    archivo = request.files.get('archivo')
    if not archivo:
        flash('No se seleccionó ningún archivo', 'danger')
        return redirect(url_for('main.dashboard'))
    try:
        if archivo.filename.endswith('.csv'):
            df = pd.read_csv(archivo)
        elif archivo.filename.endswith('.xlsx'):
            df = pd.read_excel(archivo)
        else:
            flash('Formato de archivo no soportado', 'danger')
            return redirect(url_for('main.dashboard'))
        for _, row in df.iterrows():
            nombre = row.get('Nombre')
            valor = row.get('Valor')
            unidad = row.get('Unidad')
            categoria_nombre = row.get('Categoría')
            nota = row.get('Nota')
            fecha = row.get('Fecha')
            categoria = None
            if categoria_nombre and not pd.isna(categoria_nombre):
                categoria = Categoria.query.filter_by(nombre=categoria_nombre).first()
                if not categoria:
                    categoria = Categoria(nombre=categoria_nombre)
                    db.session.add(categoria)
                    db.session.flush()
            metrica = Metrica(
                usuario_id=current_user.id,
                nombre=nombre,
                valor=valor,
                unidad=unidad,
                categoria_id=categoria.id if categoria else None,
                nota=nota,
                fecha=pd.to_datetime(fecha).date() if pd.notnull(fecha) and fecha else None
            )
            db.session.add(metrica)
        db.session.commit()
        flash('Métricas importadas correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al importar: {e}', 'danger')
    return redirect(url_for('main.dashboard'))

@main.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    from app.models import PerfilUsuario
    
    perfil_usuario = PerfilUsuario.query.filter_by(usuario_id=current_user.id).first()
    
    if request.method == 'POST':
        edad = request.form.get('edad')
        altura = request.form.get('altura')
        genero = request.form.get('genero')
        nivel_actividad = request.form.get('nivel_actividad')
        notas = request.form.get('notas')
        
        if perfil_usuario:
            # Actualizar perfil existente
            perfil_usuario.edad = int(edad) if edad else None
            perfil_usuario.altura = float(altura) if altura else None
            perfil_usuario.genero = genero
            perfil_usuario.nivel_actividad = nivel_actividad
            perfil_usuario.notas = notas
        else:
            # Crear nuevo perfil
            perfil_usuario = PerfilUsuario(
                usuario_id=current_user.id,
                edad=int(edad) if edad else None,
                altura=float(altura) if altura else None,
                genero=genero,
                nivel_actividad=nivel_actividad,
                notas=notas
            )
            db.session.add(perfil_usuario)
        
        db.session.commit()
        flash('Perfil actualizado correctamente', 'success')
        return redirect(url_for('main.perfil'))
    
    # Calcular rangos recomendados si hay perfil
    rangos = None
    if perfil_usuario and perfil_usuario.altura:
        rangos = calcular_rangos_saludables(perfil_usuario)
    
    return render_template('perfil.html', perfil=perfil_usuario, rangos=rangos)

def calcular_rangos_saludables(perfil):
    """Calcula rangos saludables basados en el perfil del usuario"""
    rangos = {}
    
    if perfil.altura:
        altura_m = perfil.altura / 100  # convertir cm a metros
        
        # Rango de peso saludable según IMC (18.5 - 24.9)
        peso_min = 18.5 * (altura_m ** 2)
        peso_max = 24.9 * (altura_m ** 2)
        rangos['peso'] = {
            'min': round(peso_min, 1),
            'max': round(peso_max, 1),
            'ideal': round((peso_min + peso_max) / 2, 1),
            'unidad': 'kg',
            'descripcion': f'Rango saludable según IMC (18.5-24.9)'
        }
    
    # Rangos de presión arterial
    rangos['presion_sistolica'] = {
        'min': 90,
        'max': 120,
        'ideal': 110,
        'unidad': 'mmHg',
        'descripcion': 'Presión sistólica normal'
    }
    
    rangos['presion_diastolica'] = {
        'min': 60,
        'max': 80,
        'ideal': 70,
        'unidad': 'mmHg',
        'descripcion': 'Presión diastólica normal'
    }
    
    # Glucosa en ayunas
    rangos['glucosa'] = {
        'min': 70,
        'max': 100,
        'ideal': 85,
        'unidad': 'mg/dL',
        'descripcion': 'Glucosa en ayunas normal'
    }
    
    # Frecuencia cardíaca en reposo
    if perfil.edad:
        if perfil.edad < 30:
            fc_ideal = 70
        elif perfil.edad < 50:
            fc_ideal = 72
        else:
            fc_ideal = 75
        
        rangos['frecuencia_cardiaca'] = {
            'min': 60,
            'max': 100,
            'ideal': fc_ideal,
            'unidad': 'bpm',
            'descripcion': 'Frecuencia cardíaca en reposo'
        }
    
    # Horas de sueño recomendadas según edad
    if perfil.edad:
        if perfil.edad < 18:
            sueño_min, sueño_max = 8, 10
        elif perfil.edad < 65:
            sueño_min, sueño_max = 7, 9
        else:
            sueño_min, sueño_max = 7, 8
        
        rangos['horas_sueño'] = {
            'min': sueño_min,
            'max': sueño_max,
            'ideal': (sueño_min + sueño_max) / 2,
            'unidad': 'horas',
            'descripcion': 'Sueño recomendado'
        }
    
    # Pasos diarios según nivel de actividad
    if perfil.nivel_actividad:
        if perfil.nivel_actividad == 'sedentario':
            pasos = 5000
        elif perfil.nivel_actividad == 'ligero':
            pasos = 7500
        elif perfil.nivel_actividad == 'moderado':
            pasos = 10000
        elif perfil.nivel_actividad == 'activo':
            pasos = 12500
        else:  # muy_activo
            pasos = 15000
        
        rangos['pasos'] = {
            'min': pasos - 2000,
            'max': pasos + 2000,
            'ideal': pasos,
            'unidad': 'pasos',
            'descripcion': f'Objetivo de pasos ({perfil.nivel_actividad})'
        }
    
    return rangos
