import os
import sys
from datetime import datetime, timedelta

# Importamos la conexión a la base de datos y los modelos directamente de main.py
try:
    from main import (
        db, init_db,
        Ingrediente, Receta, RecetaIngrediente,
        Campamento, Rama, CensoDiarioRama,
        MenuComida, MenuComidaPlato
    )
except ImportError:
    print("❌ Error: No se pudo importar 'main.py'. Asegúrate de que este script está en la misma carpeta.")
    sys.exit(1)


def rellenar_datos():
    print("🚀 Inicializando base de datos...")
    init_db()

    if db.is_closed():
        db.connect()

    with db.atomic():
        print("🧹 Limpiando datos anteriores para evitar duplicados...")
        MenuComidaPlato.delete().execute()
        MenuComida.delete().execute()
        CensoDiarioRama.delete().execute()
        Campamento.delete().execute()
        RecetaIngrediente.delete().execute()
        Receta.delete().execute()
        Ingrediente.delete().execute()

        print("⚜️ 0. Verificando e insertando Ramas por defecto...")
        ramas_default = ["Castores", "Lobatos", "Rangers", "Pioneros", "Rutas", "Apoyo", "Cocineros"]
        for r_nom in ramas_default:
            Rama.get_or_create(nombre=r_nom)

        print("📦 1. Insertando Ingredientes reales con precios estimados...")
        ingredientes_data = [
            ("Macarrones", "kg", 1.20),
            ("Tomate frito", "kg", 1.50),
            ("Carne picada mixta", "kg", 7.50),
            ("Lentejas", "kg", 1.80),
            ("Chorizo de guiso", "kg", 8.00),
            ("Patatas", "kg", 0.90),
            ("Cebollas", "kg", 1.10),
            ("Ajos", "kg", 4.50),
            ("Aceite de oliva", "L", 6.50),
            ("Sal", "kg", 0.40),
            ("Pechuga de pollo", "kg", 6.80),
            ("Pan de barra", "ud", 0.50),
            ("Huevos", "docena", 2.20),
            ("Leche entera", "L", 0.90),
            ("Cacao en polvo", "kg", 4.00),
            ("Galletas María", "kg", 2.00),
            ("Manzanas", "kg", 1.60),
            ("Plátanos", "kg", 1.70),
            ("Atún en lata", "kg", 9.00),
            ("Jamón York", "kg", 6.00),
            ("Queso en lonchas", "kg", 7.00),
            ("Arroz", "kg", 1.30),
            ("Salchichas de cerdo", "kg", 5.50),
            ("Mayonesa", "kg", 3.20),
            ("Lechuga", "ud", 0.90),
            ("Zumo de fruta", "L", 1.10),
            ("Mantequilla", "kg", 6.00),
            ("Mermelada de fresa", "kg", 3.50),
        ]

        ing_objs = {}
        for nombre, unidad, coste in ingredientes_data:
            ing_objs[nombre] = Ingrediente.create(
                nombre=nombre,
                unidad_medida=unidad,
                coste_unidad=coste
            )

        print("👨‍🍳 2. Insertando Recetas de cocina campamentera...")
        recetas_data = [
            (
                "Desayuno Scout Básico", 10,
                "1. Calentar la leche en ollas grandes de cocina.\n2. Servir con cacao en polvo solubilizado.\n3. Repartir 4 galletas María por participante.",
                False,
                [("Leche entera", 2.5), ("Cacao en polvo", 0.3), ("Galletas María", 0.8)]
            ),
            (
                "Macarrones con Tomate y Carne", 10,
                "1. Sofreír la cebolla y el ajo picados en aceite de oliva.\n2. Añadir la carne picada, salpimentar y dorar bien.\n3. Verter el tomate frito y dejar reducir 10 min.\n4. Cocer los macarrones en abundante agua con sal.\n5. Escurrir la pasta y mezclar bien con la salsa.",
                False,
                [("Macarrones", 1.2), ("Tomate frito", 1.5), ("Carne picada mixta", 1.0), ("Cebollas", 0.3), ("Ajos", 0.05), ("Aceite de oliva", 0.1), ("Sal", 0.05)]
            ),
            (
                "Lentejas Estofadas con Chorizo", 10,
                "1. En una olla grande, añadir patatas troceadas, cebolla, ajo, chorizo en rodajas y las lentejas.\n2. Cubrir de agua, salar y añadir un chorrito de aceite.\n3. Cocer a fuego lento durante 50-60 minutos hasta que estén tiernas.",
                False,
                [("Lentejas", 1.0), ("Chorizo de guiso", 0.5), ("Patatas", 1.5), ("Cebollas", 0.4), ("Ajos", 0.05), ("Aceite de oliva", 0.1), ("Sal", 0.05)]
            ),
            (
                "Bocadillo de Pechuga Empanada y Lechuga", 10,
                "1. Freír las pechugas de pollo empanadas.\n2. Abrir las barras de pan a la mitad.\n3. Colocar una cama de lechuga limpia y añadir el filete de pollo.\n4. Envolver individualmente en papel de aluminio para la marcha.",
                True,
                [("Pechuga de pollo", 1.5), ("Pan de barra", 10.0), ("Lechuga", 2.0), ("Aceite de oliva", 0.2)]
            ),
            (
                "Bocadillo de Jamón y Queso", 10,
                "1. Abrir las barras de pan.\n2. Untar una fina capa de mantequilla.\n3. Colocar 2 lonchas de jamón york y 2 de queso loncheado por bocadillo.\n4. Envolver en papel de aluminio.",
                True,
                [("Pan de barra", 10.0), ("Jamón York", 0.8), ("Queso en lonchas", 0.6), ("Mantequilla", 0.15)]
            ),
            (
                "Arroz a la Cubana con Huevo", 10,
                "1. Cocer el arroz en agua hirviendo con sal y ajos machacados.\n2. Freír los huevos en tandas.\n3. Servir el arroz caliente, cubierto de tomate frito y acompañado del huevo frito.",
                False,
                [("Arroz", 1.1), ("Tomate frito", 1.2), ("Huevos", 0.83), ("Ajos", 0.05), ("Aceite de oliva", 0.15), ("Sal", 0.05)]
            ),
            (
                "Salchichas al Vino con Puré de Patatas", 10,
                "1. Dorar las salchichas en sartén con cebolla picada.\n2. Cocer patatas y chafarlas con mantequilla y sal para elaborar un puré cremoso.\n3. Servir las salchichas acompañadas de la guarnición de puré.",
                False,
                [("Salchichas de cerdo", 1.5), ("Patatas", 2.0), ("Cebollas", 0.3), ("Mantequilla", 0.2), ("Aceite de oliva", 0.1), ("Sal", 0.05)]
            ),
            (
                "Pieza de Fruta (Manzana / Plátano)", 10,
                "1. Lavar adecuadamente la fruta con agua limpia.\n2. Repartir 1 pieza por participante.",
                False,
                [("Manzanas", 0.8), ("Plátanos", 0.8)]
            ),
        ]

        rec_objs = {}
        for nombre, porciones, instrucciones, es_picnic, ings_lista in recetas_data:
            rec = Receta.create(
                nombre=nombre,
                porciones_base=porciones,
                instrucciones=instrucciones,
                es_item_picnic=es_picnic
            )
            rec_objs[nombre] = rec
            for nom_ing, cant in ings_lista:
                RecetaIngrediente.create(
                    receta=rec,
                    ingrediente=ing_objs[nom_ing],
                    cantidad_base=cant
                )

        print("🏕️ 3. Creando Campamento de prueba de 7 días...")
        camp = Campamento.create(
            nombre="Campamento de Verano Sierra de Espuña 2026",
            fecha_inicio="2026-07-15",
            fecha_fin="2026-07-21"
        )

        print("👥 4. Configurando Censos Diarios (con marchas y ausencias por rama)...")
        ramas = {r.nombre: r for r in Rama.select()}
        
        fechas_camp = [
            "2026-07-15", "2026-07-16", "2026-07-17", 
            "2026-07-18", "2026-07-19", "2026-07-20", "2026-07-21"
        ]

        censo_habitual = {
            "Castores": (12, 3),
            "Lobatos": (22, 4),
            "Rangers": (18, 3),
            "Pioneros": (14, 2),
            "Rutas": (8, 1),
            "Apoyo": (4, 0),
            "Cocineros": (3, 0)
        }

        for fecha in fechas_camp:
            for nom_rama, (participantes, responsables) in censo_habitual.items():
                rama_obj = ramas.get(nom_rama)
                if not rama_obj:
                    continue

                esta_salida = False
                tomas_ausentes = ""

                # Simulación 1: Pioneros de raid/marcha de 2 días (Días 18 y 19)
                if nom_rama == "Pioneros":
                    if fecha == "2026-07-18":
                        esta_salida = True
                        tomas_ausentes = "Comida,Merienda,Cena"
                    elif fecha == "2026-07-19":
                        esta_salida = True
                        tomas_ausentes = "Desayuno,Almuerzo,Comida"

                # Simulación 2: Excursión de día completo de Lobatos (Día 17)
                if nom_rama == "Lobatos" and fecha == "2026-07-17":
                    tomas_ausentes = "Comida,Merienda"

                CensoDiarioRama.create(
                    campamento=camp,
                    fecha=fecha,
                    rama=rama_obj,
                    num_participantes=participantes,
                    num_responsables=responsables,
                    esta_de_salida=esta_salida,
                    tomas_ausentes=tomas_ausentes
                )

        print("📅 5. Agendando Menús en el Cuadrante del Campamento...")
        for fecha in fechas_camp:
            # --- DESAYUNO ---
            c_des = MenuComida.create(campamento=camp, fecha=fecha, toma="Desayuno", es_picnic=False)
            MenuComidaPlato.create(menu_comida=c_des, receta=rec_objs["Desayuno Scout Básico"])

            # --- COMIDA ---
            if fecha == "2026-07-17":
                # Día de excursión de Lobatos: Picnic para ellos, caliente para el resto
                c_com_lobatos = MenuComida.create(
                    campamento=camp, fecha=fecha, toma="Comida", 
                    rama_especifica=ramas.get("Lobatos"), es_picnic=True
                )
                MenuComidaPlato.create(menu_comida=c_com_lobatos, receta=rec_objs["Bocadillo de Pechuga Empanada y Lechuga"])

                c_com_resto = MenuComida.create(campamento=camp, fecha=fecha, toma="Comida", es_picnic=False)
                MenuComidaPlato.create(menu_comida=c_com_resto, receta=rec_objs["Macarrones con Tomate y Carne"])
                MenuComidaPlato.create(menu_comida=c_com_resto, receta=rec_objs["Pieza de Fruta (Manzana / Plátano)"])

            elif fecha in ["2026-07-15", "2026-07-19", "2026-07-21"]:
                c_com = MenuComida.create(campamento=camp, fecha=fecha, toma="Comida", es_picnic=False)
                MenuComidaPlato.create(menu_comida=c_com, receta=rec_objs["Macarrones con Tomate y Carne"])
                MenuComidaPlato.create(menu_comida=c_com, receta=rec_objs["Pieza de Fruta (Manzana / Plátano)"])
            else:
                c_com = MenuComida.create(campamento=camp, fecha=fecha, toma="Comida", es_picnic=False)
                MenuComidaPlato.create(menu_comida=c_com, receta=rec_objs["Lentejas Estofadas con Chorizo"])
                MenuComidaPlato.create(menu_comida=c_com, receta=rec_objs["Pieza de Fruta (Manzana / Plátano)"])

            # --- CENA ---
            if fecha in ["2026-07-15", "2026-07-17", "2026-07-20"]:
                c_cen = MenuComida.create(campamento=camp, fecha=fecha, toma="Cena", es_picnic=False)
                MenuComidaPlato.create(menu_comida=c_cen, receta=rec_objs["Arroz a la Cubana con Huevo"])
            else:
                c_cen = MenuComida.create(campamento=camp, fecha=fecha, toma="Cena", es_picnic=False)
                MenuComidaPlato.create(menu_comida=c_cen, receta=rec_objs["Salchichas al Vino con Puré de Patatas"])

    print("\n✅ ¡Base de datos poblada con éxito!")
    print(f"📊 Resumen de registros creados:")
    print(f"   • Ramas:               {Rama.select().count()}")
    print(f"   • Ingredientes:        {Ingrediente.select().count()}")
    print(f"   • Recetas:             {Receta.select().count()}")
    print(f"   • Campamentos:         {Campamento.select().count()}")
    print(f"   • Registros de Censo:  {CensoDiarioRama.select().count()}")
    print(f"   • Comidas en Menú:     {MenuComida.select().count()}")


if __name__ == "__main__":
    rellenar_datos()