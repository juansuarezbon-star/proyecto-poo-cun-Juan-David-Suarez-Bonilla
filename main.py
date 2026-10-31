"""
Sistema de Mesa de Ayuda TI y Gestión Académica - CUN
Ingeniería de Sistemas - Programación Orientada a Objetos

Arquitectura (pensada para conectarse a la base de datos sin cambiar el dominio):

    Modelos (POO)  ->  Servicio (reglas de negocio)  ->  Repositorio (persistencia)
                                                          |- RepositorioMemoria  (por defecto)
                                                          |- RepositorioSQLite   (cun_sistema.db)

Para usar la base de datos basta con cambiar UNA línea en main():
    repo_est, repo_tic = crear_repositorios_memoria()   # modo memoria
    repo_est, repo_tic = crear_repositorios_sqlite()    # modo SQLite
"""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Generic, Iterator, List, Optional, TypeVar

NOMBRE_BD = "cun_sistema.db"


# ======================================================================
# 1. EXCEPCIONES PERSONALIZADAS
# ======================================================================
class ErrorCUN(Exception):
    """Excepción base del sistema."""


class ErrorValidacion(ErrorCUN):
    """Datos de entrada inválidos."""


class ErrorNoEncontrado(ErrorCUN):
    """El registro solicitado no existe."""


class ErrorDuplicado(ErrorCUN):
    """Ya existe un registro con esa llave."""


# ======================================================================
# 2. MODELOS DE DOMINIO (Encapsulamiento, Herencia, Polimorfismo)
# ======================================================================
def _texto_obligatorio(valor: str, campo: str) -> str:
    """Valida que un texto no esté vacío y lo devuelve limpio."""
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorValidacion(f"El campo '{campo}' es obligatorio.")
    return valor.strip()


class UsuarioCUN(ABC):
    """Clase abstracta base: define el contrato común de los usuarios."""

    def __init__(self, id_usuario: str, nombre: str, email: str = "") -> None:
        self._id_usuario = _texto_obligatorio(id_usuario, "id_usuario")
        self._nombre = _texto_obligatorio(nombre, "nombre")
        self._email = email.strip()

    @property
    def id_usuario(self) -> str:
        return self._id_usuario

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def email(self) -> str:
        return self._email

    @abstractmethod
    def obtener_rol(self) -> str:
        """Cada subclase describe su rol (polimorfismo)."""

    def __str__(self) -> str:
        return f"[{self._id_usuario}] {self._nombre} - {self.obtener_rol()}"


class Estudiante(UsuarioCUN):
    """Estudiante con promedio protegido (atributo privado)."""

    PROMEDIO_MIN = 0.0
    PROMEDIO_MAX = 5.0

    def __init__(self, id_estudiante: str, nombre: str, programa: str,
                 promedio: float = 0.0, email: str = "") -> None:
        super().__init__(id_estudiante, nombre, email)
        self._programa = _texto_obligatorio(programa, "programa")
        self.__promedio = 0.0
        self.promedio = promedio  # pasa por el setter con validación

    # --- Encapsulamiento del promedio ---
    @property
    def promedio(self) -> float:
        return self.__promedio

    @promedio.setter
    def promedio(self, valor: float) -> None:
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            raise ErrorValidacion("El promedio debe ser numérico.") from None
        if not self.PROMEDIO_MIN <= valor <= self.PROMEDIO_MAX:
            raise ErrorValidacion(
                f"El promedio debe estar entre {self.PROMEDIO_MIN} y {self.PROMEDIO_MAX}."
            )
        self.__promedio = round(valor, 2)

    @property
    def programa(self) -> str:
        return self._programa

    def obtener_rol(self) -> str:
        return f"Estudiante del programa {self._programa}"


class Docente(UsuarioCUN):
    """Docente de la facultad."""

    def __init__(self, id_docente: str, nombre: str, especialidad: str, email: str = "") -> None:
        super().__init__(id_docente, nombre, email)
        self._especialidad = _texto_obligatorio(especialidad, "especialidad")

    @property
    def especialidad(self) -> str:
        return self._especialidad

    def obtener_rol(self) -> str:
        return f"Docente de {self._especialidad}"


class EstadoTicket(str, Enum):
    ABIERTO = "ABIERTO"
    EN_PROCESO = "EN_PROCESO"
    CERRADO = "CERRADO"


# Transiciones permitidas: evita estados incoherentes.
_TRANSICIONES = {
    EstadoTicket.ABIERTO: {EstadoTicket.EN_PROCESO, EstadoTicket.CERRADO},
    EstadoTicket.EN_PROCESO: {EstadoTicket.CERRADO},
    EstadoTicket.CERRADO: set(),
}


class TicketSoporte:
    """Ticket de soporte TI asociado a un estudiante."""

    CATEGORIAS = ("HARDWARE", "SOFTWARE", "REDES", "CUENTAS", "AULAS", "OTRO")

    def __init__(self, id_estudiante: str, categoria: str, descripcion: str,
                 estado: EstadoTicket | str = EstadoTicket.ABIERTO,
                 id_ticket: Optional[int] = None) -> None:
        self._id_ticket = id_ticket  # lo asigna el repositorio / la BD (AUTOINCREMENT)
        self._id_estudiante = _texto_obligatorio(id_estudiante, "id_estudiante")

        categoria = _texto_obligatorio(categoria, "categoria").upper()
        if categoria not in self.CATEGORIAS:
            raise ErrorValidacion(f"Categoría inválida. Opciones: {', '.join(self.CATEGORIAS)}")
        self._categoria = categoria

        self._descripcion = _texto_obligatorio(descripcion, "descripcion")
        self._estado = EstadoTicket(estado)

    @property
    def id_ticket(self) -> Optional[int]:
        return self._id_ticket

    @id_ticket.setter
    def id_ticket(self, valor: int) -> None:
        if self._id_ticket is not None:
            raise ErrorValidacion("El ticket ya tiene un identificador asignado.")
        self._id_ticket = valor

    @property
    def id_estudiante(self) -> str:
        return self._id_estudiante

    @property
    def categoria(self) -> str:
        return self._categoria

    @property
    def descripcion(self) -> str:
        return self._descripcion

    @property
    def estado(self) -> EstadoTicket:
        return self._estado

    def cambiar_estado(self, nuevo: EstadoTicket) -> None:
        nuevo = EstadoTicket(nuevo)
        if nuevo not in _TRANSICIONES[self._estado]:
            raise ErrorValidacion(
                f"Transición no permitida: {self._estado.value} -> {nuevo.value}"
            )
        self._estado = nuevo

    def __str__(self) -> str:
        return (f"Ticket #{self._id_ticket} | {self._categoria} | "
                f"{self._estado.value} | Est: {self._id_estudiante} | {self._descripcion}")


# ======================================================================
# 3. CAPA DE PERSISTENCIA (patrón Repositorio)
# ======================================================================
T = TypeVar("T")


class Repositorio(ABC, Generic[T]):
    """Contrato genérico: el resto del sistema solo conoce esta interfaz."""

    @abstractmethod
    def guardar(self, entidad: T) -> T: ...

    @abstractmethod
    def obtener(self, llave) -> T: ...

    @abstractmethod
    def listar(self) -> List[T]: ...


class RepositorioEstudiantes(Repositorio[Estudiante], ABC):
    @abstractmethod
    def actualizar(self, estudiante: Estudiante) -> None: ...


class RepositorioTickets(Repositorio[TicketSoporte], ABC):
    @abstractmethod
    def listar_por_estudiante(self, id_estudiante: str) -> List[TicketSoporte]: ...

    @abstractmethod
    def actualizar(self, ticket: TicketSoporte) -> None: ...


# ---------- Implementación en memoria (sin BD) ----------
class RepositorioEstudiantesMemoria(RepositorioEstudiantes):
    def __init__(self) -> None:
        self._datos: Dict[str, Estudiante] = {}

    def guardar(self, entidad: Estudiante) -> Estudiante:
        if entidad.id_usuario in self._datos:
            raise ErrorDuplicado(f"Ya existe el estudiante {entidad.id_usuario}.")
        self._datos[entidad.id_usuario] = entidad
        return entidad

    def obtener(self, llave: str) -> Estudiante:
        try:
            return self._datos[llave]
        except KeyError:
            raise ErrorNoEncontrado(f"Estudiante {llave} no encontrado.") from None

    def listar(self) -> List[Estudiante]:
        return list(self._datos.values())

    def actualizar(self, estudiante: Estudiante) -> None:
        self.obtener(estudiante.id_usuario)
        self._datos[estudiante.id_usuario] = estudiante


class RepositorioTicketsMemoria(RepositorioTickets):
    def __init__(self) -> None:
        self._datos: Dict[int, TicketSoporte] = {}
        self._siguiente = 1

    def guardar(self, entidad: TicketSoporte) -> TicketSoporte:
        entidad.id_ticket = self._siguiente
        self._datos[self._siguiente] = entidad
        self._siguiente += 1
        return entidad

    def obtener(self, llave: int) -> TicketSoporte:
        try:
            return self._datos[llave]
        except KeyError:
            raise ErrorNoEncontrado(f"Ticket {llave} no encontrado.") from None

    def listar(self) -> List[TicketSoporte]:
        return list(self._datos.values())

    def listar_por_estudiante(self, id_estudiante: str) -> List[TicketSoporte]:
        return [t for t in self._datos.values() if t.id_estudiante == id_estudiante]

    def actualizar(self, ticket: TicketSoporte) -> None:
        self.obtener(ticket.id_ticket)
        self._datos[ticket.id_ticket] = ticket


# ---------- Implementación SQLite (cun_sistema.db) ----------
class ConexionSQLite:
    """Administra la conexión y crea las tablas del taller si no existen."""

    def __init__(self, ruta: str = NOMBRE_BD) -> None:
        self.ruta = ruta
        self._conn = sqlite3.connect(ruta)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._crear_tablas()

    def _crear_tablas(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS estudiantes (
                    id_estudiante TEXT PRIMARY KEY,
                    nombre        TEXT NOT NULL,
                    programa      TEXT NOT NULL,
                    promedio      REAL DEFAULT 0.0
                )""")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tickets_soporte (
                    id_ticket     INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_estudiante TEXT NOT NULL,
                    categoria     TEXT NOT NULL,
                    descripcion   TEXT NOT NULL,
                    estado        TEXT DEFAULT 'ABIERTO',
                    FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
                )""")

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def cerrar(self) -> None:
        self._conn.close()


class RepositorioEstudiantesSQLite(RepositorioEstudiantes):
    def __init__(self, conexion: ConexionSQLite) -> None:
        self._c = conexion.conn

    @staticmethod
    def _a_objeto(fila: sqlite3.Row) -> Estudiante:
        return Estudiante(fila["id_estudiante"], fila["nombre"],
                          fila["programa"], fila["promedio"])

    def guardar(self, entidad: Estudiante) -> Estudiante:
        try:
            with self._c:
                self._c.execute(
                    "INSERT INTO estudiantes (id_estudiante, nombre, programa, promedio) "
                    "VALUES (?, ?, ?, ?)",
                    (entidad.id_usuario, entidad.nombre, entidad.programa, entidad.promedio))
        except sqlite3.IntegrityError:
            raise ErrorDuplicado(f"Ya existe el estudiante {entidad.id_usuario}.") from None
        return entidad

    def obtener(self, llave: str) -> Estudiante:
        fila = self._c.execute(
            "SELECT * FROM estudiantes WHERE id_estudiante = ?", (llave,)).fetchone()
        if fila is None:
            raise ErrorNoEncontrado(f"Estudiante {llave} no encontrado.")
        return self._a_objeto(fila)

    def listar(self) -> List[Estudiante]:
        filas = self._c.execute("SELECT * FROM estudiantes ORDER BY nombre").fetchall()
        return [self._a_objeto(f) for f in filas]

    def actualizar(self, estudiante: Estudiante) -> None:
        with self._c:
            cur = self._c.execute(
                "UPDATE estudiantes SET nombre = ?, programa = ?, promedio = ? "
                "WHERE id_estudiante = ?",
                (estudiante.nombre, estudiante.programa, estudiante.promedio,
                 estudiante.id_usuario))
        if cur.rowcount == 0:
            raise ErrorNoEncontrado(f"Estudiante {estudiante.id_usuario} no encontrado.")


class RepositorioTicketsSQLite(RepositorioTickets):
    def __init__(self, conexion: ConexionSQLite) -> None:
        self._c = conexion.conn

    @staticmethod
    def _a_objeto(fila: sqlite3.Row) -> TicketSoporte:
        return TicketSoporte(fila["id_estudiante"], fila["categoria"],
                             fila["descripcion"], fila["estado"], fila["id_ticket"])

    def guardar(self, entidad: TicketSoporte) -> TicketSoporte:
        try:
            with self._c:
                cur = self._c.execute(
                    "INSERT INTO tickets_soporte (id_estudiante, categoria, descripcion, estado) "
                    "VALUES (?, ?, ?, ?)",
                    (entidad.id_estudiante, entidad.categoria,
                     entidad.descripcion, entidad.estado.value))
        except sqlite3.IntegrityError:
            raise ErrorNoEncontrado(
                f"Estudiante {entidad.id_estudiante} no existe.") from None
        entidad.id_ticket = cur.lastrowid
        return entidad

    def obtener(self, llave: int) -> TicketSoporte:
        fila = self._c.execute(
            "SELECT * FROM tickets_soporte WHERE id_ticket = ?", (llave,)).fetchone()
        if fila is None:
            raise ErrorNoEncontrado(f"Ticket {llave} no encontrado.")
        return self._a_objeto(fila)

    def listar(self) -> List[TicketSoporte]:
        filas = self._c.execute("SELECT * FROM tickets_soporte ORDER BY id_ticket").fetchall()
        return [self._a_objeto(f) for f in filas]

    def listar_por_estudiante(self, id_estudiante: str) -> List[TicketSoporte]:
        filas = self._c.execute(
            "SELECT * FROM tickets_soporte WHERE id_estudiante = ? ORDER BY id_ticket",
            (id_estudiante,)).fetchall()
        return [self._a_objeto(f) for f in filas]

    def actualizar(self, ticket: TicketSoporte) -> None:
        with self._c:
            cur = self._c.execute(
                "UPDATE tickets_soporte SET estado = ? WHERE id_ticket = ?",
                (ticket.estado.value, ticket.id_ticket))
        if cur.rowcount == 0:
            raise ErrorNoEncontrado(f"Ticket {ticket.id_ticket} no encontrado.")


# ---------- Fábricas: único punto que cambia al migrar a BD ----------
def crear_repositorios_memoria():
    return RepositorioEstudiantesMemoria(), RepositorioTicketsMemoria()


def crear_repositorios_sqlite(ruta: str = NOMBRE_BD):
    conexion = ConexionSQLite(ruta)
    return RepositorioEstudiantesSQLite(conexion), RepositorioTicketsSQLite(conexion), conexion


# ======================================================================
# 4. SERVICIO (reglas de negocio) - COMPOSICIÓN
# ======================================================================
class MesaAyudaTI:
    """
    Coordina estudiantes y tickets. Depende de las INTERFACES de los
    repositorios (inyección de dependencias), por eso no sabe si los
    datos están en memoria o en SQLite. Bajo acoplamiento (CBO).
    """

    def __init__(self, repo_estudiantes: RepositorioEstudiantes,
                 repo_tickets: RepositorioTickets) -> None:
        self._estudiantes = repo_estudiantes
        self._tickets = repo_tickets

    def registrar_estudiante(self, id_estudiante: str, nombre: str, programa: str,
                             promedio: float = 0.0) -> Estudiante:
        return self._estudiantes.guardar(Estudiante(id_estudiante, nombre, programa, promedio))

    def actualizar_promedio(self, id_estudiante: str, nuevo_promedio: float) -> Estudiante:
        est = self._estudiantes.obtener(id_estudiante)
        est.promedio = nuevo_promedio
        self._estudiantes.actualizar(est)
        return est

    def crear_ticket(self, id_estudiante: str, categoria: str, descripcion: str) -> TicketSoporte:
        self._estudiantes.obtener(id_estudiante)  # valida que el estudiante exista
        return self._tickets.guardar(TicketSoporte(id_estudiante, categoria, descripcion))

    def cambiar_estado_ticket(self, id_ticket: int, nuevo_estado: EstadoTicket) -> TicketSoporte:
        ticket = self._tickets.obtener(id_ticket)
        ticket.cambiar_estado(nuevo_estado)
        self._tickets.actualizar(ticket)
        return ticket

    def tickets_de(self, id_estudiante: str) -> List[TicketSoporte]:
        self._estudiantes.obtener(id_estudiante)
        return self._tickets.listar_por_estudiante(id_estudiante)

    def listar_estudiantes(self) -> List[Estudiante]:
        return self._estudiantes.listar()

    def listar_tickets(self) -> List[TicketSoporte]:
        return self._tickets.listar()


# ======================================================================
# 5. PROGRAMA PRINCIPAL (demostración)
# ======================================================================
def _intentar(descripcion: str, accion) -> None:
    """Ejecuta una acción mostrando el error en lugar de romper el programa."""
    try:
        resultado = accion()
        print(f"[OK]    {descripcion}" + (f" -> {resultado}" if resultado else ""))
    except ErrorCUN as err:
        print(f"[ERROR] {descripcion}: {err}")


def main() -> None:
    # --- Elegir persistencia: cambiar SOLO este bloque ---------------------
    USAR_SQLITE = False
    conexion = None
    if USAR_SQLITE:
        repo_est, repo_tic, conexion = crear_repositorios_sqlite()
    else:
        repo_est, repo_tic = crear_repositorios_memoria()
    # -----------------------------------------------------------------------

    mesa = MesaAyudaTI(repo_est, repo_tic)

    print("=== Registro de estudiantes ===")
    _intentar("Registrar Laura", lambda: mesa.registrar_estudiante("10184321", "Laura Gómez", "Sistemas", 4.2))
    _intentar("Registrar Ana", lambda: mesa.registrar_estudiante("10299876", "Ana Martínez", "Contaduría", 3.8))
    _intentar("Registrar duplicado", lambda: mesa.registrar_estudiante("10184321", "Otra", "Sistemas"))
    _intentar("Promedio inválido", lambda: mesa.actualizar_promedio("10184321", 6.0))

    print("\n=== Tickets de soporte ===")
    t1 = mesa.crear_ticket("10184321", "redes", "No hay conexión WiFi en el aula 301")
    mesa.crear_ticket("10299876", "cuentas", "No puedo ingresar al aula virtual")
    _intentar("Ticket a estudiante inexistente", lambda: mesa.crear_ticket("999", "software", "x"))
    _intentar("Categoría inválida", lambda: mesa.crear_ticket("10184321", "magia", "x"))

    _intentar("ABIERTO -> EN_PROCESO", lambda: mesa.cambiar_estado_ticket(t1.id_ticket, EstadoTicket.EN_PROCESO))
    _intentar("EN_PROCESO -> CERRADO", lambda: mesa.cambiar_estado_ticket(t1.id_ticket, EstadoTicket.CERRADO))
    _intentar("CERRADO -> ABIERTO (no permitido)", lambda: mesa.cambiar_estado_ticket(t1.id_ticket, EstadoTicket.ABIERTO))

    print("\n=== Consultas ===")
    for e in mesa.listar_estudiantes():
        print(f"{e} | promedio: {e.promedio}")
    for t in mesa.listar_tickets():
        print(t)

    # Polimorfismo: distintos usuarios responden al mismo método
    print("\n=== Polimorfismo ===")
    usuarios: List[UsuarioCUN] = [
        Docente("D-201", "Dr. Carlos Ruiz", "Ingeniería de Software", "carlos_ruiz@cun.edu.co"),
        *mesa.listar_estudiantes(),
    ]
    for u in usuarios:
        print(u)

    if conexion:
        conexion.cerrar()


if __name__ == "__main__":
    main()
