"""Pruebas automatizadas de SistemaRural-PE (ejecutar con: pytest -v)."""
from datetime import date, datetime, timedelta

import pytest

import sistema_rural as sr
from sistema_rural import Cita, PersonalSalud, Paciente, SaludError


def manana(hora=9):
    return (datetime.now() + timedelta(days=1)).replace(hour=hora, minute=0, second=0, microsecond=0)


@pytest.fixture
def registro(tmp_path):
    r = sr.RegistroCentral()
    r.configurar(str(tmp_path))
    r.registrar(Paciente, "12345678", nombres="Juan", apellidos="Prueba", fecha_nacimiento=date(1990, 5, 20))
    r.registrar(PersonalSalud, "87654321", nombres="Ana", apellidos="Prueba", cargo="Médico",
                colegiatura="CMP-00001")
    return r


def atender(registro, hora):
    cita = registro.programar_cita("12345678", "PS-0001", manana(hora), "Medicina general")
    registro.actualizar_cita(cita.codigo, "CONFIRMADA")
    registro.actualizar_cita(cita.codigo, "ATENDIDA", "Control", "Reposo")
    return cita


def test_dni_invalido_lanza_error(registro):
    with pytest.raises(SaludError):
        registro.registrar(Paciente, "123", nombres="Luis", apellidos="P", fecha_nacimiento=date(2000, 1, 1))


def test_dni_no_se_guarda_en_texto_plano(registro, tmp_path):
    contenido = (tmp_path / "pacientes.csv").read_text(encoding="utf-8")
    assert "12345678" not in contenido and "*****678" in contenido


def test_no_permite_paciente_duplicado(registro):
    with pytest.raises(SaludError):
        registro.registrar(Paciente, "12345678", nombres="Otro", apellidos="P", fecha_nacimiento=date(1980, 1, 1))


def test_ciclo_completo_de_una_cita(registro):
    assert atender(registro, 9).estado == "ATENDIDA"


def test_no_se_atiende_una_cita_sin_confirmar(registro):
    cita = registro.programar_cita("12345678", "PS-0001", manana(), "Medicina general")
    with pytest.raises(SaludError):
        registro.actualizar_cita(cita.codigo, "ATENDIDA", "Control", "Reposo")


def test_no_se_programa_cita_en_fecha_pasada(registro):
    with pytest.raises(SaludError):
        registro.programar_cita("12345678", "PS-0001", datetime.now() - timedelta(days=2), "Medicina general")


def test_no_se_programa_dos_citas_en_el_mismo_horario(registro):
    registro.programar_cita("12345678", "PS-0001", manana(), "Medicina general")
    with pytest.raises(SaludError):
        registro.programar_cita("12345678", "PS-0001", manana(), "Medicina general")


def test_los_datos_persisten_en_archivos(registro, tmp_path):
    atender(registro, 9)
    registro.configurar(str(tmp_path))          # simula reiniciar la aplicación
    assert len(registro.pacientes) == 1 and registro.citas[0].estado == "ATENDIDA"


def test_reporte_atenciones_por_servicio(registro):
    atender(registro, 9)
    atender(registro, 10)
    _, datos = sr.generar_reporte("Atenciones por servicio", registro.citas, date.today(),
                                  date.today() + timedelta(days=1))
    assert datos == {"Medicina general": 2}


def test_tasa_de_atencion_del_resumen(registro):
    atender(registro, 9)
    registro.programar_cita("12345678", "PS-0001", manana(10), "Medicina general")
    _, datos = sr.generar_reporte("Resumen de gestión", registro.citas, date.today(),
                                  date.today() + timedelta(days=1))
    assert datos["Tasa de atención de citas (%)"] == 50.0


def test_rango_de_fechas_invalido():
    with pytest.raises(SaludError):
        sr.generar_reporte("Citas por estado", [], date(2026, 12, 1), date(2026, 11, 1))


def test_fecha_con_formato_incorrecto():
    with pytest.raises(SaludError):
        sr.leer_fecha("2026-11-10")


def test_singleton_devuelve_misma_instancia():
    assert sr.RegistroCentral() is sr.RegistroCentral()
