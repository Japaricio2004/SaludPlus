import os
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave_secreta_segura'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///seguimiento.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

