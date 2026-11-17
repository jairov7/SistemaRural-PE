# SistemaRural-PE

Módulo de escritorio (Python 3.8 o superior + tkinter) para el Centro de Salud Rural
«Santa Rosa» (Chugur, Cajamarca): registra pacientes, personal de salud, citas y atenciones,
y genera reportes de gestión sanitaria. Funciona sin conexión y guarda los datos en archivos CSV.

## Cómo ejecutar
1. Abrir la carpeta del proyecto en VS Code.
2. Abrir `sistema_rural.py` y ejecutarlo (botón Run) o, en la terminal: `python sistema_rural.py`.

## Pruebas
    pip install pytest
    pytest -v

## Datos personales (Ley N.° 29733)
El DNI se guarda como hash con sal y como máscara (*****123). La carpeta `datos/` se crea sola
y no se sube al repositorio. Todos los datos de prueba son ficticios.
