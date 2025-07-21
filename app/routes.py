from flask import render_template, redirect, url_for, flash, request, Blueprint
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

@main.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():
    from app.models import Categoria, Objetivo
    # Guardar/actualizar objetivos
    if request.method == 'POST' and 'objetivo_metrica' in request.form:
        nombre_metrica = request.form['objetivo_metrica']
        valor_objetivo = request.form['valor_objetivo']
        unidad = request.form.get('unidad_objetivo', '')
        if nombre_metrica and valor_objetivo:
            obj = Objetivo.query.filter_by(usuario_id=current_user.id, nombre_metrica=nombre_metrica).first()
            if obj:
                obj.valor_objetivo = valor_objetivo
                obj.unidad = unidad
            else:
                obj = Objetivo(usuario_id=current_user.id, nombre_metrica=nombre_metrica, valor_objetivo=valor_objetivo, unidad=unidad)
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
    metricas = Metrica.query.filter(and_(*filtros)).order_by(Metrica.fecha.asc()).all()
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
        data['promedio'] = round(sum(valores) / len(valores), 2) if valores else 0
        data['maximo'] = max(valores) if valores else 0
        data['minimo'] = min(valores) if valores else 0

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

    # Calcular métricas de hoy independientemente de los filtros
    metricas_hoy = Metrica.query.filter(
        Metrica.usuario_id == current_user.id,
        Metrica.fecha == date.today()
    ).count()
    return render_template('dashboard.html', metricas=metricas, metricas_json=metricas_json, total_categorias=total_categorias, stats=stats, objetivos=objetivos, tendencias=tendencias, alertas=alertas, metricas_hoy=metricas_hoy, date=date)

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
    flash('Has cerrado sesión', 'info')
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