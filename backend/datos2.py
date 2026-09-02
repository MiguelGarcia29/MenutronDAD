import sys
from datetime import datetime, timedelta

try:
    from main import (
        db, Rama, Ingrediente, Receta, RecetaIngrediente,
        Campamento, CensoDiarioRama, MenuComida, MenuComidaPlato
    )
except ImportError:
    print("❌ Error: Ejecuta este script en la misma carpeta donde está 'main.py'.")
    sys.exit(1)


def poblar_base_datos():
    print("🌱 Poblando base de datos...")

    with db.atomic():
        # 1. RAMAS SCOUT
        ramas_def = ["Castores", "Lobatos", "Rangers", "Pioneros", "Rutas", "Apoyo", "Cocineros"]
        dict_ramas = {}
        for r_nom in ramas_def:
            rama_obj, _ = Rama.get_or_create(nombre=r_nom)
            dict_ramas[r_nom] = rama_obj

        # 2. INGREDIENTES
        ingredientes_datos = [
            ("Macarrones", "kg", 1.20),
            ("Tomate frito", "kg", 1.50),
            ("Carne picada mixta", "kg", 6.80),
            ("Pechuga de pollo", "kg", 7.50),
            ("Arroz redondo", "kg", 1.10),
            ("Huevos", "ud", 0.18),
            ("Pan de barra", "ud", 0.60),
            ("Jamón york", "kg", 5.50),
            ("Queso en lonchas", "kg", 6.00),
            ("Leche entera", "l", 0.90),
            ("Cacao en polvo", "kg", 3.20),
            ("Galletas Maria", "pack", 1.50),
            ("Manzanas", "kg", 1.80),
            ("Lechuga iceberg", "ud", 0.90),
        ]

        dict_ing = {}
        for nombre, unidad, coste in ingredientes_datos:
            ing, _ = Ingrediente.get_or_create(
                nombre=nombre,
                defaults={"unidad_medida": unidad, "coste_unidad": coste}
            )
            dict_ing[nombre] = ing

        # 3. RECETAS
        recetas_datos = [
            {
                "nombre": "Macarrones a la Bolonesa",
                "porciones_base": 10,
                "instrucciones": "Hervir pasta. Sofreír la carne con tomate.",
                "es_item_picnic": False,
                "ingredientes": [("Macarrones", 1.0), ("Tomate frito", 0.8), ("Carne picada mixta", 0.8)]
            },
            {
                "nombre": "Pechuga a la Plancha con Ensalada",
                "porciones_base": 10,
                "instrucciones": "Hacer pechugas a la plancha.",
                "es_item_picnic": False,
                "ingredientes": [("Pechuga de pollo", 1.5), ("Lechuga iceberg", 2.0)]
            },
            {
                "nombre": "Arroz a la Cubana",
                "porciones_base": 10,
                "instrucciones": "Hervir arroz con tomate y huevo.",
                "es_item_picnic": False,
                "ingredientes": [("Arroz redondo", 1.0), ("Huevos", 10.0), ("Tomate frito", 0.6)]
            },
            {
                "nombre": "Bocadillo de Jamón y Queso",
                "porciones_base": 1,
                "instrucciones": "Montar bocadillo.",
                "es_item_picnic": True,
                "ingredientes": [("Pan de barra", 1.0), ("Jamón york", 0.06), ("Queso en lonchas", 0.04)]
            },
            {
                "nombre": "Desayuno Scout Básico",
                "porciones_base": 10,
                "instrucciones": "Leche con cacao y galletas.",
                "es_item_picnic": False,
                "ingredientes": [("Leche entera", 2.5), ("Cacao en polvo", 0.15), ("Galletas Maria", 2.0)]
            },
            {
                "nombre": "Pieza de Fruta",
                "porciones_base": 1,
                "instrucciones": "Lavar y repartir.",
                "es_item_picnic": True,
                "ingredientes": [("Manzanas", 0.2)]
            }
        ]

        dict_recetas = {}
        for r_info in recetas_datos:
            receta, created = Receta.get_or_create(
                nombre=r_info["nombre"],
                defaults={
                    "porciones_base": r_info["porciones_base"],
                    "instrucciones": r_info["instrucciones"],
                    "es_item_picnic": r_info["es_item_picnic"]
                }
            )
            dict_recetas[r_info["nombre"]] = receta

            if created:
                for ing_nombre, cant in r_info["ingredientes"]:
                    if ing_nombre in dict_ing:
                        RecetaIngrediente.create(
                            receta=receta,
                            ingrediente=dict_ing[ing_nombre],
                            cantidad_base=cant
                        )

        # 4. CAMPAMENTO (Limpieza de datos viejos con el mismo nombre)
        nombre_camp = "Campamento Sierra 2026"
        f_inicio = datetime.now().date() + timedelta(days=5)
        f_fin = f_inicio + timedelta(days=4)

        camp_old = Campamento.get_or_none(Campamento.nombre == nombre_camp)
        if camp_old:
            MenuComidaPlato.delete().where(
                MenuComidaPlato.menu_comida.in_(MenuComida.select().where(MenuComida.campamento == camp_old))
            ).execute()
            MenuComida.delete().where(MenuComida.campamento == camp_old).execute()
            CensoDiarioRama.delete().where(CensoDiarioRama.campamento == camp_old).execute()
            camp_old.delete_instance()

        campamento = Campamento.create(
            nombre=nombre_camp,
            fecha_inicio=f_inicio.strftime("%Y-%m-%d"),
            fecha_fin=f_fin.strftime("%Y-%m-%d")
        )

        # 5. CENSOS Y MENÚS
        participantes_base = {
            "Castores": (12, 3), "Lobatos": (20, 4), "Rangers": (22, 4),
            "Pioneros": (15, 2), "Rutas": (8, 1), "Apoyo": (4, 0), "Cocineros": (5, 0)
        }

        # LAS TOMAS DEBEN IR EN MAYÚSCULA INICIAL PARA COINCIDIR CON main.py
        tomas_cuadrante = ["Desayuno", "Almuerzo", "Comida", "Merienda", "Cena"]

        dia_idx = 0
        curr_date = f_inicio
        while curr_date <= f_fin:
            fecha_str = curr_date.strftime("%Y-%m-%d")

            # Censos
            for r_nom, (n_p, n_r) in participantes_base.items():
                esta_salida = (r_nom == "Pioneros" and dia_idx == 2)
                tomas_aus = "Comida,Merienda" if esta_salida else ""

                CensoDiarioRama.create(
                    campamento=campamento,
                    fecha=fecha_str,
                    rama=dict_ramas[r_nom],
                    num_participantes=n_p,
                    num_responsables=n_r,
                    esta_de_salida=esta_salida,
                    tomas_ausentes=tomas_aus
                )

            # Menús para cada toma
            recetas_por_toma = {
                "Desayuno": [dict_recetas["Desayuno Scout Básico"]],
                "Almuerzo": [dict_recetas["Pieza de Fruta"]],
                "Comida": [dict_recetas["Macarrones a la Bolonesa"], dict_recetas["Pieza de Fruta"]] if dia_idx % 2 == 0 else [dict_recetas["Arroz a la Cubana"]],
                "Merienda": [dict_recetas["Bocadillo de Jamón y Queso"]],
                "Cena": [dict_recetas["Pechuga a la Plancha con Ensalada"]]
            }

            for toma_nombre in tomas_cuadrante:
                menu_obj = MenuComida.create(
                    campamento=campamento,
                    fecha=fecha_str,
                    toma=toma_nombre,  # "Desayuno", "Almuerzo", etc.
                    es_picnic=False
                )
                for receta_obj in recetas_por_toma[toma_nombre]:
                    MenuComidaPlato.create(menu_comida=menu_obj, receta=receta_obj)

            curr_date += timedelta(days=1)
            dia_idx += 1

    print("✅ Base de datos poblada correctamente con tomas compatibles.")


if __name__ == "__main__":
    poblar_base_datos()