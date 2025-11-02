from . import db
from flask_login import UserMixin
from datetime import datetime, date

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    perfil = db.relationship('PerfilUsuario', backref='usuario', uselist=False, lazy=True)

class PerfilUsuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, unique=True)
    edad = db.Column(db.Integer, nullable=True)
    altura = db.Column(db.Float, nullable=True)  # en cm
    genero = db.Column(db.String(20), nullable=True)  # 'masculino', 'femenino', 'otro'
    nivel_actividad = db.Column(db.String(20), nullable=True)  # 'sedentario', 'ligero', 'moderado', 'activo', 'muy_activo'
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    notas = db.Column(db.Text, nullable=True)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), unique=True, nullable=False)
    metricas = db.relationship('Metrica', backref='categoria', lazy=True)

class Metrica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    unidad = db.Column(db.String(20), nullable=True)
    nota = db.Column(db.Text, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=True)
    fecha = db.Column(db.Date, default=date.today)

class Objetivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nombre_metrica = db.Column(db.String(64), nullable=False)
    valor_inicial = db.Column(db.Float, nullable=True)  # Valor de partida
    valor_objetivo = db.Column(db.Float, nullable=False)  # Valor meta
    unidad = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(10), default='aumentar')  # 'aumentar' o 'disminuir'
    __table_args__ = (db.UniqueConstraint('usuario_id', 'nombre_metrica', name='uq_objetivo_usuario_metrica'),)
