# -*- coding: utf-8 -*-
"""SistemaRural-PE - Centro de Salud Rural «Santa Rosa» (Chugur, Cajamarca).
Registra pacientes, personal, citas y atenciones y genera reportes de gestión.
Funciona sin conexión: los datos se guardan en archivos CSV."""
import csv
import hashlib
import os
import secrets
from abc import ABC, abstractmethod
from datetime import date, datetime
from functools import reduce

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # permite probar la lógica aunque no haya interfaz gráfica
    tk = filedialog = messagebox = ttk = None

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
CARGOS = ("Médico", "Obstetra", "Enfermería", "Odontólogo", "Técnico de enfermería")
SERVICIOS = ("Medicina general", "Obstetricia", "Enfermería", "Odontología",
             "Crecimiento y desarrollo")
REPORTES = ("Resumen de gestión", "Atenciones por servicio", "Citas por estado")
FONDO, PRIMARIO, ACENTO, ALERTA = "#EAF4F8", "#0B6E99", "#17A589", "#C0392B"


class SaludError(Exception):
    """Error controlado: dato inválido, regla incumplida o problema con los archivos."""


# ---------------------------------------------------------------- utilidades
def leer_fecha(texto, formato="%d/%m/%Y"):
    try:
        return datetime.strptime(texto.strip(), formato)
    except ValueError:
        raise SaludError("Fecha u hora con formato incorrecto (ejemplo: 25/11/2026 08:30).")


def obligatorio(valor, campo):
    valor = (valor or "").strip()
    if not valor:
        raise SaludError("El campo «" + campo + "» es obligatorio.")
    return valor


def hash_dni(dni, sal):
    """El DNI nunca se guarda en texto plano (Ley N.° 29733): solo su hash con sal."""
    if not (dni.isdigit() and len(dni) == 8):
        raise SaludError("El DNI debe tener 8 dígitos numéricos.")
    return hashlib.sha256((sal + dni).encode("utf-8")).hexdigest()


def a_fila(objeto):
    return {campo: str(getattr(objeto, "_" + campo)) for campo in objeto.CAMPOS}


def desde_fila(clase, fila):
    return clase(*[fila[campo] for campo in clase.CAMPOS])


def leer_csv(ruta):
    try:
        if not os.path.exists(ruta):
            return []
        with open(ruta, newline="", encoding="utf-8") as archivo:
            return list(csv.DictReader(archivo))
    except (OSError, csv.Error) as error:
        raise SaludError("No se pudo leer " + os.path.basename(ruta) + ": " + str(error))


def guardar_csv(ruta, clase, objetos):
    try:
        with open(ruta + ".tmp", "w", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=clase.CAMPOS)
            escritor.writeheader()
            escritor.writerows([a_fila(o) for o in objetos])
        os.replace(ruta + ".tmp", ruta)  # reemplazo atómico: evita archivos a medias
    except OSError as error:
        raise SaludError("No se pudo guardar " + os.path.basename(ruta) + ": " + str(error))


def obtener_sal(ruta):
    try:
        if not os.path.exists(ruta):
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as archivo:
                archivo.write(secrets.token_hex(16))
        with open(ruta, encoding="utf-8") as archivo:
            return archivo.read().strip()
    except OSError as error:
        raise SaludError("No se pudo acceder a la carpeta de datos: " + str(error))


# ------------------------------------------------ clases (orientado a objetos)
class Persona(ABC):
    CAMPOS = ("codigo", "dni_hash", "dni_mascara", "nombres", "apellidos")

    def __init__(self, codigo, dni_hash, dni_mascara, nombres, apellidos):
        self._codigo, self._dni_hash, self._dni_mascara = codigo, dni_hash, dni_mascara
        self.nombres = nombres                      # usa el setter con validación
        self._apellidos = obligatorio(apellidos, "Apellidos")

    codigo = property(lambda self: self._codigo)
    dni_hash = property(lambda self: self._dni_hash)
    dni_mascara = property(lambda self: self._dni_mascara)
    nombre_completo = property(lambda self: self._nombres + " " + self._apellidos)

    @property
    def nombres(self):
        return self._nombres

    @nombres.setter
    def nombres(self, valor):
        self._nombres = obligatorio(valor, "Nombres")

    @abstractmethod
    def detalle(self):
        """Dato que distingue a cada tipo de persona."""


class Paciente(Persona):
    CAMPOS = Persona.CAMPOS + ("fecha_nacimiento",)

    def __init__(self, codigo, dni_hash, dni_mascara, nombres, apellidos, fecha_nacimiento):
        super().__init__(codigo, dni_hash, dni_mascara, nombres, apellidos)
        self._fecha_nacimiento = date.fromisoformat(str(fecha_nacimiento))
        if self._fecha_nacimiento > date.today():
            raise SaludError("La fecha de nacimiento no puede ser futura.")

    def detalle(self):
        hoy, nac = date.today(), self._fecha_nacimiento
        return str(hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))) + " años"


class PersonalSalud(Persona):
    CAMPOS = Persona.CAMPOS + ("cargo", "colegiatura")

    def __init__(self, codigo, dni_hash, dni_mascara, nombres, apellidos, cargo, colegiatura):
        super().__init__(codigo, dni_hash, dni_mascara, nombres, apellidos)
        self.cargo = cargo
        self._colegiatura = obligatorio(colegiatura, "Colegiatura")

    @property
    def cargo(self):
        return self._cargo

    @cargo.setter
    def cargo(self, valor):
        if valor not in CARGOS:
            raise SaludError("Seleccione un cargo válido.")
        self._cargo = valor

    def detalle(self):
        return self._cargo


class Cita:
    CAMPOS = ("codigo", "codigo_paciente", "codigo_personal", "fecha_hora", "servicio",
              "estado", "motivo", "tratamiento")
    PERMITIDO = {"PROGRAMADA": ("CONFIRMADA", "CANCELADA"), "CONFIRMADA": ("ATENDIDA", "CANCELADA")}

    def __init__(self, codigo, codigo_paciente, codigo_personal, fecha_hora, servicio,
                 estado="PROGRAMADA", motivo="", tratamiento=""):
        if servicio not in SERVICIOS:
            raise SaludError("Seleccione un servicio válido.")
        self._codigo, self._codigo_paciente, self._codigo_personal = codigo, codigo_paciente, codigo_personal
        self._fecha_hora = datetime.fromisoformat(str(fecha_hora))
        self._servicio, self._estado, self._motivo, self._tratamiento = servicio, estado, motivo, tratamiento

    codigo = property(lambda self: self._codigo)
    codigo_paciente = property(lambda self: self._codigo_paciente)
    codigo_personal = property(lambda self: self._codigo_personal)
    fecha_hora = property(lambda self: self._fecha_hora)
    servicio = property(lambda self: self._servicio)
    estado = property(lambda self: self._estado)
    motivo = property(lambda self: self._motivo)

    def cambiar_estado(self, nuevo, motivo="", tratamiento=""):
        """Aplica una transición permitida; al atender exige motivo y tratamiento."""
        if nuevo not in self.PERMITIDO.get(self._estado, ()):
            raise SaludError("No se puede pasar de " + self._estado + " a " + nuevo + ".")
        if nuevo == "ATENDIDA":
            motivo, tratamiento = obligatorio(motivo, "Motivo de consulta"), obligatorio(tratamiento, "Tratamiento")
            self._motivo, self._tratamiento = motivo, tratamiento
        self._estado = nuevo


ARCHIVOS = {Paciente: "pacientes.csv", PersonalSalud: "personal.csv", Cita: "citas.csv"}
PREFIJOS = {Paciente: "HC", PersonalSalud: "PS", Cita: "C"}


class RegistroCentral:
    """Patrón Singleton: una sola fuente de datos para todo el programa."""
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._carpeta = None
            cls._instancia._datos = {clase: {} for clase in ARCHIVOS}
        return cls._instancia

    def configurar(self, carpeta):
        """Define la carpeta de datos y carga lo que ya existe."""
        self._carpeta = carpeta
        self.__sal = obtener_sal(os.path.join(carpeta, "sal.key"))   # atributo privado
        try:
            self._datos = {
                clase: {o.codigo: o for o in map(lambda f: desde_fila(clase, f),
                                                 leer_csv(os.path.join(carpeta, archivo)))}
                for clase, archivo in ARCHIVOS.items()}
        except (KeyError, ValueError, TypeError):
            raise SaludError("Los archivos de datos están dañados.")

    def _agregar(self, objeto):
        self._datos[type(objeto)][objeto.codigo] = objeto
        guardar_csv(os.path.join(self._carpeta, ARCHIVOS[type(objeto)]), type(objeto),
                    self._datos[type(objeto)].values())
        return objeto

    def _codigo_nuevo(self, clase):
        return PREFIJOS[clase] + "-" + str(len(self._datos[clase]) + 1).zfill(4)

    def registrar(self, clase, dni, **datos):
        """Crea un paciente o un profesional protegiendo su DNI."""
        dni_hash = hash_dni(dni, self.__sal)
        if any(p.dni_hash == dni_hash for p in self._datos[clase].values()):
            raise SaludError("Ya existe una persona registrada con ese DNI.")
        return self._agregar(clase(self._codigo_nuevo(clase), dni_hash, "*****" + dni[-3:], **datos))

    def programar_cita(self, dni, codigo_personal, fecha_hora, servicio):
        paciente = next((p for p in self.pacientes if p.dni_hash == hash_dni(dni, self.__sal)), None)
        if paciente is None:
            raise SaludError("No existe un paciente con ese DNI.")
        if codigo_personal not in self._datos[PersonalSalud]:
            raise SaludError("El profesional no existe.")
        if fecha_hora.date() < date.today():
            raise SaludError("No se puede programar una cita en una fecha pasada.")
        if any(c.codigo_personal == codigo_personal and c.fecha_hora == fecha_hora
               and c.estado != "CANCELADA" for c in self.citas):
            raise SaludError("El profesional ya tiene una cita en ese horario.")
        return self._agregar(Cita(self._codigo_nuevo(Cita), paciente.codigo, codigo_personal,
                                  fecha_hora, servicio))

    def actualizar_cita(self, codigo, nuevo_estado, motivo="", tratamiento=""):
        if codigo not in self._datos[Cita]:
            raise SaludError("La cita no existe.")
        self._datos[Cita][codigo].cambiar_estado(nuevo_estado, motivo, tratamiento)
        self._agregar(self._datos[Cita][codigo])

    pacientes = property(lambda self: list(self._datos[Paciente].values()))
    personal = property(lambda self: list(self._datos[PersonalSalud].values()))
    citas = property(lambda self: list(self._datos[Cita].values()))

    def nombre(self, codigo):
        for coleccion in (self._datos[Paciente], self._datos[PersonalSalud]):
            if codigo in coleccion:
                return coleccion[codigo].nombre_completo
        return "(desconocido)"


registro = RegistroCentral()


# ------------------------------------------------- reportes (paradigma funcional)
def contar_por(elementos, clave):
    return reduce(lambda acc, e: dict(acc, **{clave(e): acc.get(clave(e), 0) + 1}), elementos, {})


def generar_reporte(tipo, citas, desde, hasta):
    """Devuelve (texto, datos). Solo contiene totales: no identifica a los pacientes."""
    if tipo not in REPORTES:
        raise SaludError("Seleccione un tipo de reporte válido.")
    if desde > hasta:
        raise SaludError("La fecha inicial no puede ser posterior a la final.")
    periodo = list(filter(lambda c: desde <= c.fecha_hora.date() <= hasta, citas))
    atendidas = list(filter(lambda c: c.estado == "ATENDIDA", periodo))
    if tipo == "Atenciones por servicio":
        datos = contar_por(atendidas, lambda c: c.servicio)
    elif tipo == "Citas por estado":
        datos = contar_por(periodo, lambda c: c.estado)
    else:
        datos = {"Citas en el periodo": len(periodo), "Atenciones realizadas": len(atendidas),
                 "Pacientes distintos atendidos": len(set(map(lambda c: c.codigo_paciente, atendidas))),
                 "Tasa de atención de citas (%)": round(len(atendidas) * 100 / len(periodo), 1) if periodo else 0.0}
    lineas = ["REPORTE DE GESTIÓN SANITARIA - C.S. RURAL SANTA ROSA, CHUGUR", "Tipo de reporte : " + tipo,
              "Periodo         : " + desde.strftime("%d/%m/%Y") + " al " + hasta.strftime("%d/%m/%Y"), "-" * 52]
    lineas += [k.ljust(42) + str(v).rjust(10) for k, v in datos.items()] or ["Sin registros en el periodo."]
    return "\n".join(lineas), datos


# ------------------------------------------------ interfaz (orientado a eventos)
def boton(padre, texto, comando, color=PRIMARIO, ancho=14):
    return tk.Button(padre, text=texto, command=comando, width=ancho, bg=color, fg="white",
                     font=("Arial", 10, "bold"), relief="flat", cursor="hand2")


def formulario(padre, titulo, campos, accion, boton_principal="Guardar", columnas=None,
               filas=None, extras=(), iniciales=(), limpiar=True):
    """Ventana genérica. campos: [(etiqueta, None | opciones | función que da opciones)].
    Con 'columnas' muestra una tabla; sin ellas, un cuadro de texto (reportes)."""
    ventana = tk.Toplevel(padre)
    ventana.title(titulo + " - SistemaRural-PE")
    ventana.geometry("760x560")
    ventana.config(bg=FONDO)
    tk.Label(ventana, text=titulo.upper(), font=("Arial", 15, "bold"), bg=PRIMARIO, fg="white",
             pady=10).pack(fill="x")
    marco = tk.Frame(ventana, bg=FONDO)
    marco.pack(fill="x", padx=15, pady=8)
    marco.columnconfigure(1, weight=1)
    widgets = []
    for i, (etiqueta, opciones) in enumerate(campos):
        tk.Label(marco, text=etiqueta, bg=FONDO, anchor="w").grid(row=i, column=0, sticky="w", pady=4)
        w = tk.Entry(marco, width=48) if opciones is None else ttk.Combobox(marco, state="readonly", width=45)
        w.grid(row=i, column=1, sticky="ew", pady=4, padx=(10, 0))
        widgets.append(w)
    barra = tk.Frame(ventana, bg=FONDO)
    barra.pack(fill="x", padx=15)
    if columnas:
        salida = ttk.Treeview(ventana, columns=tuple(columnas), show="headings", height=8)
        for nombre, ancho in columnas.items():
            salida.heading(nombre, text=nombre)
            salida.column(nombre, width=ancho)
    else:
        salida = tk.Text(ventana, height=16, font=("Consolas", 10))
    salida.pack(fill="both", expand=True, padx=15, pady=10)

    def poner(widget, texto):
        widget.set(texto) if isinstance(widget, ttk.Combobox) else widget.insert(0, texto)

    def refrescar():
        for w, (_, opciones) in zip(widgets, campos):
            if opciones is not None:
                w["values"] = opciones() if callable(opciones) else opciones
        if columnas:
            salida.delete(*salida.get_children())
            for fila in filas():
                salida.insert("", "end", values=fila)

    def intentar(funcion, argumento):
        try:
            return True, funcion(argumento)
        except SaludError as error:
            messagebox.showerror("No se pudo completar", str(error), parent=ventana)
            return False, None

    def principal():
        ok, resultado = intentar(accion, [w.get().strip() for w in widgets])
        if not ok:
            return
        if columnas:
            messagebox.showinfo("Listo", resultado or "Operación realizada correctamente.", parent=ventana)
        else:
            salida.delete("1.0", tk.END)
            salida.insert("1.0", resultado)
        if limpiar:
            for w in widgets:
                w.set("") if isinstance(w, ttk.Combobox) else w.delete(0, tk.END)
        refrescar()

    def extra(funcion):
        if columnas:   # argumento: código de la fila seleccionada
            seleccion = salida.selection()
            argumento = salida.item(seleccion[0], "values")[0] if seleccion else ""
        else:          # argumento: texto del reporte mostrado
            argumento = salida.get("1.0", tk.END).strip()
        ok, mensaje = intentar(funcion, argumento)
        if ok and mensaje:
            messagebox.showinfo("Listo", mensaje, parent=ventana)
        refrescar()

    boton(barra, boton_principal, principal, ACENTO, 16).pack(side="left", padx=4)
    for texto, funcion in extras:
        boton(barra, texto, lambda f=funcion: extra(f)).pack(side="left", padx=4)
    boton(barra, "Cerrar", ventana.destroy, ALERTA, 10).pack(side="left", padx=4)
    ventana.bind("<Return>", lambda evento: principal())      # evento de teclado
    for w, texto in zip(widgets, iniciales):
        poner(w, texto)
    refrescar()


def cambiar_cita(codigo, estado):
    if not codigo:
        raise SaludError("Seleccione una cita de la tabla.")
    registro.actualizar_cita(codigo, estado)
    return "Cita actualizada."


def exportar_reporte(texto):
    if not texto:
        raise SaludError("Primero genere un reporte.")
    ruta = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Texto", "*.txt")])
    if ruta:
        try:
            with open(ruta, "w", encoding="utf-8") as archivo:
                archivo.write(texto)
        except OSError as error:
            raise SaludError("No se pudo exportar el reporte: " + str(error))
        return "Reporte exportado correctamente."


def abrir_pacientes(padre):
    formulario(padre, "Registro de pacientes",
               [("DNI (8 dígitos)", None), ("Nombres", None), ("Apellidos", None),
                ("Fecha de nacimiento (DD/MM/AAAA)", None)],
               lambda v: "Historia clínica asignada: " + registro.registrar(
                   Paciente, v[0], nombres=v[1], apellidos=v[2],
                   fecha_nacimiento=leer_fecha(v[3]).date()).codigo,
               columnas={"Historia": 90, "DNI": 100, "Paciente": 330, "Edad": 90},
               filas=lambda: [(p.codigo, p.dni_mascara, p.nombre_completo, p.detalle())
                              for p in registro.pacientes])


def abrir_personal(padre):
    formulario(padre, "Registro de personal de salud",
               [("DNI (8 dígitos)", None), ("Nombres", None), ("Apellidos", None),
                ("Cargo", CARGOS), ("N.° de colegiatura", None)],
               lambda v: "Código asignado: " + registro.registrar(
                   PersonalSalud, v[0], nombres=v[1], apellidos=v[2], cargo=v[3],
                   colegiatura=v[4]).codigo,
               columnas={"Código": 80, "DNI": 100, "Nombre": 300, "Cargo": 160},
               filas=lambda: [(p.codigo, p.dni_mascara, p.nombre_completo, p.detalle())
                              for p in registro.personal])


def abrir_citas(padre):
    formulario(padre, "Programación de citas",
               [("DNI del paciente", None),
                ("Profesional", lambda: [p.codigo + " | " + p.nombre_completo for p in registro.personal]),
                ("Servicio", SERVICIOS), ("Fecha y hora (DD/MM/AAAA HH:MM)", None)],
               lambda v: "Código de cita: " + registro.programar_cita(
                   v[0], v[1].split("|")[0].strip(), leer_fecha(v[3], "%d/%m/%Y %H:%M"), v[2]).codigo,
               boton_principal="Programar cita",
               columnas={"Código": 60, "Paciente": 200, "Fecha y hora": 120, "Servicio": 130,
                         "Profesional": 150, "Estado": 90},
               filas=lambda: [(c.codigo, registro.nombre(c.codigo_paciente),
                               c.fecha_hora.strftime("%d/%m/%Y %H:%M"), c.servicio,
                               registro.nombre(c.codigo_personal), c.estado) for c in registro.citas],
               extras=(("Confirmar", lambda cod: cambiar_cita(cod, "CONFIRMADA")),
                       ("Cancelar cita", lambda cod: cambiar_cita(cod, "CANCELADA"))))


def abrir_atenciones(padre):
    formulario(padre, "Registro de atenciones",
               [("Cita confirmada", lambda: [
                   c.codigo + " | " + c.fecha_hora.strftime("%d/%m/%Y %H:%M") + " | "
                   + registro.nombre(c.codigo_paciente) for c in registro.citas if c.estado == "CONFIRMADA"]),
                ("Motivo de consulta", None), ("Tratamiento indicado", None)],
               lambda v: registro.actualizar_cita(v[0].split("|")[0].strip(), "ATENDIDA", v[1], v[2])
               or "Atención registrada correctamente.",
               boton_principal="Registrar atención",
               columnas={"Código": 60, "Fecha y hora": 120, "Paciente": 220, "Servicio": 140, "Motivo": 190},
               filas=lambda: [(c.codigo, c.fecha_hora.strftime("%d/%m/%Y %H:%M"),
                               registro.nombre(c.codigo_paciente), c.servicio, c.motivo)
                              for c in registro.citas if c.estado == "ATENDIDA"])


def abrir_reportes(padre):
    hoy = date.today()
    formulario(padre, "Reportes de gestión sanitaria",
               [("Tipo de reporte", REPORTES), ("Desde (DD/MM/AAAA)", None), ("Hasta (DD/MM/AAAA)", None)],
               lambda v: generar_reporte(v[0], registro.citas, leer_fecha(v[1]).date(),
                                         leer_fecha(v[2]).date())[0],
               boton_principal="Generar reporte", extras=(("Exportar TXT", exportar_reporte),),
               iniciales=(REPORTES[0], hoy.replace(day=1).strftime("%d/%m/%Y"), hoy.strftime("%d/%m/%Y")),
               limpiar=False)


def iniciar_aplicacion():
    if tk is None:
        print("No se encontró tkinter. En Linux instale: sudo apt install python3-tk")
        return
    ventana = tk.Tk()
    ventana.title("SistemaRural-PE")
    ventana.geometry("440x560")
    ventana.resizable(False, False)
    ventana.config(bg=FONDO)
    try:
        registro.configurar(CARPETA)
    except SaludError as error:
        messagebox.showerror("Error al iniciar", str(error))
        ventana.destroy()
        return
    estilo = ttk.Style(ventana)
    estilo.theme_use("clam")
    estilo.configure("Treeview.Heading", font=("Arial", 10, "bold"), background=PRIMARIO, foreground="white")
    tk.Label(ventana, text="SistemaRural-PE", font=("Arial", 22, "bold"), bg=PRIMARIO, fg="white",
             pady=14).pack(fill="x")
    tk.Label(ventana, text="Centro de Salud Rural «Santa Rosa»\nChugur, Cajamarca",
             font=("Arial", 11), bg=FONDO, pady=14).pack()
    for texto, funcion in (("Registro de pacientes", abrir_pacientes), ("Personal de salud", abrir_personal),
                           ("Programación de citas", abrir_citas), ("Registro de atenciones", abrir_atenciones),
                           ("Reportes de gestión", abrir_reportes)):
        boton(ventana, texto, lambda f=funcion: f(ventana), PRIMARIO, 30).pack(pady=8, ipady=6)
    boton(ventana, "Salir", lambda: messagebox.askyesno("Salir", "¿Desea salir?") and ventana.destroy(),
          ALERTA, 30).pack(pady=14, ipady=6)
    ventana.mainloop()


if __name__ == "__main__":
    iniciar_aplicacion()
