"""
Script de creación de la base de datos SQLite del sistema CUN (cun_sistema.db).

Usa las mismas clases de main.py (ConexionSQLite y el servicio MesaAyudaTI),
por lo que el esquema generado es exactamente el que espera el código POO.

Ejecución:
    python crear_base_datos.py            -> crea tablas y carga datos de ejemplo
    python crear_base_datos.py --vacia    -> crea solo las tablas (sin datos)
"""

import argparse
import os

from main import (
    NOMBRE_BD,
    ErrorCUN,
    EstadoTicket,
    MesaAyudaTI,
    crear_repositorios_sqlite,
)

ESTUDIANTES_EJEMPLO = [
    ("10184321", "Laura Gómez", "Ingeniería de Sistemas", 4.2),
    ("10299876", "Ana Martínez", "Contaduría Pública", 3.8),
    ("10355412", "Juan Pérez", "Ingeniería de Sistemas", 4.5),
    ("10477890", "Camila Rojas", "Administración de Empresas", 3.9),
]

TICKETS_EJEMPLO = [
    ("10184321", "REDES", "No hay conexión WiFi en el aula 301"),
    ("10299876", "CUENTAS", "No puedo ingresar al aula virtual"),
    ("10355412", "SOFTWARE", "Error al instalar el IDE en el laboratorio 2"),
    ("10477890", "HARDWARE", "El proyector del aula 105 no enciende"),
    ("10184321", "AULAS", "Solicito cambio de aula para la clase de POO"),
]


def crear_base_datos(sembrar: bool = True) -> None:
    repo_est, repo_tic, conexion = crear_repositorios_sqlite(NOMBRE_BD)
    try:
        if sembrar and (repo_est.listar() or repo_tic.listar()):
            print("[Aviso] La base de datos ya tiene registros; no se cargan datos de ejemplo.")
            sembrar = False
        if sembrar:
            mesa = MesaAyudaTI(repo_est, repo_tic)
            for datos in ESTUDIANTES_EJEMPLO:
                try:
                    mesa.registrar_estudiante(*datos)
                except ErrorCUN as err:
                    print(f"[Aviso] {err}")
            for datos in TICKETS_EJEMPLO:
                try:
                    mesa.crear_ticket(*datos)
                except ErrorCUN as err:
                    print(f"[Aviso] {err}")
            # Un ticket en proceso y otro cerrado para tener variedad de estados
            mesa.cambiar_estado_ticket(1, EstadoTicket.EN_PROCESO)
            mesa.cambiar_estado_ticket(2, EstadoTicket.EN_PROCESO)
            mesa.cambiar_estado_ticket(2, EstadoTicket.CERRADO)
    finally:
        conexion.cerrar()
    print(f"[Exitoso] Base de datos '{NOMBRE_BD}' creada correctamente "
          f"({os.path.abspath(NOMBRE_BD)}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crea la base de datos cun_sistema.db")
    parser.add_argument("--vacia", action="store_true",
                        help="Crea solo las tablas, sin datos de ejemplo")
    args = parser.parse_args()
    crear_base_datos(sembrar=not args.vacia)
