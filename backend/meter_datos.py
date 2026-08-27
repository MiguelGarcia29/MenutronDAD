import os
from datetime import datetime, timedelta

# Importar la base de datos y los modelos directamente desde main
from main import (
    db, Ingrediente, Receta, RecetaIngrediente, Campamento, Rama,
    CensoDiarioRama, MenuComida, MenuComidaPlato
)

def poblar_datos():
    if db.is_closed():
        db.connect()

    print("🧹 Limpiando base de datos...")
    with db.atomic():
        MenuComidaPlato.delete().execute()
        MenuComida.delete().execute()
        CensoDiarioRama.delete().execute()
        RecetaIngrediente.delete().execute()
        Receta.delete().execute()
        Ingrediente.delete().execute()
        Campamento.delete().execute()
        Rama.delete().execute()

    print("🌱 Insertando Ramas Scout...")
    ramas_nombres = ["Castores", "Lobatos", "Rangers", "Pioneros", "Rutas", "Apoyo", "Cocineros"]
    dict_ramas = {nombre: Rama.create(nombre=nombre) for nombre in ramas_nombres}

    print("🥕 Insertando Ingredientes...")
    ingredientes_list = [
        ("Arroz", "kg", 1.25), ("Macarrones", "kg", 1.10), ("Tomate frito", "kg", 1.40),
        ("Carne picada mixta", "kg", 7.20), ("Pechuga de pollo", "kg", 6.80), ("Patatas", "kg", 0.95),
        ("Aceite de oliva", "l", 8.50), ("Huevos", "ud", 0.22), ("Pan de barra", "ud", 0.75),
        ("Atún en lata", "kg", 9.50), ("Leche entera", "l", 0.90), ("Cacao en polvo", "kg", 4.20),
        ("Galletas María", "kg", 2.10), ("Manzanas", "kg", 1.60), ("Plátanos", "kg", 1.80),
        ("Lentejas", "kg", 1.50), ("Cereales", "kg", 3.00), ("Jamón york", "kg", 5.50),
        ("Queso en lonchas", "kg", 6.00), ("Nocilla / Cacao untar", "kg", 4.80), ("Hamburguesas", "ud", 0.85)
    ]
    dict_ings = {nombre: Ingrediente.create(nombre=nombre, unidad_medida=um, coste_unidad=coste) 
                 for nombre, um, coste in ingredientes_list}

    print("📖 Creando Recetas...")
    def crear_receta(nombre, picnic, ingredientes_cantidades):
        rec = Receta.create(nombre=nombre, porciones_base=10, es_item_picnic=picnic)
        for ing_nombre, cant in ingredientes_cantidades:
            RecetaIngrediente.create(receta=rec, ingrediente=dict_ings[ing_nombre], cantidad_base=cant)
        return rec

    # Desayunos
    d1 = crear_receta("Leche con Cacao y Galletas", False, [("Leche entera", 2.5), ("Cacao en polvo", 0.2), ("Galletas María", 0.8)])
    d2 = crear_receta("Leche con Cacao y Cereales", False, [("Leche entera", 2.5), ("Cacao en polvo", 0.2), ("Cereales", 0.6)])

    # Almuerzos
    a1 = crear_receta("Pieza de Manzana", True, [("Manzanas", 2.0)])
    a2 = crear_receta("Pieza de Plátano", True, [("Plátanos", 2.0)])

    # Comidas
    c1 = crear_receta("Macarrones con Tomate y Carne", False, [("Macarrones", 1.2), ("Carne picada mixta", 1.0), ("Tomate frito", 0.8)])
    c2 = crear_receta("Lentejas Estofadas", False, [("Lentejas", 1.0), ("Patatas", 1.5), ("Tomate frito", 0.4)])
    c3 = crear_receta("Arroz a la Cubana con Huevo", False, [("Arroz", 1.0), ("Tomate frito", 0.8), ("Huevos", 10.0)])
    c4 = crear_receta("Pollo Asado con Patatas Fritas", False, [("Pechuga de pollo", 2.5), ("Patatas", 3.0), ("Aceite de oliva", 0.5)])

    # Meriendas
    m1 = crear_receta("Bocadillo de Atún y Tomate", True, [("Pan de barra", 10.0), ("Atún en lata", 0.6), ("Tomate frito", 0.3)])
    m2 = crear_receta("Bocadillo de Nocilla", True, [("Pan de barra", 10.0), ("Nocilla / Cacao untar", 0.5)])
    m3 = crear_receta("Bocadillo de Jamón y Queso", True, [("Pan de barra", 10.0), ("Jamón york", 0.5), ("Queso en lonchas", 0.5)])

    # Cenas
    cn1 = crear_receta("Tortilla de Patatas", False, [("Huevos", 20.0), ("Patatas", 2.5), ("Aceite de oliva", 0.3)])
    cn2 = crear_receta("Hamburguesa Completa", False, [("Hamburguesas", 10.0), ("Pan de barra", 10.0), ("Queso en lonchas", 0.4)])

    print("⛺ Creando Campamento de Verano...")
    camp1 = Campamento.create(
        nombre="Campamento de Verano 2026 - Sierra de Gredos",
        fecha_inicio="2026-07-15",
        fecha_fin="2026-07-20"
    )

    menu_rotativo = [
        {"Desayuno": d1, "Almuerzo": a1, "Comida": c1, "Merienda": m2, "Cena": c4},
        {"Desayuno": d2, "Almuerzo": a2, "Comida": c2, "Merienda": m1, "Cena": cn1},
        {"Desayuno": d1, "Almuerzo": a1, "Comida": c3, "Merienda": m3, "Cena": cn2},
        {"Desayuno": d2, "Almuerzo": a2, "Comida": c4, "Merienda": m2, "Cena": c1},
        {"Desayuno": d1, "Almuerzo": a1, "Comida": c2, "Merienda": m1, "Cena": cn1},
        {"Desayuno": d2, "Almuerzo": a2, "Comida": c3, "Merienda": m3, "Cena": cn2},
    ]

    f_inicio = datetime.strptime(camp1.fecha_inicio, "%Y-%m-%d").date()
    f_fin = datetime.strptime(camp1.fecha_fin, "%Y-%m-%d").date()
    
    fecha_curr = f_inicio
    idx = 0
    total_comidas = 0

    print("🗓️ Generando Cuadrante Diarios en MenuComida y MenuComidaPlato...")
    with db.atomic():
        while fecha_curr <= f_fin:
            fecha_str = fecha_curr.strftime("%Y-%m-%d")

            # Censo Diario
            for r_nombre, r_obj in dict_ramas.items():
                is_staff = r_nombre in ["Cocineros", "Apoyo"]
                CensoDiarioRama.create(
                    campamento=camp1,
                    fecha=fecha_str,
                    rama=r_obj,
                    num_participantes=0 if is_staff else 15,
                    num_responsables=4 if is_staff else 3,
                    esta_de_salida=False
                )

            # Insertar las 5 tomas para este día
            plan_dia = menu_rotativo[idx % len(menu_rotativo)]
            for toma_nombre, receta_obj in plan_dia.items():
                mc = MenuComida.create(
                    campamento=camp1,
                    fecha=fecha_str,
                    toma=toma_nombre,
                    rama_especifica=None,
                    es_picnic=receta_obj.es_item_picnic
                )
                MenuComidaPlato.create(
                    menu_comida=mc,
                    receta=receta_obj
                )
                total_comidas += 1

            fecha_curr += timedelta(days=1)
            idx += 1

    if not db.is_closed():
        db.close()

    print(f"✅ ¡Éxito! Se crearon {total_comidas} registros de comida vinculados a sus platos.")

if __name__ == "__main__":
    poblar_datos()