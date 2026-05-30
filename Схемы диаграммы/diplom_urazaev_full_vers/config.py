import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # Используем относительный путь для SQLite (папка instance/ будет создана автоматически)
    # Формат: sqlite:///./instance/filename.db для относительного пути
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, 'instance')
    # Создаем папку instance, если её нет
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir, exist_ok=True)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(instance_dir, "planeta_shop.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False