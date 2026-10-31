# Sistema Mesa de Ayuda TI y Gestión Académica - CUN

Proyecto del taller integrador de **Programación Orientada a Objetos** (Ingeniería de Sistemas, Corporación Unificada Nacional de Educación Superior - CUN).

Automatiza la atención de solicitudes técnicas de la Mesa de Ayuda de TI: gestiona **estudiantes**, **docentes** y **tickets de soporte**, con persistencia en **SQLite** mediante el módulo estándar `sqlite3`.

**Autor:** _Tu Nombre Completo_ · **Programa:** Ingeniería de Sistemas · **Año:** 2026

---

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `main.py` | Clases POO, repositorios (memoria y SQLite), servicio y demostración. |
| `crear_base_datos.py` | Script que crea `cun_sistema.db` (tablas + datos de ejemplo). |
| `cun_sistema.db` | Base de datos SQLite generada con el script anterior. |
| `README.md` | Este documento. |

## Requisitos

- Python 3.8 o superior.
- No requiere instalar librerías externas (solo la biblioteca estándar).

## Cómo ejecutarlo

```bash
# 1. Crear la base de datos (tablas + datos de ejemplo)
python crear_base_datos.py

#    Opcional: solo las tablas, sin datos
python crear_base_datos.py --vacia

# 2. Ejecutar el programa (por defecto trabaja en memoria)
python main.py
```

Para que `main.py` use la base de datos, cambia en la función `main()`:

```python
USAR_SQLITE = True   # antes: False
```

## Modelo de la base de datos

```sql
CREATE TABLE estudiantes (
    id_estudiante TEXT PRIMARY KEY,
    nombre        TEXT NOT NULL,
    programa      TEXT NOT NULL,
    promedio      REAL DEFAULT 0.0
);

CREATE TABLE tickets_soporte (
    id_ticket     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_estudiante TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    descripcion   TEXT NOT NULL,
    estado        TEXT DEFAULT 'ABIERTO',
    FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
);
```

## Arquitectura

```
Modelos (POO)  ->  Servicio MesaAyudaTI  ->  Repositorio (interfaz)
                                               |- Memoria
                                               |- SQLite (cun_sistema.db)
```

El servicio solo conoce la **interfaz** del repositorio (inyección de dependencias), por lo que cambiar de memoria a SQLite, o a otro motor en el futuro, no requiere modificar las clases del dominio.

## Pilares de la POO aplicados

| Pilar | Dónde se aplica |
|---|---|
| **Encapsulamiento** | `Estudiante.__promedio` es privado y se modifica solo mediante una propiedad con validación (0.0 a 5.0). Los demás atributos se exponen como propiedades de solo lectura. |
| **Herencia** | `Estudiante` y `Docente` heredan de `UsuarioCUN` usando `super().__init__()`. |
| **Polimorfismo** | Cada subclase implementa `obtener_rol()` con su propia lógica. |
| **Abstracción** | `UsuarioCUN` y los repositorios son clases abstractas (`ABC`, `@abstractmethod`) que definen contratos. |
| **Composición** | `MesaAyudaTI` se compone de un repositorio de estudiantes y uno de tickets. |

## Reglas de negocio

- El promedio de un estudiante debe estar entre 0.0 y 5.0.
- Un ticket solo se crea para un estudiante existente.
- Categorías válidas: `HARDWARE`, `SOFTWARE`, `REDES`, `CUENTAS`, `AULAS`, `OTRO`.
- Flujo de estados: `ABIERTO` → `EN_PROCESO` → `CERRADO` (un ticket cerrado no se puede reabrir).
- Manejo de errores con excepciones propias: `ErrorValidacion`, `ErrorNoEncontrado`, `ErrorDuplicado`.

## Referencias

- Documentación oficial de Python: clases y POO.
- Documentación del módulo `sqlite3` de la biblioteca estándar.
- Guía Integral de POO - CUN.
