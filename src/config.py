"""
Módulo de configuración.

Lee el archivo config.yaml y expone los parámetros como un diccionario
accesible en todo el proyecto.  Las rutas relativas se resuelven desde
el directorio raíz del proyecto (directorio que contiene este módulo).
"""

import os
import yaml

# Directorio raíz del proyecto (directorio que contiene src/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.yaml")


def load_config(path: str = CONFIG_PATH) -> dict:
    """Carga y retorna la configuración desde un archivo YAML."""
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def resolve_path(relative_path: str) -> str:
    """Resuelve una ruta relativa al directorio raíz del proyecto."""
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.join(ROOT_DIR, relative_path)
