from peewee import (
    SqliteDatabase, Model, CharField, FloatField, IntegerField, 
    ForeignKeyField, TextField, DateField, BooleanField
)

db = SqliteDatabase('camp_menu.db')

class BaseModel(Model):
    class Meta:
        database = db

class Ingrediente(BaseModel):
    nombre = CharField(unique=True)
    unidad_medida = CharField()
    coste_unidad = FloatField(default=0.0)

class Receta(BaseModel):
    nombre = CharField()
    porciones_base = IntegerField(default=1)  # En picnics suele ser 1 porción por persona
    instrucciones = TextField(null=True)
    es_item_picnic = BooleanField(default=False)  # Ej: Bocadillos, piezas de fruta, zumos...

class RecetaIngrediente(BaseModel):
    receta = ForeignKeyField(Receta, backref='ingredientes_rel', on_delete='CASCADE')
    ingrediente = ForeignKeyField(Ingrediente, backref='recetas_rel', on_delete='CASCADE')
    cantidad_base = FloatField()

class Campamento(BaseModel):
    nombre = CharField()
    fecha_inicio = DateField()
    fecha_fin = DateField()

class Rama(BaseModel):
    nombre = CharField(unique=True)

class CensoDiarioRama(BaseModel):
    campamento = ForeignKeyField(Campamento, backref='censos', on_delete='CASCADE')
    fecha = DateField()
    rama = ForeignKeyField(Rama, backref='censos', on_delete='CASCADE')
    num_participantes = IntegerField(default=0)
    num_responsables = IntegerField(default=0)
    esta_de_salida = BooleanField(default=False)

# REGISTRO DE COMIDA (PRESENCIAL O PICNIC)
class MenuComida(BaseModel):
    campamento = ForeignKeyField(Campamento, backref='comidas', on_delete='CASCADE')
    fecha = DateField()
    toma = CharField()  # Desayuno, Almuerzo, Comida, Merienda, Cena
    rama_especifica = ForeignKeyField(Rama, null=True, backref='comidas_especificas', on_delete='SET NULL')
    es_picnic = BooleanField(default=False)
    nota_salida = CharField(null=True)  # Ej: "Marcha 2 días - Preparar mochila de comida"

# PLATOS / ÍTEMS QUE COMPONEN LA COMIDA (Permite combinar 1º, 2º y Postre o varios ítems de Picnic)
class MenuComidaPlato(BaseModel):
    menu_comida = ForeignKeyField(MenuComida, backref='platos', on_delete='CASCADE')
    receta = ForeignKeyField(Receta, backref='en_menus', on_delete='CASCADE')