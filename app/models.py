from . import db
from flask_login import UserMixin
from datetime import datetime, date

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

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
    valor_objetivo = db.Column(db.Float, nullable=False)
    unidad = db.Column(db.String(20), nullable=True)
    __table_args__ = (db.UniqueConstraint('usuario_id', 'nombre_metrica', name='uq_objetivo_usuario_metrica'),)
