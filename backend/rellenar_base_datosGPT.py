"""
rellenar_base_datos.py
----------------------
Carga datos de ejemplo en la base de datos de la aplicación
"Gestor de Menús para Campamentos".

Uso:
    python rellenar_base_datos.py

Por defecto VACÍA los datos de ingredientes, recetas, campamentos,
censos y menús y vuelve a cargarlos desde cero.

Si no quieres borrar los datos existentes:
    python rellenar_base_datos.py --no-reset
"""

import argparse
from datetime import date, timedelta

from main import (
    db,
    init_db,
    Ingrediente,
    Receta,
    RecetaIngrediente,
    Campamento,
    Rama,
    CensoDiarioRama,
    MenuComida,
    MenuComidaPlato,
)


# ---------------------------------------------------------------------------
# DATOS DE EJEMPLO
# ---------------------------------------------------------------------------

INGREDIENTES = [
    ("Arroz", "kg", 1.45),
    ("Pasta", "kg", 1.30),
    ("Macarrones", "kg", 1.35),
    ("Pan", "ud", 0.85),
    ("Pan de molde", "paquete", 1.60),
    ("Leche", "litro", 1.05),
    ("Yogur natural", "ud", 0.45),
    ("Cereales", "kg", 3.20),
    ("Galletas", "paquete", 1.50),
    ("Cacao soluble", "kg", 6.50),
    ("Azúcar", "kg", 1.20),
    ("Aceite de oliva", "litro", 7.50),
    ("Sal", "kg", 0.70),
    ("Tomate frito", "kg", 2.20),
    ("Tomate triturado", "kg", 1.70),
    ("Atún", "lata", 1.15),
    ("Maíz dulce", "lata", 0.95),
    ("Aceitunas", "kg", 4.20),
    ("Huevos", "ud", 0.22),
    ("Pollo", "kg", 6.50),
    ("Carne picada", "kg", 7.50),
    ("Salchichas", "paquete", 2.80),
    ("Chorizo", "kg", 8.90),
    ("Lentejas", "kg", 2.10),
    ("Garbanzos", "kg", 2.30),
    ("Patatas", "kg", 1.60),
    ("Cebolla", "kg", 1.50),
    ("Ajo", "kg", 5.50),
    ("Pimiento verde", "kg", 2.80),
    ("Pimiento rojo", "kg", 3.20),
    ("Zanahoria", "kg", 1.40),
    ("Calabacín", "kg", 1.80),
    ("Lechuga", "ud", 1.10),
    ("Manzana", "kg", 2.20),
    ("Plátano", "kg", 1.70),
    ("Naranja", "kg", 1.80),
    ("Limón", "kg", 2.20),
    ("Queso", "kg", 8.50),
    ("Jamón cocido", "kg", 7.90),
    ("Mermelada", "kg", 3.80),
    ("Mayonesa", "kg", 3.50),
    ("Atún en lata", "lata", 1.15),
    ("Caldo de pollo", "litro", 1.80),
    ("Caldo de pescado", "litro", 2.20),
    ("Harina", "kg", 1.10),
    ("Chocolate", "kg", 8.50),
    ("Nata para cocinar", "litro", 3.50),
]


def receta(nombre, porciones, instrucciones, ingredientes, picnic=False):
    """
    ingredientes: lista de tuplas (nombre_ingrediente, cantidad_base)
    """
    return {
        "nombre": nombre,
        "porciones_base": porciones,
        "instrucciones": instrucciones,
        "es_item_picnic": picnic,
        "ingredientes": ingredientes,
    }


RECETAS = [
    receta(
        "Tostadas con tomate y aceite", 10,
        "Tostar el pan. Triturar o rallar el tomate y repartir sobre las tostadas. "
        "Añadir aceite de oliva y una pizca de sal.",
        [("Pan", 10), ("Tomate triturado", 0.50), ("Aceite de oliva", 0.10), ("Sal", 0.02)]
    ),
    receta(
        "Desayuno de leche y cereales", 10,
        "Servir la leche fría o caliente junto con los cereales.",
        [("Leche", 2.00), ("Cereales", 0.50)]
    ),
    receta(
        "Yogur con plátano", 10,
        "Trocear los plátanos y servir con los yogures.",
        [("Yogur natural", 10), ("Plátano", 1.20)]
    ),
    receta(
        "Macarrones con tomate", 10,
        "Cocer los macarrones. Preparar el tomate frito en una cazuela y mezclar "
        "con la pasta. Añadir queso al gusto.",
        [("Macarrones", 1.00), ("Tomate frito", 1.00), ("Queso", 0.25), ("Sal", 0.02)]
    ),
    receta(
        "Arroz con pollo", 10,
        "Sofreír cebolla y pimiento. Añadir el pollo troceado y dorar. Incorporar "
        "el arroz y el caldo. Cocinar hasta que el arroz esté en su punto.",
        [("Arroz", 0.90), ("Pollo", 1.20), ("Cebolla", 0.30), ("Pimiento rojo", 0.25),
         ("Caldo de pollo", 2.00), ("Aceite de oliva", 0.10), ("Sal", 0.02)]
    ),
    receta(
        "Lentejas con chorizo", 10,
        "Sofreír cebolla, ajo y chorizo. Añadir las lentejas, patatas y zanahoria. "
        "Cubrir con agua y cocinar hasta que las lentejas estén tiernas.",
        [("Lentejas", 0.90), ("Chorizo", 0.30), ("Patatas", 0.70), ("Zanahoria", 0.30),
         ("Cebolla", 0.30), ("Ajo", 0.03), ("Aceite de oliva", 0.08), ("Sal", 0.02)]
    ),
    receta(
        "Ensalada de pasta y atún", 10,
        "Cocer la pasta y dejar enfriar. Añadir atún, maíz, aceitunas y tomate. "
        "Aliñar con aceite y sal.",
        [("Pasta", 0.80), ("Atún", 8), ("Maíz dulce", 3), ("Aceitunas", 0.20),
         ("Tomate triturado", 0.30), ("Aceite de oliva", 0.08), ("Sal", 0.02)]
    ),
    receta(
        "Tortilla de patatas", 10,
        "Pelar y cortar las patatas y la cebolla. Freír a fuego suave. Mezclar "
        "con los huevos y cuajar la tortilla.",
        [("Patatas", 1.50), ("Huevos", 20), ("Cebolla", 0.30),
         ("Aceite de oliva", 0.25), ("Sal", 0.02)]
    ),
    receta(
        "Hamburguesa con patatas", 10,
        "Cocinar las hamburguesas a la plancha. Servir con pan y patatas.",
        [("Carne picada", 1.20), ("Pan", 10), ("Patatas", 1.50),
         ("Aceite de oliva", 0.12), ("Sal", 0.02)]
    ),
    receta(
        "Garbanzos con verduras", 10,
        "Sofreír cebolla, ajo, pimiento y zanahoria. Añadir los garbanzos y "
        "cocinar unos minutos para integrar los sabores.",
        [("Garbanzos", 0.90), ("Cebolla", 0.30), ("Ajo", 0.03),
         ("Pimiento verde", 0.25), ("Zanahoria", 0.30), ("Aceite de oliva", 0.08),
         ("Sal", 0.02)]
    ),
    receta(
        "Sándwich de jamón y queso", 10,
        "Montar los sándwiches con pan de molde, jamón cocido y queso. "
        "Servir fríos o tostados.",
        [("Pan de molde", 20), ("Jamón cocido", 0.40), ("Queso", 0.30)],
        picnic=False
    ),
    receta(
        "Ensalada de atún para picnic", 10,
        "Mezclar atún, maíz, aceitunas y lechuga. Repartir en recipientes individuales.",
        [("Atún", 10), ("Maíz dulce", 4), ("Aceitunas", 0.20), ("Lechuga", 2)],
        picnic=False
    ),
    receta(
        "Fruta variada para picnic", 10,
        "Lavar y repartir las piezas de fruta entre los participantes.",
        [("Manzana", 1.00), ("Plátano", 1.00), ("Naranja", 1.00)],
        picnic=False
    ),
    receta(
        "Bizcocho de chocolate", 10,
        "Mezclar huevos, harina, azúcar, leche y chocolate. Hornear hasta que "
        "el bizcocho esté cocido.",
        [("Huevos", 4), ("Harina", 0.25), ("Azúcar", 0.20),
         ("Leche", 0.20), ("Chocolate", 0.15)]
    ),
    receta(
        "Pasta con nata y pollo", 10,
        "Cocer la pasta. Saltear el pollo, añadir la nata y mezclar con la pasta. "
        "Rectificar de sal.",
        [("Pasta", 0.90), ("Pollo", 1.00), ("Nata para cocinar", 0.50),
         ("Aceite de oliva", 0.08), ("Sal", 0.02)]
    ),
]


CAMPAMENTO = {
    "nombre": "Campamento de Verano 2026",
    "fecha_inicio": "2026-07-06",
    "fecha_fin": "2026-07-12",
}

# Participantes y responsables por rama.
CENSO = {
    "Castores": (12, 3),
    "Lobatos": (20, 4),
    "Rangers": (18, 4),
    "Pioneros": (15, 3),
    "Rutas": (8, 2),
    "Apoyo": (6, 3),
    "Cocineros": (0, 4),
}


# ---------------------------------------------------------------------------
# FUNCIONES
# ---------------------------------------------------------------------------

def reset_database():
    """Borra los datos respetando las relaciones de la aplicación."""
    with db.atomic():
        MenuComidaPlato.delete().execute()
        MenuComida.delete().execute()
        CensoDiarioRama.delete().execute()
        Campamento.delete().execute()
        RecetaIngrediente.delete().execute()
        Receta.delete().execute()
        Ingrediente.delete().execute()
        # Rama se conserva porque main.py ya crea las ramas correctas.


def cargar_ingredientes():
    ingredientes = {}
    for nombre, unidad, coste in INGREDIENTES:
        obj = Ingrediente.create(
            nombre=nombre,
            unidad_medida=unidad,
            coste_unidad=coste,
        )
        ingredientes[nombre] = obj
    return ingredientes


def cargar_recetas(ingredientes):
    recetas = {}
    for datos in RECETAS:
        r = Receta.create(
            nombre=datos["nombre"],
            porciones_base=datos["porciones_base"],
            instrucciones=datos["instrucciones"],
            es_item_picnic=datos["es_item_picnic"],
        )

        for nombre_ing, cantidad in datos["ingredientes"]:
            RecetaIngrediente.create(
                receta=r,
                ingrediente=ingredientes[nombre_ing],
                cantidad_base=cantidad,
            )

        recetas[datos["nombre"]] = r

    return recetas


def cargar_campamento():
    return Campamento.create(**CAMPAMENTO)


def cargar_censo(campamento):
    """
    Genera el mismo censo para todos los días del campamento.
    Algunas ramas tienen una salida el día 3 para probar la lógica de
    tomas ausentes y los menús picnic.
    """
    inicio = date.fromisoformat(campamento.fecha_inicio)
    fin = date.fromisoformat(campamento.fecha_fin)

    while inicio <= fin:
        fecha = inicio.isoformat()

        for nombre_rama, (participantes, responsables) in CENSO.items():
            rama = Rama.get(Rama.nombre == nombre_rama)

            salida = nombre_rama in {"Rangers", "Pioneros"} and inicio.weekday() == 2

            # Rangers y Pioneros están de excursión el miércoles.
            tomas_ausentes = ""
            if salida:
                tomas_ausentes = "Desayuno,Almuerzo,Comida"

            CensoDiarioRama.create(
                campamento=campamento,
                fecha=fecha,
                rama=rama,
                num_participantes=participantes,
                num_responsables=responsables,
                esta_de_salida=salida,
                tomas_ausentes=tomas_ausentes,
            )

        inicio += timedelta(days=1)


def agregar_comida(campamento, fecha, toma, receta_obj, rama=None, picnic=False):
    """Crea una MenuComida y su MenuComidaPlato."""
    comida = MenuComida.create(
        campamento=campamento,
        fecha=fecha,
        toma=toma,
        rama_especifica=rama,
        es_picnic=picnic or receta_obj.es_item_picnic,
    )
    MenuComidaPlato.create(
        menu_comida=comida,
        receta=receta_obj,
    )


def cargar_menus(campamento, recetas):
    """
    Crea un cuadrante de ejemplo para todos los días.
    Se incluyen comidas generales, una comida específica de rama y un picnic.
    """
    inicio = date.fromisoformat(campamento.fecha_inicio)
    fin = date.fromisoformat(campamento.fecha_fin)

    menu_por_dia = [
        ("Desayuno", "Desayuno de leche y cereales"),
        ("Almuerzo", "Yogur con plátano"),
        ("Comida", "Arroz con pollo"),
        ("Merienda", "Sándwich de jamón y queso"),
        ("Cena", "Lentejas con chorizo"),
    ]

    dia_num = 0
    actual = inicio

    while actual <= fin:
        fecha = actual.isoformat()

        # Cambiamos la comida principal algunos días para que el cuadrante
        # de ejemplo sea más variado.
        if dia_num == 1:
            comida_principal = "Macarrones con tomate"
        elif dia_num == 2:
            comida_principal = "Ensalada de pasta y atún"
        elif dia_num == 3:
            comida_principal = "Garbanzos con verduras"
        elif dia_num == 4:
            comida_principal = "Hamburguesa con patatas"
        elif dia_num == 5:
            comida_principal = "Pasta con nata y pollo"
        else:
            comida_principal = "Arroz con pollo"

        agregar_comida(campamento, fecha, "Desayuno", recetas[menu_por_dia[0][1]])
        agregar_comida(campamento, fecha, "Almuerzo", recetas[menu_por_dia[1][1]])
        agregar_comida(campamento, fecha, "Comida", recetas[comida_principal])
        agregar_comida(campamento, fecha, "Merienda", recetas[menu_por_dia[3][1]])
        agregar_comida(campamento, fecha, "Cena", recetas[menu_por_dia[4][1]])

        # El miércoles hay una comida picnic para Rangers y Pioneros.
        if actual.weekday() == 2:
            for nombre_rama in ("Rangers", "Pioneros"):
                rama = Rama.get(Rama.nombre == nombre_rama)
                agregar_comida(
                    campamento,
                    fecha,
                    "Comida",
                    recetas["Fruta variada para picnic"],
                    rama=rama,
                    picnic=False,
                )
                agregar_comida(
                    campamento,
                    fecha,
                    "Almuerzo",
                    recetas["Sándwich de jamón y queso"],
                    rama=rama,
                    picnic=False,
                )

        actual += timedelta(days=1)
        dia_num += 1


def main():
    parser = argparse.ArgumentParser(description="Rellenar la base de datos del Gestor de Menús.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="No borrar los datos existentes antes de insertar los datos de ejemplo.",
    )
    args = parser.parse_args()

    init_db()

    try:
        if not args.no_reset:
            print("Vaciando datos anteriores...")
            reset_database()

        print("Cargando ingredientes...")
        ingredientes = cargar_ingredientes()

        print("Cargando recetas...")
        recetas = cargar_recetas(ingredientes)

        print("Creando campamento...")
        campamento = cargar_campamento()

        print("Cargando censos...")
        cargar_censo(campamento)

        print("Cargando cuadrante y menús...")
        cargar_menus(campamento, recetas)

        print("\n======================================")
        print(" BASE DE DATOS RELLENADA CORRECTAMENTE")
        print("======================================")
        print(f"Ingredientes: {Ingrediente.select().count()}")
        print(f"Recetas:      {Receta.select().count()}")
        print(f"Campamentos:  {Campamento.select().count()}")
        print(f"Censos:       {CensoDiarioRama.select().count()}")
        print(f"Comidas:      {MenuComida.select().count()}")
        print("\nCampamento creado:")
        print(f"  {campamento.nombre}")
        print(f"  {campamento.fecha_inicio} -> {campamento.fecha_fin}")

    finally:
        if not db.is_closed():
            db.close()


if __name__ == "__main__":
    main()
