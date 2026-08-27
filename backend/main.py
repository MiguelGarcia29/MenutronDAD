import os
import logging
import threading
import uvicorn
import webview
from datetime import datetime, timedelta
from io import BytesIO
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from peewee import (
    SqliteDatabase, Model, CharField, FloatField, IntegerField, 
    ForeignKeyField, TextField, BooleanField
)

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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

class Receta(BaseModelDB):
    nombre = CharField()
    porciones_base = IntegerField(default=1)
    instrucciones = TextField(null=True)
    es_item_picnic = BooleanField(default=False)

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

class MenuComida(BaseModelDB):
    campamento = ForeignKeyField(Campamento, backref='comidas', on_delete='CASCADE')
    fecha = CharField()
    toma = CharField()
    rama_especifica = ForeignKeyField(Rama, null=True, backref='comidas_especificas', on_delete='SET NULL')
    es_picnic = BooleanField(default=False)

class MenuComidaPlato(BaseModelDB):
    menu_comida = ForeignKeyField(MenuComida, backref='platos', on_delete='CASCADE')
    receta = ForeignKeyField(Receta, backref='en_menus', on_delete='CASCADE')

def init_db():
    if db.is_closed():
        db.connect()
    db.create_tables([Ingrediente, Receta, RecetaIngrediente, Campamento, Rama, CensoDiarioRama, MenuComida, MenuComidaPlato], safe=True)
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

class IngredienteCreate(BaseModel):
    nombre: str
    unidad_medida: str
    coste_unidad: float = 0.0

class RecetaItem(BaseModel):
    ingrediente_id: int
    cantidad_base: float

class RecetaCreate(BaseModel):
    nombre: str
    porciones_base: int = 10
    instrucciones: str = ""
    es_item_picnic: bool = False
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

class AsignarComida(BaseModel):
    toma: str
    receta_id: int
    rama_id: Optional[int] = None
    es_picnic: bool = False

def generar_fechas_campamento(f_inicio_str, f_fin_str):
    f_inicio = datetime.strptime(str(f_inicio_str), "%Y-%m-%d").date()
    f_fin = datetime.strptime(str(f_fin_str), "%Y-%m-%d").date()
    fechas = []
    curr = f_inicio
    while curr <= f_fin:
        fechas.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)
    return fechas

@app.get("/api/ramas")
def get_ramas(): return list(Rama.select().dicts())

@app.get("/api/ingredientes")
def get_ingredientes(): return list(Ingrediente.select().dicts())

@app.post("/api/ingredientes")
def create_ingrediente(data: IngredienteCreate):
    logger.info(f"Creando ingrediente: {data.nombre}")
    return Ingrediente.create(**data.dict()).__dict__['__data__']

@app.put("/api/ingredientes/{ing_id}")
def update_ingrediente(ing_id: int, data: IngredienteCreate):
    logger.info(f"Actualizando ingrediente ID {ing_id}")
    ing = Ingrediente.get_by_id(ing_id)
    ing.nombre, ing.unidad_medida, ing.coste_unidad = data.nombre, data.unidad_medida, data.coste_unidad
    ing.save()
    return ing.__dict__['__data__']

@app.delete("/api/ingredientes/{ing_id}")
def delete_ingrediente(ing_id: int):
    logger.info(f"Eliminando ingrediente ID {ing_id}")
    Ingrediente.get_by_id(ing_id).delete_instance(recursive=True)
    return {"status": "ok"}

@app.get("/api/recetas")
def get_recetas():
    resultado = []
    for r in Receta.select():
        ings = [{"ingrediente": rel.ingrediente.nombre, "unidad": rel.ingrediente.unidad_medida, "cantidad_base": rel.cantidad_base} for rel in r.ingredientes_rel]
        resultado.append({"id": r.id, "nombre": r.nombre, "porciones_base": r.porciones_base, "es_item_picnic": r.es_item_picnic, "ingredientes": ings})
    return resultado

@app.post("/api/recetas")
def create_receta(data: RecetaCreate):
    logger.info(f"Creando receta: {data.nombre}")
    r = Receta.create(nombre=data.nombre, porciones_base=data.porciones_base, instrucciones=data.instrucciones, es_item_picnic=data.es_item_picnic)
    for item in data.ingredientes: RecetaIngrediente.create(receta=r, ingrediente_id=item.ingrediente_id, cantidad_base=item.cantidad_base)
    return {"status": "ok"}

@app.delete("/api/recetas/{rec_id}")
def delete_receta(rec_id: int):
    logger.info(f"Eliminando receta ID {rec_id}")
    Receta.get_by_id(rec_id).delete_instance(recursive=True)
    return {"status": "ok"}

@app.get("/api/campamentos")
def get_campamentos(): return list(Campamento.select().dicts())

@app.post("/api/campamentos")
def create_campamento(data: CampamentoCreate):
    logger.info(f"Creando campamento: {data.nombre}")
    return Campamento.create(nombre=data.nombre, fecha_inicio=data.fecha_inicio, fecha_fin=data.fecha_fin).__dict__['__data__']

@app.get("/api/campamentos/{camp_id}/dias")
def get_dias_campamento(camp_id: int):
    camp = Campamento.get_by_id(camp_id)
    return generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)

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
            "esta_de_salida": c.esta_de_salida
        }
        for c in censos
    ]

@app.post("/api/campamentos/{camp_id}/copiar-censo-todos")
def copiar_censo_todos(camp_id: int, datos: List[CensoItem]):
    logger.info(f"[LOG] Iniciando copia masiva de censo para Campamento ID {camp_id}")
    try:
        camp = Campamento.get_by_id(camp_id)
        fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
        
        with db.atomic():
            CensoDiarioRama.delete().where(CensoDiarioRama.campamento_id == camp_id).execute()
            
            filas = []
            for f in fechas:
                for item in datos:
                    filas.append({
                        'campamento': camp_id,
                        'fecha': f,
                        'rama': item.rama_id,
                        'num_participantes': item.num_participantes or 0,
                        'num_responsables': item.num_responsables or 0,
                        'esta_de_salida': bool(item.esta_de_salida)
                    })
            if filas:
                for i in range(0, len(filas), 100):
                    CensoDiarioRama.insert_many(filas[i:i+100]).execute()
                
        return {"status": "ok", "filas_afectadas": len(filas)}
    except Exception as e:
        logger.error(f"[ERROR] Error copiando censo: {str(e)}", exc_info=True)
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
                filas.append({
                    'campamento': camp_id,
                    'fecha': fecha_str,
                    'rama': item.rama_id,
                    'num_participantes': item.num_participantes or 0,
                    'num_responsables': item.num_responsables or 0,
                    'esta_de_salida': bool(item.esta_de_salida)
                })
            if filas:
                CensoDiarioRama.insert_many(filas).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[ERROR] Error al guardar censo: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campamentos/{camp_id}/cuadrante")
def get_cuadrante(camp_id: int):
    camp = Campamento.get_by_id(camp_id)
    fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
    tomas = ["Desayuno", "Almuerzo", "Comida", "Merienda", "Cena"]
    cuadrante = []
    
    for f in fechas:
        fila = {"fecha": f, "tomas": {}}
        for t in tomas:
            comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f) & (MenuComida.toma == t))
            platos_str = []
            for c in comidas:
                prefix = f"[{c.rama_especifica.nombre}]" if c.rama_especifica else ""
                for p in c.platos:
                    platos_str.append(f"{prefix} {p.receta.nombre}".strip())
            fila["tomas"][t] = " | ".join(platos_str) if platos_str else "-"
        cuadrante.append(fila)
    return cuadrante

@app.get("/api/campamentos/{camp_id}/comidas_dia/{fecha}")
def get_comidas_dia(camp_id: int, fecha: str):
    comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == str(fecha)))
    resultado = []
    for c in comidas:
        platos = [p.receta.nombre for p in c.platos]
        destino = f"Solo {c.rama_especifica.nombre}" if c.rama_especifica else "Todo el Campamento"
        resultado.append({
            "id": c.id,
            "toma": c.toma,
            "destino": destino,
            "plato": ", ".join(platos)
        })
    return resultado

@app.post("/api/campamentos/{camp_id}/comidas/{fecha}")
def agendar_comida(camp_id: int, fecha: str, data: AsignarComida):
    comida = MenuComida.create(
        campamento_id=camp_id, 
        fecha=str(fecha), 
        toma=data.toma, 
        rama_especifica_id=data.rama_id, 
        es_picnic=data.es_picnic
    )
    MenuComidaPlato.create(menu_comida=comida, receta_id=data.receta_id)
    return {"status": "ok"}

@app.delete("/api/campamentos/{camp_id}/comidas/{comida_id}")
def delete_comida(camp_id: int, comida_id: int):
    MenuComida.get_by_id(comida_id).delete_instance(recursive=True)
    return {"status": "ok"}

@app.get("/api/campamentos/{camp_id}/pdf/lista-compra")
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
            censos = CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == f))
            censo_por_rama = {}
            comensales_campamento_base = 0
            
            for c in censos:
                total_rama = c.num_participantes + c.num_responsables
                censo_por_rama[c.rama_id] = total_rama
                if not c.esta_de_salida:
                    comensales_campamento_base += total_rama

            comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f))
            
            # Cálculo de ingredientes para la fecha actual
            lista_dia = {}
            for comida in comidas:
                comensales = censo_por_rama.get(comida.rama_especifica_id, 0) if comida.rama_especifica_id else comensales_campamento_base

                for plato in comida.platos:
                    receta = plato.receta
                    factor = comensales / receta.porciones_base if receta.porciones_base > 0 else 1
                    for rel in receta.ingredientes_rel:
                        ing = rel.ingrediente
                        cant = rel.cantidad_base * factor
                        if ing.id not in lista_dia:
                            lista_dia[ing.id] = {"nombre": ing.nombre, "unidad": ing.unidad_medida, "cantidad": 0.0, "coste": 0.0}
                        lista_dia[ing.id]["cantidad"] += cant
                        lista_dia[ing.id]["coste"] += cant * ing.coste_unidad

            # Encabezado por día
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

        # Bloque resumen al final del PDF
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
        logger.error(f"Error generando PDF de lista de compra por días: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    try:
        camp = Campamento.get_by_id(camp_id)
        fechas = generar_fechas_campamento(camp.fecha_inicio, camp.fecha_fin)
        lista_totales = {}

        for f in fechas:
            censos = CensoDiarioRama.select().where((CensoDiarioRama.campamento_id == camp_id) & (CensoDiarioRama.fecha == f))
            censo_por_rama = {}
            comensales_campamento_base = 0
            
            for c in censos:
                total_rama = c.num_participantes + c.num_responsables
                censo_por_rama[c.rama_id] = total_rama
                if not c.esta_de_salida:
                    comensales_campamento_base += total_rama

            comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f))
            for comida in comidas:
                comensales = censo_por_rama.get(comida.rama_especifica_id, 0) if comida.rama_especifica_id else comensales_campamento_base

                for plato in comida.platos:
                    receta = plato.receta
                    factor = comensales / receta.porciones_base if receta.porciones_base > 0 else 1
                    for rel in receta.ingredientes_rel:
                        ing = rel.ingrediente
                        cant = rel.cantidad_base * factor
                        if ing.id not in lista_totales:
                            lista_totales[ing.id] = {"nombre": ing.nombre, "unidad": ing.unidad_medida, "cantidad": 0.0, "coste": 0.0}
                        lista_totales[ing.id]["cantidad"] += cant
                        lista_totales[ing.id]["coste"] += cant * ing.coste_unidad

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        style_subtitle = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#4B5563'))

        elements.append(Paragraph(f"Lista de la Compra Global", styles['Title']))
        elements.append(Paragraph(f"Campamento: {camp.nombre} ({camp.fecha_inicio} al {camp.fecha_fin})", style_subtitle))
        elements.append(Spacer(1, 15))

        data_tabla = [["Ingrediente", "Cantidad Total", "Unidad", "Coste Estimado"]]
        coste_total_campamento = 0

        for item in lista_totales.values():
            coste_total_campamento += item["coste"]
            data_tabla.append([item["nombre"], f"{round(item['cantidad'], 2)}", item["unidad"], f"{round(item['coste'], 2)} €"])

        data_tabla.append(["TOTAL ESTIMADO", "", "", f"{round(coste_total_campamento, 2)} €"])

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
        ]))
        elements.append(t)
        doc.build(elements)
        buffer.seek(0)
        return StreamingResponse(
            buffer, 
            media_type="application/pdf", 
            headers={"Content-Disposition": f'attachment; filename="Lista_Compra_{camp_id}.pdf"'}
        )
    except Exception as e:
        logger.error(f"Error generando PDF de lista de compra: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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

        style_subtitle = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#4B5563'))
        style_header = ParagraphStyle('Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.whitesmoke, alignment=1)
        style_cell = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
        style_fecha = ParagraphStyle('Fecha', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=1)

        elements.append(Paragraph(f"<b>Cuadrante General de Menús para Cocina</b>", styles['Title']))
        elements.append(Paragraph(f"Campamento: {camp.nombre} ({camp.fecha_inicio} al {camp.fecha_fin})", style_subtitle))
        elements.append(Spacer(1, 15))

        headers = [Paragraph("Fecha", style_header)] + [Paragraph(t, style_header) for t in tomas]
        data_tabla = [headers]

        for f in fechas:
            fila = [Paragraph(f, style_fecha)]
            for t in tomas:
                comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f) & (MenuComida.toma == t))
                platos = []
                for c in comidas:
                    prefix = f"<b>[{c.rama_especifica.nombre}]</b> " if c.rama_especifica else ""
                    for p in c.platos:
                        platos.append(f"{prefix}{p.receta.nombre}")
                texto_celda = "<br/>".join(platos) if platos else "-"
                fila.append(Paragraph(texto_celda, style_cell))
            data_tabla.append(fila)

        col_widths = [70, 146, 146, 146, 146, 146]

        t = Table(data_tabla, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t)
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

        # Estilos de celda con auto-ajuste de texto
        style_header = ParagraphStyle('Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.whitesmoke, alignment=1)
        style_cell = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=10, alignment=0)
        style_fecha = ParagraphStyle('Fecha', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=1)

        elements.append(Paragraph(f"<b>Cuadrante General de Menús para Cocina</b>", styles['Title']))
        elements.append(Paragraph(f"Campamento: {camp.nombre} ({camp.fecha_inicio} al {camp.fecha_fin})", styles['Subtitle']))
        elements.append(Spacer(1, 15))

        headers = [Paragraph("Fecha", style_header)] + [Paragraph(t, style_header) for t in tomas]
        data_tabla = [headers]

        for f in fechas:
            fila = [Paragraph(f, style_fecha)]
            for t in tomas:
                comidas = MenuComida.select().where((MenuComida.campamento_id == camp_id) & (MenuComida.fecha == f) & (MenuComida.toma == t))
                platos = []
                for c in comidas:
                    prefix = f"<b>[{c.rama_especifica.nombre}]</b> " if c.rama_especifica else ""
                    for p in c.platos:
                        platos.append(f"{prefix}{p.receta.nombre}")
                texto_celda = "<br/>".join(platos) if platos else "-"
                fila.append(Paragraph(texto_celda, style_cell))
            data_tabla.append(fila)

        # 6 Columnas distribuidas a lo ancho de la página horizontal (landscape)
        col_widths = [70, 146, 146, 146, 146, 146]

        t = Table(data_tabla, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t)
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

if not os.path.exists("static"): os.makedirs("static")

@app.get("/", response_class=HTMLResponse)
def read_index():
    if os.path.exists("static/index.html"):
        with open("static/index.html", "r", encoding="utf-8") as f: return f.read()
    return "<h1>Error: static/index.html no encontrado</h1>"

def start_backend(): uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    threading.Thread(target=start_backend, daemon=True).start()
    webview.create_window("Gestor de Menús para Campamentos", "http://127.0.0.1:8000/", width=1300, height=850)
    webview.start()