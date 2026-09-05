import os
import sys
import logging
import threading
import uvicorn
import webview
from pathlib import Path
from datetime import datetime, timedelta
from io import BytesIO
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
from peewee import (
    SqliteDatabase, Model, CharField, FloatField, IntegerField, 
    ForeignKeyField, TextField, BooleanField
)

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# CONFIGURACIÓN DE LOGS
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app_camp.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("CampApp")

db = SqliteDatabase('camp_menu.db', pragmas={'journal_mode': 'wal', 'foreign_keys': 1})

class BaseModelDB(Model):
    class Meta:
        database = db

class Ingrediente(BaseModelDB):
    nombre = CharField(unique=True)
    unidad_medida = CharField()
    coste_unidad = FloatField(default=0.0)
    alergenos = TextField(default="[]")

class Receta(BaseModelDB):
    nombre = CharField()
    porciones_base = IntegerField(default=10)
    instrucciones = TextField(default="")
    es_item_picnic = BooleanField(default=False)
    alergenos = TextField(default="[]")

class RecetaIngrediente(BaseModelDB):
    receta = ForeignKeyField(Receta, backref='ingredientes_rel', on_delete='CASCADE')
    ingrediente = ForeignKeyField(Ingrediente, backref='recetas_rel', on_delete='CASCADE')
    cantidad_base = FloatField()

class Campamento(BaseModelDB):
    nombre = CharField()
    fecha_inicio = CharField()
    fecha_fin = CharField()

class Rama(BaseModelDB):
    nombre = CharField(unique=True)

class CensoDiarioRama(BaseModelDB):
    campamento = ForeignKeyField(Campamento, backref='censos', on_delete='CASCADE')
    fecha = CharField()
    rama = ForeignKeyField(Rama, backref='censos', on_delete='CASCADE')
    num_participantes = IntegerField(default=0)
    num_responsables = IntegerField(default=0)
    esta_de_salida = BooleanField(default=False)
    tomas_ausentes = CharField(default="")
    alergenos_detalle = TextField(default="{}")

class MenuComida(BaseModelDB):
    campamento = ForeignKeyField(Campamento, backref='comidas', on_delete='CASCADE')
    fecha = CharField()
    toma = CharField()
    rama_especifica = ForeignKeyField(Rama, null=True, backref='comidas_especificas', on_delete='SET NULL')
    es_picnic = BooleanField(default=False)

class MenuComidaPlato(BaseModelDB):
    menu_comida = ForeignKeyField(MenuComida, backref='platos', on_delete='CASCADE')
    receta = ForeignKeyField(Receta, backref='en_menus', on_delete='CASCADE')
    es_alternativa = BooleanField(default=False)
    para_alergeno = CharField(null=True, default=None)

def init_db():
    if db.is_closed():
        db.connect()
    db.create_tables([Ingrediente, Receta, RecetaIngrediente, Campamento, Rama, CensoDiarioRama, MenuComida, MenuComidaPlato], safe=True)
    
    try:
        db.execute_sql("ALTER TABLE censodiariorama ADD COLUMN tomas_ausentes VARCHAR DEFAULT '';")
    except Exception:
        pass

    try:
        db.execute_sql("ALTER TABLE receta RENAME COLUMN pasos TO instrucciones;")
    except Exception:
        pass

    # Migraciones para alérgenos (compatibles con bases de datos existentes).
    for tabla, columna, definicion in [
        ("ingrediente", "alergenos", "TEXT DEFAULT '[]'"),
        ("receta", "alergenos", "TEXT DEFAULT '[]'"),
        ("censodiariorama", "alergenos_detalle", "TEXT DEFAULT '{}'"),
        ("menucomidaplato", "es_alternativa", "INTEGER DEFAULT 0"),
        ("menucomidaplato", "para_alergeno", "VARCHAR DEFAULT NULL"),
    ]:
        try:
            db.execute_sql(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion};")
        except Exception:
            pass
        
    Rama.delete().where(Rama.nombre == "Responsables").execute()
    ramas_correctas = ["Castores", "Lobatos", "Rangers", "Pioneros", "Rutas", "Apoyo", "Cocineros"]
    for r in ramas_correctas:
        Rama.get_or_create(nombre=r)
    if not db.is_closed():
        db.close()
    logger.info("Base de datos inicializada correctamente.")

app = FastAPI()

@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    if db.is_closed():
        db.connect()
    try:
        response = await call_next(request)
    finally:
        if not db.is_closed():
            db.close()
    return response

init_db()

# DTOs / Esquemas Pydantic
class IngredienteCreate(BaseModel):
    nombre: str
    unidad_medida: str
    coste_unidad: float = 0.0
    alergenos: List[str] = []

class RecetaItem(BaseModel):
    ingrediente_id: int
    cantidad_base: float

class RecetaCreate(BaseModel):
    nombre: str
    porciones_base: int = 10
    instrucciones: str = ""
    alergenos: List[str] = []
    ingredientes: List[RecetaItem]

class CampamentoCreate(BaseModel):
    nombre: str
    fecha_inicio: str
    fecha_fin: str

class CensoItem(BaseModel):
    rama_id: int
    num_participantes: Optional[int] = 0
    num_responsables: Optional[int] = 0
    esta_de_salida: Optional[bool] = False
    tomas_ausentes: Optional[List[str]] = []
    alergenos_detalle: Optional[dict] = {}

class AsignarComida(BaseModel):
    toma: str
    receta_id: int
    rama_id: Optional[int] = None
    es_picnic: bool = False
    es_alternativa: bool = False
    para_alergeno: Optional[str] = None

def generar_fechas_campamento(f_inicio_str, f_fin_str):
    f_inicio = datetime.strptime(str(f_inicio_str), "%Y-%m-%d").date()
    f_fin = datetime.strptime(str(f_fin_str), "%Y-%m-%d").date()
    fechas = []
    curr = f_inicio
    while curr <= f_fin:
        fechas.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)
    return fechas

import json

def obtener_tomas_ausentes(censo):
    """Devuelve las tomas en las que la rama está ausente."""
    if not censo.esta_de_salida or not censo.tomas_ausentes:
        return []
    
    raw = censo.tomas_ausentes
    
    # Si ya viene como lista
    if isinstance(raw, list):
        return raw
    
    # Si viene como string
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [t.strip() for t in raw.split(",") if t.strip()]
        
    return []


def calcular_comensales_comida(comida, censos_del_dia):
    if comida.rama_especifica_id:
        c_rama = next((c for c in censos_del_dia if c.rama_id == comida.rama_especifica_id), None)
        if c_rama:
            t_ausentes = obtener_tomas_ausentes(c_rama)
            # Solo está fuera si la toma actual está explícitamente en sus tomas ausentes
            esta_fuera = comida.toma in t_ausentes
            
            # Si la comida está asignada a una rama concreta y es picnic, se prepara para esa rama
            if comida.es_picnic:
                return (c_rama.num_participantes or 0) + (c_rama.num_responsables or 0)
            else:
                # Si es comida regular en campamento, solo la comen si no están fuera
                if not esta_fuera:
                    return (c_rama.num_participantes or 0) + (c_rama.num_responsables or 0)
        return 0

    total_comensales = 0
    for c in censos_del_dia:
        t_ausentes = obtener_tomas_ausentes(c)
        esta_fuera = comida.toma in t_ausentes
        
        if comida.es_picnic:
            # Si el menú general es de picnic, aplica a las ramas que están de salida/ausentes en esta toma
            if esta_fuera:
                total_comensales += ((c.num_participantes or 0) + (c.num_responsables or 0))
        else:
            # Si el menú general es estándar, aplica a las ramas que están en el campamento en esta toma
            if not esta_fuera:
                total_comensales += ((c.num_participantes or 0) + (c.num_responsables or 0))
            
    return total_comensales

# RUTAS DE LA API

@app.get("/api/ramas")
def get_ramas(): 
    return list(Rama.select().dicts())

@app.get("/api/ingredientes")
def get_ingredientes():
    return [{**i, "alergenos": parsear_alergenos(i.get("alergenos"))} for i in Ingrediente.select().dicts()]

@app.post("/api/ingredientes")
def create_ingrediente(data: IngredienteCreate):
    logger.info(f"Creando ingrediente: {data.nombre}")
    ing = Ingrediente.create(
        nombre=data.nombre,
        unidad_medida=data.unidad_medida,
        coste_unidad=data.coste_unidad,
        alergenos=json.dumps(data.alergenos, ensure_ascii=False)
    )
    return {"id": ing.id, "nombre": ing.nombre, "unidad_medida": ing.unidad_medida, "coste_unidad": ing.coste_unidad, "alergenos": data.alergenos}

@app.put("/api/ingredientes/{ing_id}")
def update_ingrediente(ing_id: int, data: IngredienteCreate):
    logger.info(f"Actualizando ingrediente ID {ing_id}")
    ing = Ingrediente.get_by_id(ing_id)
    ing.nombre = data.nombre
    ing.unidad_medida = data.unidad_medida
    ing.coste_unidad = data.coste_unidad
    ing.alergenos = json.dumps(data.alergenos, ensure_ascii=False)
    ing.save()
    return {"id": ing.id, "nombre": ing.nombre, "unidad_medida": ing.unidad_medida, "coste_unidad": ing.coste_unidad, "alergenos": data.alergenos}

@app.delete("/api/ingredientes/{ing_id}")
def delete_ingrediente(ing_id: int):
    logger.info(f"Eliminando ingrediente ID {ing_id}")
    Ingrediente.get_by_id(ing_id).delete_instance(recursive=True)
    return {"status": "ok"}

@app.get("/api/recetas")
def get_recetas():
    resultado = []
    for r in Receta.select():
        ings = [
            {
                "ingrediente_id": rel.ingrediente.id,
                "ingrediente": rel.ingrediente.nombre, 
                "unidad": rel.ingrediente.unidad_medida, 
                "cantidad_base": rel.cantidad_base,
                "alergenos": parsear_alergenos(rel.ingrediente.alergenos)
            } for rel in r.ingredientes_rel
        ]
        resultado.append({
            "id": r.id, 
            "nombre": r.nombre, 
            "porciones_base": r.porciones_base, 
            "instrucciones": r.instrucciones,
            "alergenos": obtener_alergenos_receta(r),
            "ingredientes": ings
        })
    return resultado


@app.post("/api/recetas")
def create_receta(data: RecetaCreate):
    logger.info(f"Creando receta: {data.nombre}")
    with db.atomic():
        r = Receta.create(
            nombre=data.nombre, 
            porciones_base=data.porciones_base, 
            instrucciones=data.instrucciones,
            alergenos=json.dumps(data.alergenos, ensure_ascii=False)
        )
        for item in data.ingredientes: 
            RecetaIngrediente.create(
                receta=r, 
                ingrediente_id=item.ingrediente_id, 
                cantidad_base=item.cantidad_base
            )
    return {"status": "ok"}


@app.put("/api/recetas/{rec_id}")
def update_receta(rec_id: int, data: RecetaCreate):
    logger.info(f"Actualizando receta ID {rec_id}")
    with db.atomic():
        r = Receta.get_by_id(rec_id)
        r.nombre = data.nombre
        r.porciones_base = data.porciones_base
        r.instrucciones = data.instrucciones
        r.alergenos = json.dumps(data.alergenos, ensure_ascii=False)
        r.save()
        
        RecetaIngrediente.delete().where(RecetaIngrediente.receta == r).execute()
        for item in data.ingredientes:
            RecetaIngrediente.create(
                receta=r,
                ingrediente_id=item.ingrediente_id,
                cantidad_base=item.cantidad_base
            )
    return {"status": "ok"}

@app.delete("/api/recetas/{rec_id}")
def delete_receta(rec_id: int):
    logger.info(f"Eliminando receta ID {rec_id}")
    Receta.get_by_id(rec_id).delete_instance(recursive=True)
    return {"status": "ok"}

@app.get("/api/campamentos")
def get_campamentos(): 
    return list(Campamento.select().dicts())

@app.post("/api/campamentos")
def create_campamento(data: CampamentoCreate):
    logger.info(f"Creando campamento: {data.nombre}")
    c = Campamento.create(
        nombre=data.nombre, 
        fecha_inicio=data.fecha_inicio, 
        fecha_fin=data.fecha_fin
    )
    return {"id": c.id, "nombre": c.nombre, "fecha_inicio": c.fecha_inicio, "fecha_fin": c.fecha_fin}

@app.put("/api/campamentos/{camp_id}")
def update_campamento(camp_id: int, data: CampamentoCreate):
    logger.info(f"Actualizando campamento ID {camp_id}")
    c = Campamento.get_by_id(camp_id)
    c.nombre = data.nombre
    c.fecha_inicio = data.fecha_inicio
    c.fecha_fin = data.fecha_fin
    c.save()
    return {"id": c.id, "nombre": c.nombre, "fecha_inicio": c.fecha_inicio, "fecha_fin": c.fecha_fin}

@app.delete("/api/campamentos/{camp_id}")
def delete_campamento(camp_id: int):
    logger.info(f"Eliminando campamento ID {camp_id}")
    Campamento.get_by_id(camp_id).delete_instance(recursive=True)
    return {"status": "ok"}

@app.get("/api/campamentos/{camp_id}/dias")
def get_dias_campamento(camp_id: int):
    camp = Campamento.get_by_id(camp_id)
    return generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)

import json

def obtener_tomas_ausentes(censo):
    valor = censo.tomas_ausentes

    if not valor:
        return []

    # Ya es una lista
    if isinstance(valor, list):
        return valor

    valor = str(valor).strip()

    # Caso JSON: ["Comida", "Almuerzo"]
    if valor.startswith("["):
        try:
            resultado = json.loads(valor)
            if isinstance(resultado, list):
                return [str(t).strip() for t in resultado if str(t).strip()]
        except json.JSONDecodeError:
            pass

    # Caso texto: Comida,Almuerzo
    return [
        t.strip()
        for t in valor.split(",")
        if t.strip()
    ]

@app.get("/api/campamentos/{camp_id}/censo/{fecha}")
def get_censo(camp_id: int, fecha: str):

    censos = CensoDiarioRama.select().where(
        (CensoDiarioRama.campamento_id == camp_id) &
        (CensoDiarioRama.fecha == str(fecha))
    )

    return [
        {
            "id": c.id,
            "campamento_id": c.campamento_id,
            "fecha": c.fecha,
            "rama_id": c.rama_id,
            "num_participantes": c.num_participantes,
            "num_responsables": c.num_responsables,
            "esta_de_salida": c.esta_de_salida,
            "tomas_ausentes": obtener_tomas_ausentes(c),
            "alergenos_detalle": obtener_alergenos_censo(c)
        }
        for c in censos
    ]
@app.post("/api/campamentos/{camp_id}/copiar-censo-todos")
def copiar_censo_todos(camp_id: int, datos: List[CensoItem]):
    try:
        camp = Campamento.get_by_id(camp_id)
        fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
        
        with db.atomic():
            CensoDiarioRama.delete().where(CensoDiarioRama.campamento_id == camp_id).execute()
            
            filas = []
            for f in fechas:
                for item in datos:
                    t_str = ",".join(item.tomas_ausentes) if item.tomas_ausentes else ""
                    filas.append({
                        'campamento': camp_id,
                        'fecha': f,
                        'rama': item.rama_id,
                        'num_participantes': item.num_participantes or 0,
                        'num_responsables': item.num_responsables or 0,
                        'esta_de_salida': bool(item.esta_de_salida),
                        'tomas_ausentes': t_str,
                    'alergenos_detalle': json.dumps(item.alergenos_detalle or {}, ensure_ascii=False)
                    })
            if filas:
                for i in range(0, len(filas), 100):
                    CensoDiarioRama.insert_many(filas[i:i+100]).execute()
                
        return {"status": "ok", "filas_afectadas": len(filas)}
    except Exception as e:
        logger.error(f"Error copiando censo: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/campamentos/{camp_id}/censo/{fecha}")
def save_censo(camp_id: int, fecha: str, datos: List[CensoItem]):
    fecha_str = str(fecha)
    try:
        with db.atomic():
            CensoDiarioRama.delete().where(
                (CensoDiarioRama.campamento_id == camp_id) & 
                (CensoDiarioRama.fecha == fecha_str)
            ).execute()

            filas = []
            for item in datos:
                t_str = ",".join(item.tomas_ausentes) if item.tomas_ausentes else ""
                filas.append({
                    'campamento': camp_id,
                    'fecha': fecha_str,
                    'rama': item.rama_id,
                    'num_participantes': item.num_participantes or 0,
                    'num_responsables': item.num_responsables or 0,
                    'esta_de_salida': bool(item.esta_de_salida),
                    'tomas_ausentes': t_str,
                    'alergenos_detalle': json.dumps(item.alergenos_detalle or {}, ensure_ascii=False)
                })
            if filas:
                CensoDiarioRama.insert_many(filas).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error al guardar censo: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campamentos/{camp_id}/cuadrante")
def get_cuadrante(camp_id: int):
    camp = Campamento.get_by_id(camp_id)
    fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
    tomas = ["Desayuno", "Almuerzo", "Comida", "Merienda", "Cena"]
    cuadrante = []
    
    for f in fechas:
        censos_dia = list(CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == f)))
        fila = {"fecha": f, "tomas": {}}
        for t in tomas:
            comidas = list(MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f) & (MenuComida.toma == t)))
            platos = []
            alertas = []
            for c in comidas:
                prefix = f"[{c.rama_especifica.nombre}]" if c.rama_especifica else ""
                for p in c.platos:
                    if p.es_alternativa:
                        platos.append({"nombre": p.receta.nombre, "receta_id": p.receta.id, "es_alternativa": True, "para_alergeno": p.para_alergeno, "prefijo": prefix})
                        continue
                    alergenos = obtener_alergenos_receta(p.receta)
                    faltantes = []
                    for alergeno in alergenos:
                        afectados = contar_afectados_alergeno(c, censos_dia, alergeno)
                        if afectados <= 0:
                            continue
                        cubierta = any(
                            alt.rama_especifica_id in (None, c.rama_especifica_id) and
                            any(ap.es_alternativa and ap.para_alergeno == alergeno for ap in alt.platos)
                            for alt in comidas
                            if alt.id != c.id
                        )
                        if not cubierta:
                            faltantes.append({"alergeno": alergeno, "cantidad": afectados})
                    platos.append({"nombre": p.receta.nombre, "receta_id": p.receta.id, "es_alternativa": False, "para_alergeno": None, "prefijo": prefix, "tiene_alerta": bool(faltantes)})
                    if faltantes:
                        alertas.extend(faltantes)
            fila["tomas"][t] = {"platos": platos, "alertas": alertas} if platos or alertas else "-"
        cuadrante.append(fila)
    return cuadrante

@app.get("/api/campamentos/{camp_id}/comidas_dia/{fecha}")
def get_comidas_dia(camp_id: int, fecha: str):
    comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == str(fecha)))
    resultado = []
    for c in comidas:
        platos = [{"nombre": p.receta.nombre, "receta_id": p.receta.id, "es_alternativa": p.es_alternativa, "para_alergeno": p.para_alergeno, "alergenos": obtener_alergenos_receta(p.receta)} for p in c.platos]
        destino = f"Solo {c.rama_especifica.nombre}" if c.rama_especifica else "Todo el Campamento"
        resultado.append({
            "id": c.id,
            "toma": c.toma,
            "destino": destino,
            "platos": platos,
            "plato": ", ".join(p["nombre"] for p in platos)
        })
    return resultado

ALERGENOS_VALIDOS = ["celiaco", "lactosa", "otros"]

def parsear_alergenos(valor):
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(x).lower() for x in valor]
    try:
        parsed = json.loads(valor)
        return [str(x).lower() for x in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []

def obtener_alergenos_receta(receta):
    marcados = set(parsear_alergenos(receta.alergenos))
    # También se consideran los alérgenos marcados en sus ingredientes.
    for rel in receta.ingredientes_rel:
        marcados.update(parsear_alergenos(rel.ingrediente.alergenos))
    return sorted(a for a in marcados if a in ALERGENOS_VALIDOS)

def obtener_alergenos_censo(censo):
    raw = censo.alergenos_detalle or "{}"
    if isinstance(raw, dict):
        data = raw
    else:
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
    return {a: max(0, int(data.get(a, 0) or 0)) for a in ALERGENOS_VALIDOS}

def contar_comensales_base(comida, censos_del_dia):
    """Calcula comensales y excluye de la receta estándar a quienes necesitan alternativa."""
    es_pic = es_comida_picnic(comida)
    candidatos = []
    if comida.rama_especifica_id:
        c_rama = next((c for c in censos_del_dia if c.rama_id == comida.rama_especifica_id), None)
        if c_rama:
            if es_pic or not es_rama_ausente_en_toma(c_rama, comida.toma):
                candidatos.append(c_rama)
    else:
        candidatos = [c for c in censos_del_dia if (es_rama_ausente_en_toma(c, comida.toma) if es_pic else not es_rama_ausente_en_toma(c, comida.toma))]
    return sum((c.num_participantes or 0) + (c.num_responsables or 0) for c in candidatos)

def contar_afectados_alergeno(comida, censos_del_dia, alergeno):
    es_pic = es_comida_picnic(comida)
    total = 0
    censos = []
    if comida.rama_especifica_id:
        c = next((x for x in censos_del_dia if x.rama_id == comida.rama_especifica_id), None)
        if c: censos = [c]
    else:
        censos = censos_del_dia
    for c in censos:
        if not (es_pic or not es_rama_ausente_en_toma(c, comida.toma)):
            continue
        total += obtener_alergenos_censo(c).get(alergeno, 0)
    return total

def calcular_comensales_para_receta(comida, receta, censos_del_dia, es_alternativa=False, para_alergeno=None):
    base = contar_comensales_base(comida, censos_del_dia)
    if es_alternativa and para_alergeno:
        return contar_afectados_alergeno(comida, censos_del_dia, para_alergeno)
    alergenos = obtener_alergenos_receta(receta)
    if not alergenos:
        return base
    # Sin información individual, se resta el máximo para evitar doble descuento
    # de una misma persona con más de una intolerancia registrada.
    afectados = max((contar_afectados_alergeno(comida, censos_del_dia, a) for a in alergenos), default=0)
    return max(0, base - afectados)

def es_rama_ausente_en_toma(censo, toma):
    """
    Determina si una rama está ausente (de salida/excursión) en una toma específica.
    """
    if not censo.esta_de_salida:
        return False
        
    raw = censo.tomas_ausentes
    tomas_ausentes = []
    
    if isinstance(raw, list):
        tomas_ausentes = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                tomas_ausentes = parsed
            else:
                tomas_ausentes = [t.strip() for t in raw.split(",") if t.strip()]
        except Exception:
            tomas_ausentes = [t.strip() for t in raw.split(",") if t.strip()]
            
    # Si está marcada 'esta_de_salida' pero no hay tomas específicas filtradas, 
    # se asume ausente durante toda la jornada.
    if not tomas_ausentes:
        return True
        
    return toma in tomas_ausentes


def es_comida_picnic(comida):
    """
    Comprueba si el menú o alguna de sus recetas asociadas es de picnic.
    """
    return bool(comida.es_picnic)


def calcular_comensales_comida(comida, censos_del_dia):
    es_pic = es_comida_picnic(comida)

    # Caso 1: Comida asignada a una rama específica
    if comida.rama_especifica_id:
        c_rama = next((c for c in censos_del_dia if c.rama_id == comida.rama_especifica_id), None)
        if c_rama:
            esta_fuera = es_rama_ausente_en_toma(c_rama, comida.toma)
            if es_pic:
                return (c_rama.num_participantes or 0) + (c_rama.num_responsables or 0)
            else:
                if not esta_fuera:
                    return (c_rama.num_participantes or 0) + (c_rama.num_responsables or 0)
        return 0

    # Caso 2: Comida general del campamento
    total_comensales = 0
    for c in censos_del_dia:
        esta_fuera = es_rama_ausente_en_toma(c, comida.toma)
        
        if es_pic:
            # Para menús picnic, suma las ramas que están FUERA de campamento en esta toma
            if esta_fuera:
                total_comensales += ((c.num_participantes or 0) + (c.num_responsables or 0))
        else:
            # Para menús normales, suma las ramas que están EN el campamento en esta toma
            if not esta_fuera:
                total_comensales += ((c.num_participantes or 0) + (c.num_responsables or 0))
            
    return total_comensales


@app.post("/api/campamentos/{camp_id}/comidas/{fecha}")
def agendar_comida(camp_id: int, fecha: str, data: AsignarComida):
    receta = Receta.get_by_id(data.receta_id)
    
    comida = MenuComida.create(
        campamento_id=camp_id, 
        fecha=str(fecha), 
        toma=data.toma, 
        rama_especifica_id=data.rama_id, 
        es_picnic=bool(data.es_picnic)
    )
    MenuComidaPlato.create(
        menu_comida=comida,
        receta=receta,
        es_alternativa=bool(data.es_alternativa),
        para_alergeno=data.para_alergeno if data.es_alternativa else None
    )
    return {"status": "ok"}

@app.delete("/api/campamentos/{camp_id}/comidas/{comida_id}")
def delete_comida(camp_id: int, comida_id: int):
    MenuComida.get_by_id(comida_id).delete_instance(recursive=True)
    return {"status": "ok"}

# PDF REPORTING
@app.get("/api/campamentos/{camp_id}/pdf/lista-compra")
def pdf_lista_compra(camp_id: int):
    try:
        camp = Campamento.get_by_id(camp_id)
        fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        style_subtitle = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#4B5563'))
        style_day_header = ParagraphStyle('DayHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#065F46'))

        elements.append(Paragraph(f"<b>Lista de la Compra por Días</b>", styles['Title']))
        elements.append(Paragraph(f"Campamento: {camp.nombre} ({camp.fecha_inicio} al {camp.fecha_fin})", style_subtitle))
        elements.append(Spacer(1, 15))

        coste_total_campamento = 0.0

        for f in fechas:
            censos = list(CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == f)))
            comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f))
            
            lista_dia = {}
            for comida in comidas:
                for plato in comida.platos:
                    receta = plato.receta
                    comensales = calcular_comensales_para_receta(
                        comida, receta, censos, plato.es_alternativa, plato.para_alergeno
                    )
                    factor = comensales / receta.porciones_base if receta.porciones_base > 0 else 1
                    for rel in receta.ingredientes_rel:
                        ing = rel.ingrediente
                        cant = rel.cantidad_base * factor
                        coste_u = ing.coste_unidad or 0.0
                        if ing.id not in lista_dia:
                            lista_dia[ing.id] = {"nombre": ing.nombre, "unidad": ing.unidad_medida, "cantidad": 0.0, "coste": 0.0}
                        lista_dia[ing.id]["cantidad"] += cant
                        lista_dia[ing.id]["coste"] += (cant * coste_u)

            fecha_dt = datetime.strptime(f, "%Y-%m-%d")
            fecha_formateada = fecha_dt.strftime("%d/%m/%Y")
            elements.append(Paragraph(f"📅 <b>Día: {fecha_formateada}</b>", style_day_header))
            elements.append(Spacer(1, 4))

            if not lista_dia:
                elements.append(Paragraph("<i>Sin ingredientes ni comidas programadas.</i>", styles['Normal']))
                elements.append(Spacer(1, 10))
                continue

            data_tabla = [["Ingrediente", "Cantidad", "Unidad", "Coste Est."]]
            coste_dia = 0.0

            for item in lista_dia.values():
                coste_dia += item["coste"]
                data_tabla.append([
                    item["nombre"], 
                    f"{round(item['cantidad'], 2)}", 
                    item["unidad"], 
                    f"{round(item['coste'], 2)} €"
                ])

            coste_total_campamento += coste_dia
            data_tabla.append(["Total Día", "", "", f"{round(coste_dia, 2)} €"])

            t = Table(data_tabla, colWidths=[200, 100, 100, 100])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#065F46')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('SPAN', (0,-1), (2,-1)),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E5E7EB')),
                ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 12))

        elements.append(Spacer(1, 10))
        data_resumen = [["COSTE TOTAL ESTIMADO DEL CAMPAMENTO", f"{round(coste_total_campamento, 2)} €"]]
        t_resumen = Table(data_resumen, colWidths=[350, 150])
        t_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_resumen)

        doc.build(elements)
        buffer.seek(0)
        return StreamingResponse(
            buffer, 
            media_type="application/pdf", 
            headers={"Content-Disposition": f'attachment; filename="Lista_Compra_Por_Dias_{camp_id}.pdf"'}
        )
    except Exception as e:
        logger.error(f"Error generando PDF de lista de compra: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def obtener_esta_de_salida(c) -> bool:
    """Evalúa si el censo tiene la marca 'esta_de_salida' activa."""
    val = getattr(c, 'esta_de_salida', getattr(c, 'de_salida', getattr(c, 'es_salida', False)))
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in ['true', '1', 'si', 'sí', 't', 'yes']
    return False

def parsear_tomas_ausentes(val) -> list:
    """Parsea tomas ausentes soportando arrays JSON ('["Almuerzo", "Comida"]') o texto ('Desayuno')."""
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str or val_str in ["[]", '""']:
            return []
        try:
            parsed = json.loads(val_str)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            elif isinstance(parsed, str):
                return [x.strip() for x in parsed.split(',') if x.strip()]
        except Exception:
            return [x.strip().strip('[]"\'') for x in val_str.split(',') if x.strip()]
    return []

def esta_ausente_en_toma(c, toma: str) -> bool:
    """Comprueba si una rama está ausente en una toma de comida específica."""
    if not obtener_esta_de_salida(c):
        return False
    ausentes = parsear_tomas_ausentes(getattr(c, 'tomas_ausentes', None))
    return toma.strip().lower() in [x.lower() for x in ausentes]

def obtener_nombre_rama(c) -> str:
    """Obtiene el nombre de la rama desde 'rama_nombre' o la relación 'rama'."""
    if hasattr(c, 'rama_nombre') and getattr(c, 'rama_nombre'):
        return str(getattr(c, 'rama_nombre'))
    if hasattr(c, 'rama') and getattr(c, 'rama'):
        r = getattr(c, 'rama')
        return r.nombre if hasattr(r, 'nombre') else str(r)
    return "Rama"

def formatear_alergenos_detalle(c) -> str:
    """Transforma el diccionario alergenos_detalle ({'celiaco': 1, 'lactosa': 2}) a texto."""
    detalle = getattr(c, 'alergenos_detalle', None)
    if not detalle:
        detalle = getattr(c, 'alergias_info', getattr(c, 'alergias', None))
    
    if isinstance(detalle, str):
        try:
            detalle = json.loads(detalle)
        except Exception:
            return detalle if detalle.strip() else "-"
            
    if isinstance(detalle, dict):
        items = []
        for key, count in detalle.items():
            if isinstance(count, (int, float)) and count > 0:
                nombre_k = str(key).capitalize()
                items.append(f"{nombre_k}: {count}")
        return ", ".join(items) if items else "-"
        
    return "-"

@app.get("/api/campamentos/{camp_id}/pdf/cuadrante")
def pdf_cuadrante(camp_id: int):
    try:
        camp = Campamento.get_by_id(camp_id)
        fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
        tomas = ["Desayuno", "Almuerzo", "Comida", "Merienda", "Cena"]

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4), 
            rightMargin=20, 
            leftMargin=20, 
            topMargin=20, 
            bottomMargin=20
        )
        elements = []
        styles = getSampleStyleSheet()

        style_title = styles['Title']
        style_subtitle = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#4B5563'))
        style_header = ParagraphStyle('Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.whitesmoke, alignment=1)
        style_cell = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
        style_cell_center = ParagraphStyle('CellCenter', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
        style_fecha = ParagraphStyle('Fecha', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=1)

        # =========================================================================
        # PÁGINA 1: CUADRANTE GENERAL DE MENÚS CON RAMAS AUSENTES
        # =========================================================================
        elements.append(Paragraph("<b>Cuadrante General de Menús para Cocina</b>", style_title))
        elements.append(Paragraph(f"Campamento: {camp.nombre} ({camp.fecha_inicio} al {camp.fecha_fin})", style_subtitle))
        elements.append(Spacer(1, 15))

        headers_cuadrante = [Paragraph("Fecha", style_header)] + [Paragraph(t, style_header) for t in tomas]
        data_cuadrante = [headers_cuadrante]

        for f in fechas:
            fila = [Paragraph(str(f), style_fecha)]
            censos_dia = list(CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == str(f))))
            
            for t in tomas:
                comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == str(f)) & (MenuComida.toma == t))
                platos = []
                for c in comidas:
                    prefix = f"<b>[{c.rama_especifica.nombre}]</b> " if c.rama_especifica else ""
                    for p in c.platos:
                        platos.append(f"{prefix}{p.receta.nombre}")
                
                # Identificar correctamente qué ramas están fuera en esta toma
                ausentes = [obtener_nombre_rama(c) for c in censos_dia if esta_ausente_en_toma(c, t)]
                txt_ausentes = f"<br/><font color='#DC2626'><i>Fuera: {', '.join(ausentes)}</i></font>" if ausentes else ""

                texto_celda = ("<br/>".join(platos) if platos else "-") + txt_ausentes
                fila.append(Paragraph(texto_celda, style_cell))
            
            data_cuadrante.append(fila)

        t_cuadrante = Table(data_cuadrante, colWidths=[70, 146, 146, 146, 146, 146])
        t_cuadrante.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_cuadrante)

        # =========================================================================
        # SALTO DE PÁGINA
        # =========================================================================
        elements.append(PageBreak())

        # =========================================================================
        # PÁGINA 2: DESGLOSE DETALLADO DE CENSO, EXCURSIONES Y ALÉRGENOS
        # =========================================================================
        elements.append(Paragraph("<b>Desglose Diario de Censo, Excursiones y Alérgenos</b>", style_title))
        elements.append(Paragraph(f"Campamento: {camp.nombre}", style_subtitle))
        elements.append(Spacer(1, 15))

        headers_censo = [
            Paragraph("Fecha", style_header),
            Paragraph("Rama", style_header),
            Paragraph("Part.", style_header),
            Paragraph("Resp.", style_header),
            Paragraph("Total", style_header),
            Paragraph("Salida", style_header),
            Paragraph("Tomas Ausentes", style_header),
            Paragraph("Alérgenos / Necesidades Especiales", style_header)
        ]
        data_censo = [headers_censo]

        for f in fechas:
            censos_dia = list(CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == str(f))))
            
            if not censos_dia:
                data_censo.append([
                    Paragraph(f"<b>{f}</b>", style_cell_center),
                    Paragraph("<i>Sin censo registrado</i>", style_cell),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell),
                    Paragraph("-", style_cell)
                ])
                continue

            for idx, c in enumerate(censos_dia):
                part = getattr(c, 'num_participantes', 0) or 0
                resp = getattr(c, 'num_responsables', 0) or 0
                total_rama = int(part) + int(resp)
                
                es_salida = obtener_esta_de_salida(c)
                txt_salida = "<font color='#DC2626'><b>SÍ</b></font>" if es_salida else "No"
                
                list_ausentes = parsear_tomas_ausentes(getattr(c, 'tomas_ausentes', None))
                txt_tomas_aus = ", ".join(list_ausentes) if (es_salida and list_ausentes) else "-"
                
                txt_alergias = formatear_alergenos_detalle(c)
                txt_alergias_fmt = f"<font color='#B45309'><b>{txt_alergias}</b></font>" if txt_alergias != "-" else "-"

                rama_nombre = obtener_nombre_rama(c)

                data_censo.append([
                    Paragraph(f"<b>{f}</b>" if idx == 0 else "", style_cell_center),
                    Paragraph(f"<b>{rama_nombre}</b>", style_cell),
                    Paragraph(str(part), style_cell_center),
                    Paragraph(str(resp), style_cell_center),
                    Paragraph(f"<b>{total_rama}</b>", style_cell_center),
                    Paragraph(txt_salida, style_cell_center),
                    Paragraph(txt_tomas_aus, style_cell),
                    Paragraph(txt_alergias_fmt, style_cell)
                ])

        t_censo = Table(data_censo, colWidths=[65, 85, 45, 45, 45, 45, 160, 312])
        t_censo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#047857')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_censo)

        doc.build(elements)
        buffer.seek(0)
        return StreamingResponse(
            buffer, 
            media_type="application/pdf", 
            headers={"Content-Disposition": f'attachment; filename="Cuadrante_Cocina_{camp_id}.pdf"'}
        )
    except Exception as e:
        logger.error(f"Error generando PDF de cuadrante: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    try:
        camp = Campamento.get_by_id(camp_id)
        fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
        tomas = ["Desayuno", "Almuerzo", "Comida", "Merienda", "Cena"]

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4), 
            rightMargin=20, 
            leftMargin=20, 
            topMargin=20, 
            bottomMargin=20
        )
        elements = []
        styles = getSampleStyleSheet()

        style_title = styles['Title']
        style_subtitle = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#4B5563'))
        style_header = ParagraphStyle('Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.whitesmoke, alignment=1)
        style_cell = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
        style_cell_center = ParagraphStyle('CellCenter', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
        style_fecha = ParagraphStyle('Fecha', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=1)

        # =========================================================================
        # PÁGINA 1: CUADRANTE GENERAL DE MENÚS (INTACTO)
        # =========================================================================
        elements.append(Paragraph("<b>Cuadrante General de Menús para Cocina</b>", style_title))
        elements.append(Paragraph(f"Campamento: {camp.nombre} ({camp.fecha_inicio} al {camp.fecha_fin})", style_subtitle))
        elements.append(Spacer(1, 15))

        headers_cuadrante = [Paragraph("Fecha", style_header)] + [Paragraph(t, style_header) for t in tomas]
        data_cuadrante = [headers_cuadrante]

        for f in fechas:
            fila = [Paragraph(f, style_fecha)]
            censos_dia = list(CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == f)))
            
            for t in tomas:
                comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f) & (MenuComida.toma == t))
                platos = []
                for c in comidas:
                    prefix = f"<b>[{c.rama_especifica.nombre}]</b> " if c.rama_especifica else ""
                    for p in c.platos:
                        platos.append(f"{prefix}{p.receta.nombre}")
                
                ausentes = [c.rama.nombre for c in censos_dia if t in [x.strip() for x in (c.tomas_ausentes or "").split(",") if x.strip()]]
                txt_ausentes = f"<br/><font color='#DC2626'><i>Fuera: {', '.join(ausentes)}</i></font>" if ausentes else ""

                texto_celda = ("<br/>".join(platos) if platos else "-") + txt_ausentes
                fila.append(Paragraph(texto_celda, style_cell))
            
            data_cuadrante.append(fila)

        col_widths_cuadrante = [70, 146, 146, 146, 146, 146]

        t_cuadrante = Table(data_cuadrante, colWidths=col_widths_cuadrante)
        t_cuadrante.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_cuadrante)

        # =========================================================================
        # SALTO DE PÁGINA
        # =========================================================================
        elements.append(PageBreak())

        # =========================================================================
        # PÁGINA 2: TABLA DETALLADA DE CENSO, EXCURSIONES Y ALÉRGENOS
        # =========================================================================
        elements.append(Paragraph("<b>Desglose Diario de Censo, Excursiones y Alérgenos</b>", style_title))
        elements.append(Paragraph(f"Campamento: {camp.nombre}", style_subtitle))
        elements.append(Spacer(1, 15))

        headers_censo = [
            Paragraph("Fecha", style_header),
            Paragraph("Rama", style_header),
            Paragraph("Part.", style_header),
            Paragraph("Resp.", style_header),
            Paragraph("Total", style_header),
            Paragraph("Salida", style_header),
            Paragraph("Tomas Ausentes", style_header),
            Paragraph("Alérgenos / Necesidades Especiales", style_header)
        ]
        data_censo = [headers_censo]

        for f in fechas:
            censos_dia = list(CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == f)))
            
            if not censos_dia:
                data_censo.append([
                    Paragraph(f"<b>{f}</b>", style_cell_center),
                    Paragraph("<i>Sin censo registrado</i>", style_cell),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell_center),
                    Paragraph("-", style_cell),
                    Paragraph("-", style_cell)
                ])
                continue

            for idx, c in enumerate(censos_dia):
                part = getattr(c, 'num_participantes', getattr(c, 'participantes', 0)) or 0
                resp = getattr(c, 'num_responsables', getattr(c, 'responsables', 0)) or 0
                total_rama = part + resp
                
                es_salida = getattr(c, 'de_salida', getattr(c, 'es_salida', False))
                txt_salida = "<font color='#DC2626'><b>SÍ</b></font>" if es_salida else "No"
                
                tomas_aus = (c.tomas_ausentes or "-") if es_salida else "-"
                
                # Obtener detalles de alérgenos/dietas especiales guardados en la rama/censo
                info_alergias = getattr(c, 'alergias_info', getattr(c, 'alergias', getattr(c, 'observaciones_alergias', '-'))) or "-"
                txt_alergias = f"<font color='#B45309'><b>{info_alergias}</b></font>" if info_alergias != "-" else "-"

                rama_nombre = c.rama.nombre if hasattr(c, 'rama') and c.rama else "Rama"

                data_censo.append([
                    Paragraph(f"<b>{f}</b>" if idx == 0 else "", style_cell_center), # Muestra la fecha solo en la primera rama del día
                    Paragraph(f"<b>{rama_nombre}</b>", style_cell),
                    Paragraph(str(part), style_cell_center),
                    Paragraph(str(resp), style_cell_center),
                    Paragraph(f"<b>{total_rama}</b>", style_cell_center),
                    Paragraph(txt_salida, style_cell_center),
                    Paragraph(tomas_aus, style_cell),
                    Paragraph(txt_alergias, style_cell)
                ])

        # Anchos de columna optimizados para A4 Apagado / Horizontal (802pt)
        col_widths_censo = [65, 90, 45, 45, 45, 50, 150, 312]

        t_censo = Table(data_censo, colWidths=col_widths_censo)
        t_censo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#047857')), # Encabezado verde para diferenciarlo
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_censo)

        doc.build(elements)
        buffer.seek(0)
        return StreamingResponse(
            buffer, 
            media_type="application/pdf", 
            headers={"Content-Disposition": f'attachment; filename="Cuadrante_Cocina_{camp_id}.pdf"'}
        )
    except Exception as e:
        logger.error(f"Error generando PDF de cuadrante: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campamentos/{camp_id}/pdf/recetario")
def pdf_recetario(camp_id: int):
    try:
        # ---------------------------------------------------------
        # 1. Obtener campamento
        # ---------------------------------------------------------
        camp = Campamento.get_by_id(camp_id)

        # ---------------------------------------------------------
        # 2. Obtener comidas del campamento
        # ---------------------------------------------------------
        comidas = MenuComida.select().where(
            MenuComida.campamento_id == camp_id
        )

        # ---------------------------------------------------------
        # 3. Extraer recetas únicas asignadas al campamento
        # ---------------------------------------------------------
        recetas_map = {}

        for c in comidas:
            for p in getattr(c, 'platos', []):
                receta = getattr(p, 'receta', None)

                if receta:
                    recetas_map[receta.id] = receta

        recetas = list(recetas_map.values())

        if not recetas:
            raise HTTPException(
                status_code=404,
                detail="No hay recetas registradas para este campamento"
            )

        # ---------------------------------------------------------
        # 4. Crear PDF
        # ---------------------------------------------------------
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=35,
            leftMargin=35,
            topMargin=35,
            bottomMargin=35
        )

        elements = []

        # ---------------------------------------------------------
        # 5. Estilos
        # ---------------------------------------------------------
        styles = getSampleStyleSheet()

        style_title = ParagraphStyle(
            'RecetaTitle',
            parent=styles['Title'],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#0F172A'),
            alignment=0
        )

        style_subtitle = ParagraphStyle(
            'RecetaSub',
            parent=styles['Normal'],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#64748B')
        )

        style_h2 = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#047857'),
            spaceBefore=12,
            spaceAfter=6
        )

        style_body = ParagraphStyle(
            'RecetaBody',
            parent=styles['Normal'],
            fontSize=9,
            leading=14
        )

        style_ing_header = ParagraphStyle(
            'IngHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=colors.whitesmoke
        )

        # ---------------------------------------------------------
        # 6. Generar una página por receta
        # ---------------------------------------------------------
        total_recetas = len(recetas)

        for idx, receta in enumerate(recetas):

            # -----------------------------------------------------
            # ENCABEZADO DE LA RECETA
            # -----------------------------------------------------
            nombre_receta = getattr(
                receta,
                'nombre',
                'Receta sin nombre'
            )

            elements.append(
                Paragraph(
                    f"<b>{nombre_receta}</b>",
                    style_title
                )
            )

            elements.append(
                Paragraph(
                    f"Campamento: {camp.nombre} | Recetario de Cocina",
                    style_subtitle
                )
            )

            elements.append(Spacer(1, 12))

            # -----------------------------------------------------
            # INGREDIENTES Y CANTIDADES
            # -----------------------------------------------------
            elements.append(
                Paragraph(
                    "<b>Ingredientes y Cantidades</b>",
                    style_h2
                )
            )

            ingredientes_data = [
                [
                    Paragraph("Ingrediente", style_ing_header),
                    Paragraph("Cantidad Necesaria", style_ing_header)
                ]
            ]

            # IMPORTANTE:
            # La relación correcta es receta.ingredientes_rel
            #
            # rel.ingrediente.nombre
            # rel.cantidad_base
            #
            # No usamos:
            # receta.ingredientes
            # ing.cantidad
            # -----------------------------------------------------

            ing_list = getattr(
                receta,
                'ingredientes_rel',
                []
            )

            if ing_list:

                for rel in ing_list:

                    # ---------------------------------------------
                    # Ingrediente relacionado
                    # ---------------------------------------------
                    ingrediente = getattr(
                        rel,
                        'ingrediente',
                        None
                    )

                    if ingrediente:

                        nombre_ing = getattr(
                            ingrediente,
                            'nombre',
                            'Ingrediente sin nombre'
                        )

                        # La cantidad está en la relación
                        cant_ing = getattr(
                            rel,
                            'cantidad_base',
                            None
                        )

                        # La unidad pertenece al ingrediente
                        unidad = getattr(
                            ingrediente,
                            'unidad',
                            ''
                        )

                    else:
                        nombre_ing = "Ingrediente sin nombre"
                        cant_ing = getattr(
                            rel,
                            'cantidad_base',
                            None
                        )
                        unidad = ''

                    # ---------------------------------------------
                    # Formatear cantidad
                    # ---------------------------------------------
                    if cant_ing is None:
                        cantidad_texto = "-"
                    else:
                        cantidad_texto = str(cant_ing)

                    # Evitar cosas como 2.0 cuando sea posible
                    try:
                        numero = float(cant_ing)

                        if numero.is_integer():
                            cantidad_texto = str(int(numero))
                        else:
                            cantidad_texto = str(numero)

                    except (TypeError, ValueError):
                        pass

                    # ---------------------------------------------
                    # Añadir unidad
                    # ---------------------------------------------
                    if unidad:
                        cantidad_texto = (
                            f"{cantidad_texto} {unidad}"
                        )

                    # ---------------------------------------------
                    # Añadir fila
                    # ---------------------------------------------
                    ingredientes_data.append(
                        [
                            Paragraph(
                                str(nombre_ing),
                                style_body
                            ),
                            Paragraph(
                                cantidad_texto,
                                style_body
                            )
                        ]
                    )

            else:

                ingredientes_data.append(
                    [
                        Paragraph(
                            "No especificados",
                            style_body
                        ),
                        Paragraph(
                            "-",
                            style_body
                        )
                    ]
                )

            # -----------------------------------------------------
            # TABLA DE INGREDIENTES
            # -----------------------------------------------------

            # A4 vertical con márgenes:
            # 595 - 35 - 35 = 525 pt
            t_ing = Table(
                ingredientes_data,
                colWidths=[345, 180],
                repeatRows=1
            )

            t_ing.setStyle(
                TableStyle(
                    [
                        (
                            'BACKGROUND',
                            (0, 0),
                            (-1, 0),
                            colors.HexColor('#047857')
                        ),
                        (
                            'GRID',
                            (0, 0),
                            (-1, -1),
                            0.5,
                            colors.HexColor('#CBD5E1')
                        ),
                        (
                            'VALIGN',
                            (0, 0),
                            (-1, -1),
                            'MIDDLE'
                        ),
                        (
                            'TOPPADDING',
                            (0, 0),
                            (-1, -1),
                            5
                        ),
                        (
                            'BOTTOMPADDING',
                            (0, 0),
                            (-1, -1),
                            5
                        ),
                    ]
                )
            )

            elements.append(t_ing)
            elements.append(Spacer(1, 10))

            # -----------------------------------------------------
            # PASOS DE PREPARACIÓN
            # -----------------------------------------------------
            elements.append(
                Paragraph(
                    "<b>Pasos de Preparación</b>",
                    style_h2
                )
            )

            pasos_raw = getattr(
                receta,
                'instrucciones',
                ''
            )

            # -----------------------------------------------------
            # Instrucciones como texto
            # -----------------------------------------------------
            if isinstance(pasos_raw, str) and pasos_raw.strip():

                lineas = [
                    p.strip()
                    for p in pasos_raw.split('\n')
                    if p.strip()
                ]

                for num, paso in enumerate(lineas, 1):

                    elements.append(
                        Paragraph(
                            f"<b>{num}.</b> {paso}",
                            style_body
                        )
                    )

                    elements.append(
                        Spacer(1, 4)
                    )

            # -----------------------------------------------------
            # Instrucciones como lista
            # -----------------------------------------------------
            elif isinstance(pasos_raw, list) and pasos_raw:

                for num, paso in enumerate(pasos_raw, 1):

                    elements.append(
                        Paragraph(
                            f"<b>{num}.</b> {paso}",
                            style_body
                        )
                    )

                    elements.append(
                        Spacer(1, 4)
                    )

            # -----------------------------------------------------
            # Sin instrucciones
            # -----------------------------------------------------
            else:

                elements.append(
                    Paragraph(
                        "<i>Sin instrucciones de preparación registradas.</i>",
                        style_body
                    )
                )

            # -----------------------------------------------------
            # Salto de página entre recetas
            # -----------------------------------------------------
            if idx < total_recetas - 1:
                elements.append(PageBreak())

        # ---------------------------------------------------------
        # 7. Generar PDF
        # ---------------------------------------------------------
        doc.build(elements)

        buffer.seek(0)

        # ---------------------------------------------------------
        # 8. Devolver PDF
        # ---------------------------------------------------------
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="Recetario_Campamento_{camp_id}.pdf"'
            }
        )

    except HTTPException:
        raise

    except Exception as e:

        logger.error(
            f"Error generando el recetario: {e}",
            exc_info=True
        )

        raise HTTPException(
            status_code=500,
            detail=f"Error al generar el recetario PDF: {str(e)}"
        )



@app.get("/api/database/export")
def export_database():
    try:
        # 1. Ingredientes
        ing_data = [{**i, "alergenos": parsear_alergenos(i.get("alergenos"))} for i in Ingrediente.select().dicts()]
        
        # 2. Recetas con sus ingredientes
        rec_data = []
        for r in Receta.select():
            rec_dict = {
                "nombre": r.nombre,
                "porciones_base": r.porciones_base,
                "instrucciones": r.instrucciones,
                "es_item_picnic": r.es_item_picnic,
                "alergenos": obtener_alergenos_receta(r),
                "ingredientes": [
                    {
                        "ingrediente_nombre": rel.ingrediente.nombre,
                        "cantidad_base": rel.cantidad_base
                    } for rel in r.ingredientes_rel
                ]
            }
            rec_data.append(rec_dict)
        
        # 3. Campamentos con censos y menús asociados
        camp_data = []
        for c in Campamento.select():
            censos = [
                {
                    "fecha": censo.fecha,
                    "rama_nombre": censo.rama.nombre,
                    "num_participantes": censo.num_participantes,
                    "num_responsables": censo.num_responsables,
                    "esta_de_salida": censo.esta_de_salida,
                    "tomas_ausentes": censo.tomas_ausentes,
                    "alergenos_detalle": obtener_alergenos_censo(censo)
                } for censo in c.censos
            ]
            
            menus = []
            for m in c.comidas:
                menus.append({
                    "fecha": m.fecha,
                    "toma": m.toma,
                    "rama_nombre": m.rama_especifica.nombre if m.rama_especifica else None,
                    "es_picnic": m.es_picnic,
                    "platos": [{"nombre": p.receta.nombre, "es_alternativa": p.es_alternativa, "para_alergeno": p.para_alergeno} for p in m.platos]
                })
            
            camp_data.append({
                "nombre": c.nombre,
                "fecha_inicio": c.fecha_inicio,
                "fecha_fin": c.fecha_fin,
                "censos": censos,
                "menus": menus
            })
        
        export_payload = {
            "version": "1.0",
            "fecha_exportacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ingredientes": ing_data,
            "recetas": rec_data,
            "campamentos": camp_data
        }
        
        json_bytes = json.dumps(export_payload, ensure_ascii=False, indent=2).encode('utf-8')
        buffer = BytesIO(json_bytes)
        
        fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        return StreamingResponse(
            buffer,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="copia_seguridad_{fecha_str}.json"'}
        )
    except Exception as e:
        logger.error(f"Error exportando base de datos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/database/import")
async def import_database(file: UploadFile = File(...), modo: str = Form("append")):
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        
        with db.atomic():
            # Si el modo es sobreescribir, se limpian las tablas dependientes primero
            if modo == "overwrite":
                MenuComidaPlato.delete().execute()
                MenuComida.delete().execute()
                CensoDiarioRama.delete().execute()
                RecetaIngrediente.delete().execute()
                Receta.delete().execute()
                Ingrediente.delete().execute()
                Campamento.delete().execute()
            
            # 1. Importar Ingredientes
            ing_map = {}
            for ing_item in data.get("ingredientes", []):
                nombre = ing_item["nombre"]
                ing, created = Ingrediente.get_or_create(
                    nombre=nombre,
                    defaults={
                        "unidad_medida": ing_item.get("unidad_medida", "ud"),
                        "coste_unidad": ing_item.get("coste_unidad", 0.0),
                        "alergenos": json.dumps(ing_item.get("alergenos", []), ensure_ascii=False)
                    }
                )
                if modo == "overwrite" or not created:
                    ing.unidad_medida = ing_item.get("unidad_medida", ing.unidad_medida)
                    ing.coste_unidad = ing_item.get("coste_unidad", ing.coste_unidad)
                    ing.alergenos = json.dumps(ing_item.get("alergenos", parsear_alergenos(ing.alergenos)), ensure_ascii=False)
                    ing.save()
                ing_map[nombre] = ing
                
            # 2. Importar Recetas
            rec_map = {}
            for rec_item in data.get("recetas", []):
                nombre = rec_item["nombre"]
                rec, created = Receta.get_or_create(
                    nombre=nombre,
                    defaults={
                        "porciones_base": rec_item.get("porciones_base", 10),
                        "instrucciones": rec_item.get("instrucciones", ""),
                        "es_item_picnic": rec_item.get("es_item_picnic", False),
                        "alergenos": json.dumps(rec_item.get("alergenos", []), ensure_ascii=False)
                    }
                )
                if not created:
                    rec.porciones_base = rec_item.get("porciones_base", 10)
                    rec.instrucciones = rec_item.get("instrucciones", "")
                    rec.es_item_picnic = rec_item.get("es_item_picnic", False)
                    rec.alergenos = json.dumps(rec_item.get("alergenos", parsear_alergenos(rec.alergenos)), ensure_ascii=False)
                    rec.save()
                    RecetaIngrediente.delete().where(RecetaIngrediente.receta == rec).execute()
                
                rec_map[nombre] = rec
                
                for ing_rel in rec_item.get("ingredientes", []):
                    ing_nombre = ing_rel.get("ingrediente_nombre")
                    if ing_nombre in ing_map:
                        RecetaIngrediente.create(
                            receta=rec,
                            ingrediente=ing_map[ing_nombre],
                            cantidad_base=ing_rel.get("cantidad_base", 1.0)
                        )
                        
            # 3. Importar Campamentos (junto a sus censos y menús)
            for camp_item in data.get("campamentos", []):
                nombre_camp = camp_item["nombre"]
                f_inicio = camp_item["fecha_inicio"]
                f_fin = camp_item["fecha_fin"]
                
                if modo == "append":
                    camp = Campamento.create(
                        nombre=nombre_camp,
                        fecha_inicio=f_inicio,
                        fecha_fin=f_fin
                    )
                else:
                    camp, _ = Campamento.get_or_create(
                        nombre=nombre_camp,
                        defaults={"fecha_inicio": f_inicio, "fecha_fin": f_fin}
                    )
                
                # Censos
                for c_item in camp_item.get("censos", []):
                    rama_obj = Rama.get_or_none(Rama.nombre == c_item["rama_nombre"])
                    if rama_obj:
                        CensoDiarioRama.create(
                            campamento=camp,
                            fecha=c_item["fecha"],
                            rama=rama_obj,
                            num_participantes=c_item.get("num_participantes", 0),
                            num_responsables=c_item.get("num_responsables", 0),
                            esta_de_salida=c_item.get("esta_de_salida", False),
                            tomas_ausentes=c_item.get("tomas_ausentes", ""),
                            alergenos_detalle=json.dumps(c_item.get("alergenos_detalle", {}), ensure_ascii=False)
                        )
                
                # Menús
                for m_item in camp_item.get("menus", []):
                    rama_spec = Rama.get_or_none(Rama.nombre == m_item["rama_nombre"]) if m_item.get("rama_nombre") else None
                    menu_obj = MenuComida.create(
                        campamento=camp,
                        fecha=m_item["fecha"],
                        toma=m_item["toma"],
                        rama_especifica=rama_spec,
                        es_picnic=m_item.get("es_picnic", False)
                    )
                    for plato_item in m_item.get("platos", []):
                        if isinstance(plato_item, str):
                            plato_nombre, es_alt, para_alg = plato_item, False, None
                        else:
                            plato_nombre = plato_item.get("nombre")
                            es_alt = bool(plato_item.get("es_alternativa", False))
                            para_alg = plato_item.get("para_alergeno")
                        if plato_nombre in rec_map:
                            MenuComidaPlato.create(
                                menu_comida=menu_obj,
                                receta=rec_map[plato_nombre],
                                es_alternativa=es_alt,
                                para_alergeno=para_alg
                            )
                            
        return {"status": "ok", "message": "Importación completada con éxito."}
    except Exception as e:
        logger.error(f"Error importando base de datos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error procesando el archivo: {str(e)}")

    
# Si es el ejecutable de PyInstaller:
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Modo desarrollo: main.py está en backend/, así que subimos 1 nivel a la raíz del proyecto
    BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_DIR = BASE_DIR / "static"

@app.get("/")
def read_index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/info.html")
def get_info_page():
    return FileResponse(STATIC_DIR / "info.html")

@app.get('/favicon.ico')
def favicon():
    return FileResponse(STATIC_DIR / "favicon.ico")

def start_backend(): 
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    threading.Thread(target=start_backend, daemon=True).start()
    webview.create_window("MenutronDAD - Por favor reportarme todo lo que necesiteis, bug, mejoras, etc. - MiguelDAD", "http://127.0.0.1:8000/", width=1300, height=850)
    webview.start()