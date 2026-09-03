"""
Carga un caso de ejemplo completo para Gestor de Menús y Cocina.

USO:
    python rellenar_datos_ejemplo.py

Por defecto BORRA los datos actuales de la aplicación y crea un campamento
completo de 5 días con ramas, censo, salidas, alérgenos, recetas, alternativas
 y menús.
"""

import json
from datetime import date, timedelta

# Importa los mismos modelos y la BD que utiliza la aplicación.
try:
    from main import (
        db, init_db,
        Ingrediente, Receta, RecetaIngrediente,
        Campamento, Rama, CensoDiarioRama,
        MenuComida, MenuComidaPlato,
    )
except ImportError:
    from main_alergenos import (
        db, init_db,
        Ingrediente, Receta, RecetaIngrediente,
        Campamento, Rama, CensoDiarioRama,
        MenuComida, MenuComidaPlato,
    )

ALERGENOS = ("celiaco", "lactosa", "otros")
TOMAS = ("Desayuno", "Comida", "Almuerzo",  "Merienda", "Cena")


def limpiar_base():
    """Elimina los datos de ejemplo/anterior para dejar un caso reproducible."""
    with db.atomic():
        MenuComidaPlato.delete().execute()
        MenuComida.delete().execute()
        CensoDiarioRama.delete().execute()
        RecetaIngrediente.delete().execute()
        Receta.delete().execute()
        Ingrediente.delete().execute()
        Campamento.delete().execute()
    print("🧹 Base de datos limpiada.")


def crear_ingredientes():
    datos = [
        ("Leche", "litro", 0.95, ["lactosa"]),
        ("Yogur natural", "ud", 0.42, ["lactosa"]),
        ("Queso rallado", "kg", 8.90, ["lactosa"]),
        ("Mantequilla", "kg", 7.80, ["lactosa"]),
        ("Pan de trigo", "kg", 2.10, ["celiaco"]),
        ("Pasta de trigo", "kg", 1.75, ["celiaco"]),
        ("Pan sin gluten", "kg", 5.90, []),
        ("Pasta sin gluten", "kg", 4.50, []),
        ("Arroz", "kg", 1.60, []),
        ("Lentejas", "kg", 2.30, []),
        ("Garbanzos", "kg", 2.15, []),
        ("Pollo", "kg", 6.20, []),
        ("Pavo", "kg", 7.40, []),
        ("Atún", "kg", 8.90, []),
        ("Huevo", "docena", 2.80, []),
        ("Tomate frito", "kg", 2.40, []),
        ("Tomate natural", "kg", 2.10, []),
        ("Lechuga", "ud", 1.20, []),
        ("Zanahoria", "kg", 1.30, []),
        ("Cebolla", "kg", 1.35, []),
        ("Pimiento", "kg", 2.40, []),
        ("Calabacín", "kg", 1.70, []),
        ("Patata", "kg", 1.45, []),
        ("Plátano", "kg", 1.80, []),
        ("Manzana", "kg", 2.20, []),
        ("Naranja", "kg", 1.70, []),
        ("Aceite de oliva", "litro", 7.90, []),
        ("Sal", "kg", 0.70, []),
        ("Especias", "kg", 12.00, []),
        ("Caldo vegetal", "litro", 2.90, ["otros"]),
        ("Mayonesa", "kg", 4.80, ["otros"]),
        ("Chocolate", "kg", 8.50, ["lactosa"]),
    ]
    ingredientes = {}
    for nombre, unidad, coste, alergenos in datos:
        ing = Ingrediente.create(
            nombre=nombre,
            unidad_medida=unidad,
            coste_unidad=coste,
            alergenos=json.dumps(alergenos, ensure_ascii=False),
        )
        ingredientes[nombre] = ing
    return ingredientes


def crear_receta(nombre, porciones, instrucciones, ingredientes, alergenos=None):
    receta = Receta.create(
        nombre=nombre,
        porciones_base=porciones,
        instrucciones=instrucciones,
        alergenos=json.dumps(alergenos or [], ensure_ascii=False),
    )
    for ing_nombre, cantidad in ingredientes:
        RecetaIngrediente.create(
            receta=receta,
            ingrediente=ing_nombre,
            cantidad_base=cantidad,
        )
    return receta


def crear_recetas(ing):
    R = {}

    R["Tostadas con tomate"] = crear_receta(
        "Tostadas con tomate", 10,
        "Tostar el pan y servir con tomate rallado y aceite.",
        [(ing["Pan de trigo"], 0.70), (ing["Tomate natural"], 0.50), (ing["Aceite de oliva"], 0.10)],
    )
    R["Tostadas sin gluten"] = crear_receta(
        "Tostadas sin gluten", 10,
        "Tostar pan sin gluten y servir con tomate y aceite.",
        [(ing["Pan sin gluten"], 0.70), (ing["Tomate natural"], 0.50), (ing["Aceite de oliva"], 0.10)],
    )
    R["Leche con cereales"] = crear_receta(
        "Leche con cereales", 10,
        "Servir la leche fría o templada con cereales.",
        [(ing["Leche"], 2.0)],
    )
    R["Bebida vegetal con cereales"] = crear_receta(
        "Bebida vegetal con cereales", 10,
        "Servir bebida vegetal con cereales sin lácteos.",
        [(ing["Arroz"], 0.80)],
        [],
    )
    R["Pasta boloñesa"] = crear_receta(
        "Pasta boloñesa", 10,
        "Cocer la pasta. Preparar el sofrito, añadir pollo picado y tomate y mezclar.",
        [(ing["Pasta de trigo"], 1.20), (ing["Pollo"], 0.90), (ing["Tomate frito"], 1.00), (ing["Cebolla"], 0.30)],
    )
    R["Pasta boloñesa sin gluten"] = crear_receta(
        "Pasta boloñesa sin gluten", 10,
        "Cocer pasta sin gluten y mezclar con pollo y salsa de tomate sin ingredientes con gluten.",
        [(ing["Pasta sin gluten"], 1.20), (ing["Pollo"], 0.90), (ing["Tomate frito"], 1.00), (ing["Cebolla"], 0.30)],
    )
    R["Arroz con pollo"] = crear_receta(
        "Arroz con pollo", 10,
        "Sofreír verduras, añadir pollo y arroz, cubrir con caldo y cocinar hasta que esté tierno.",
        [(ing["Arroz"], 1.20), (ing["Pollo"], 1.00), (ing["Pimiento"], 0.30), (ing["Cebolla"], 0.30), (ing["Caldo vegetal"], 2.50)],
    )
    R["Arroz con pollo sin caldo"] = crear_receta(
        "Arroz con pollo sin caldo", 10,
        "Preparar arroz con pollo utilizando agua, aceite y especias, sin caldo preparado.",
        [(ing["Arroz"], 1.20), (ing["Pollo"], 1.00), (ing["Pimiento"], 0.30), (ing["Cebolla"], 0.30)],
        ["otros"],
    )
    R["Lentejas con verduras"] = crear_receta(
        "Lentejas con verduras", 10,
        "Cocer lentejas con patata, zanahoria, cebolla y pimiento hasta que estén tiernas.",
        [(ing["Lentejas"], 1.10), (ing["Patata"], 0.70), (ing["Zanahoria"], 0.30), (ing["Cebolla"], 0.25)],
    )
    R["Ensalada de pasta"] = crear_receta(
        "Ensalada de pasta", 10,
        "Cocer la pasta, enfriar y mezclar con tomate, lechuga, atún y mayonesa.",
        [(ing["Pasta de trigo"], 0.90), (ing["Tomate natural"], 0.50), (ing["Lechuga"], 2.0), (ing["Atún"], 0.40), (ing["Mayonesa"], 0.20)],
    )
    R["Ensalada de arroz"] = crear_receta(
        "Ensalada de arroz", 10,
        "Cocer el arroz y mezclar en frío con tomate, lechuga y atún.",
        [(ing["Arroz"], 0.90), (ing["Tomate natural"], 0.50), (ing["Lechuga"], 2.0), (ing["Atún"], 0.40)],
    )
    R["Tortilla de patatas"] = crear_receta(
        "Tortilla de patatas", 10,
        "Freír patata y cebolla, mezclar con huevo y cuajar la tortilla.",
        [(ing["Patata"], 1.40), (ing["Cebolla"], 0.30), (ing["Huevo"], 2.0), (ing["Aceite de oliva"], 0.20)],
    )
    R["Tortilla con patata para otros"] = crear_receta(
        "Tortilla con patata para otros", 10,
        "Preparar tortilla casera sin caldo vegetal ni salsas preparadas.",
        [(ing["Patata"], 1.40), (ing["Cebolla"], 0.30), (ing["Huevo"], 2.0), (ing["Aceite de oliva"], 0.20)],
        ["otros"],
    )
    R["Yogur con fruta"] = crear_receta(
        "Yogur con fruta", 10,
        "Servir yogur natural acompañado de fruta fresca.",
        [(ing["Yogur natural"], 10), (ing["Plátano"], 1.0)],
    )
    R["Fruta variada"] = crear_receta(
        "Fruta variada", 10,
        "Servir fruta fresca lavada y cortada.",
        [(ing["Manzana"], 1.5), (ing["Naranja"], 1.5), (ing["Plátano"], 1.0)],
    )
    R["Pollo al horno con patatas"] = crear_receta(
        "Pollo al horno con patatas", 10,
        "Hornear el pollo sazonado junto con las patatas hasta que esté bien cocinado.",
        [(ing["Pollo"], 1.30), (ing["Patata"], 1.50), (ing["Aceite de oliva"], 0.15)],
    )
    R["Garbanzos con verduras"] = crear_receta(
        "Garbanzos con verduras", 10,
        "Cocer garbanzos con patata, zanahoria, cebolla y pimiento.",
        [(ing["Garbanzos"], 1.10), (ing["Patata"], 0.70), (ing["Zanahoria"], 0.30), (ing["Pimiento"], 0.25)],
    )
    R["Sándwich mixto"] = crear_receta(
        "Sándwich mixto", 10,
        "Preparar sándwich de pan, queso y pavo.",
        [(ing["Pan de trigo"], 0.90), (ing["Queso rallado"], 0.30), (ing["Pavo"], 0.40)],
    )
    R["Sándwich de pavo sin gluten"] = crear_receta(
        "Sándwich de pavo sin gluten", 10,
        "Preparar con pan sin gluten, pavo y tomate.",
        [(ing["Pan sin gluten"], 0.90), (ing["Pavo"], 0.40), (ing["Tomate natural"], 0.30)],
    )
    R["Cacao con leche"] = crear_receta(
        "Cacao con leche", 10,
        "Calentar la leche y añadir cacao/chocolate.",
        [(ing["Leche"], 2.0), (ing["Chocolate"], 0.15)],
    )
    R["Bebida vegetal con cacao"] = crear_receta(
        "Bebida vegetal con cacao", 10,
        "Calentar bebida vegetal y añadir cacao sin lácteos.",
        [(ing["Arroz"], 0.80)],
    )

    return R


def crear_campamento():
    camp = Campamento.create(
        nombre="CTO Sierra Verde 2026 - Caso de Prueba",
        fecha_inicio="2026-07-13",
        fecha_fin="2026-07-17",
    )
    print(f"⛺ Campamento creado: {camp.nombre} ({camp.fecha_inicio} → {camp.fecha_fin})")
    return camp


def crear_ramas():
    nombres = ["Castores", "Lobatos", "Rangers", "Pioneros", "Rutas", "Apoyo", "Cocineros"]
    return {n: Rama.get_or_create(nombre=n)[0] for n in nombres}


def crear_censo(camp, ramas):
    # Censo base: participantes + responsables. Los alérgenos son cantidades
    # dentro de cada rama, por lo que sirven para comprobar la lógica de cantidades.
    base = {
        "Castores": (18, 3),
        "Lobatos": (24, 4),
        "Rangers": (22, 4),
        "Pioneros": (20, 4),
        "Rutas": (12, 3),
        "Apoyo": (6, 5),
        "Cocineros": (4, 2),
    }

    # Cambios diarios para que el caso pruebe que el cálculo depende del día.
    cambios = {
        "2026-07-14": {"Rangers": (-2, 0), "Pioneros": (0, -1)},
        "2026-07-15": {"Lobatos": (-3, 0), "Rutas": (-2, 0)},
        "2026-07-16": {"Castores": (-2, 0), "Pioneros": (-2, 0)},
        "2026-07-17": {"Rangers": (-4, -1), "Rutas": (0, -1)},
    }

    alergias = {
        "Castores": {"celiaco": 1, "lactosa": 2, "otros": 0},
        "Lobatos": {"celiaco": 2, "lactosa": 1, "otros": 1},
        "Rangers": {"celiaco": 1, "lactosa": 2, "otros": 0},
        "Pioneros": {"celiaco": 0, "lactosa": 2, "otros": 1},
        "Rutas": {"celiaco": 1, "lactosa": 1, "otros": 0},
        "Apoyo": {"celiaco": 0, "lactosa": 1, "otros": 0},
        "Cocineros": {"celiaco": 0, "lactosa": 0, "otros": 0},
    }

    # Salidas/excursiones: se marcan tomas concretas, no el día completo.
    salidas = {
        ("2026-07-14", "Rangers"): ["Almuerzo", "Comida"],
        ("2026-07-15", "Lobatos"): ["Desayuno", "Almuerzo"],
        ("2026-07-15", "Rutas"): ["Almuerzo", "Comida", "Merienda"],
        ("2026-07-16", "Castores"): ["Comida", "Merienda"],
        ("2026-07-17", "Rangers"): ["Almuerzo", "Comida", "Merienda"],
    }

    inicio = date.fromisoformat(camp.fecha_inicio)
    fin = date.fromisoformat(camp.fecha_fin)
    d = inicio
    while d <= fin:
        fecha = d.isoformat()
        for nombre, rama in ramas.items():
            participantes, responsables = base[nombre]
            for rama_cambio, (dp, dr) in cambios.get(fecha, {}).items():
                if nombre == rama_cambio:
                    participantes += dp
                    responsables += dr

            CensoDiarioRama.create(
                campamento=camp,
                fecha=fecha,
                rama=rama,
                num_participantes=participantes,
                num_responsables=responsables,
                esta_de_salida=(fecha, nombre) in salidas,
                tomas_ausentes=json.dumps(salidas.get((fecha, nombre), []), ensure_ascii=False),
                alergenos_detalle=json.dumps(alergias[nombre], ensure_ascii=False),
            )
        d += timedelta(days=1)

    print("📋 Censo de 5 días creado con salidas y alérgenos.")


def añadir_menu(camp, fecha, toma, receta, rama=None, alternativa=False, para=None, picnic=False):
    comida = MenuComida.create(
        campamento=camp,
        fecha=fecha,
        toma=toma,
        rama_especifica=rama,
        es_picnic=picnic,
    )
    MenuComidaPlato.create(
        menu_comida=comida,
        receta=receta,
        es_alternativa=alternativa,
        para_alergeno=para if alternativa else None,
    )
    return comida


def crear_menus(camp, ramas, R):
    # Menú normal de 5 días. Se añaden alternativas donde realmente hay
    # personas afectadas, y deliberadamente se deja una alerta de ejemplo.
    menus = {
        "2026-07-13": {
            "Desayuno": "Tostadas con tomate",
            "Almuerzo": "Fruta variada",
            "Comida": "Pasta boloñesa",
            "Merienda": "Yogur con fruta",
            "Cena": "Pollo al horno con patatas",
        },
        "2026-07-14": {
            "Desayuno": "Leche con cereales",
            "Almuerzo": "Fruta variada",
            "Comida": "Arroz con pollo",
            "Merienda": "Sándwich mixto",
            "Cena": "Lentejas con verduras",
        },
        "2026-07-15": {
            "Desayuno": "Tostadas con tomate",
            "Almuerzo": "Yogur con fruta",
            "Comida": "Ensalada de pasta",
            "Merienda": "Cacao con leche",
            "Cena": "Garbanzos con verduras",
        },
        "2026-07-16": {
            "Desayuno": "Leche con cereales",
            "Almuerzo": "Fruta variada",
            "Comida": "Tortilla de patatas",
            "Merienda": "Sándwich mixto",
            "Cena": "Arroz con pollo",
        },
        "2026-07-17": {
            "Desayuno": "Cacao con leche",
            "Almuerzo": "Fruta variada",
            "Comida": "Pasta boloñesa",
            "Merienda": "Yogur con fruta",
            "Cena": "Pollo al horno con patatas",
        },
    }

    for fecha, tomas in menus.items():
        for toma, nombre in tomas.items():
            añadir_menu(camp, fecha, toma, R[nombre])

    # Alternativas: algunas generales y una específica de rama para probar
    # la lógica de alcance por rama.
    añadir_menu(camp, "2026-07-13", "Comida", R["Pasta boloñesa sin gluten"], alternativa=True, para="celiaco")
    añadir_menu(camp, "2026-07-13", "Merienda", R["Bebida vegetal con cacao"], alternativa=True, para="lactosa")

    añadir_menu(camp, "2026-07-14", "Desayuno", R["Bebida vegetal con cereales"], alternativa=True, para="lactosa")
    añadir_menu(camp, "2026-07-14", "Comida", R["Arroz con pollo sin caldo"], alternativa=True, para="otros")
    # Los Rangers están de salida en comida; esta alternativa específica
    # permite comprobar que las asignaciones por rama también funcionan.
    añadir_menu(camp, "2026-07-14", "Cena", R["Bebida vegetal con cereales"], rama=ramas["Rangers"], alternativa=True, para="lactosa")

    añadir_menu(camp, "2026-07-15", "Comida", R["Ensalada de arroz"], alternativa=True, para="celiaco")
    añadir_menu(camp, "2026-07-15", "Merienda", R["Bebida vegetal con cacao"], alternativa=True, para="lactosa")

    # Aquí dejamos SIN alternativa de lactosa a propósito: el cuadrante debe
    # señalar la comida en rojo para demostrar que la alerta funciona.
    añadir_menu(camp, "2026-07-16", "Merienda", R["Sándwich de pavo sin gluten"], alternativa=True, para="celiaco")
    añadir_menu(camp, "2026-07-16", "Cena", R["Arroz con pollo sin caldo"], alternativa=True, para="otros")

    añadir_menu(camp, "2026-07-17", "Desayuno", R["Bebida vegetal con cacao"], alternativa=True, para="lactosa")
    añadir_menu(camp, "2026-07-17", "Comida", R["Pasta boloñesa sin gluten"], alternativa=True, para="celiaco")
    añadir_menu(camp, "2026-07-17", "Merienda", R["Bebida vegetal con cereales"], alternativa=True, para="lactosa")

    print("🍽️ Menús normales y alternativas creados.")


def resumen(camp):
    print("\n" + "=" * 68)
    print("✅ CASO DE EJEMPLO CARGADO CORRECTAMENTE")
    print("=" * 68)
    print(f"Campamento : {camp.nombre}")
    print(f"Fechas     : {camp.fecha_inicio} → {camp.fecha_fin}")
    print(f"Ramas      : {Rama.select().count()}")
    print(f"Ingredientes: {Ingrediente.select().count()}")
    print(f"Recetas    : {Receta.select().count()}")
    print(f"Censos     : {CensoDiarioRama.select().count()}")
    print(f"Menús      : {MenuComida.select().count()}")
    print(f"Platos     : {MenuComidaPlato.select().count()}")
    print("\nCasos que puedes comprobar en la interfaz:")
    print("  • 13/07: pasta normal + alternativa sin gluten + alternativa sin lactosa.")
    print("  • 14/07: Rangers de salida en almuerzo/comida.")
    print("  • 15/07: Lobatos y Rutas de salida en distintas tomas.")
    print("  • 16/07: Castores de salida y una ALERTA de lactosa deliberadamente sin cubrir.")
    print("  • 17/07: Rangers de salida y varias alternativas.")
    print("  • Hay alérgenos derivados de ingredientes y otros marcados directamente en recetas.")
    print("\n💡 Abre el cuadrante y la previsualización de comidas para comprobar las alertas.")


def main():
    init_db()
    limpiar_base()
    camp = crear_campamento()
    ramas = crear_ramas()
    ingredientes = crear_ingredientes()
    recetas = crear_recetas(ingredientes)
    crear_censo(camp, ramas)
    crear_menus(camp, ramas, recetas)
    resumen(camp)


if __name__ == "__main__":
    main()
