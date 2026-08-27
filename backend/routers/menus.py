from fastapi import APIRouter, HTTPException
from models import Menu, MenuComida, RecetaIngrediente, Ingrediente

router = APIRouter(prefix="/api/menus", tags=["Menus"])

@router.get("/{menu_id}/lista-compra")
def generar_lista_compra(menu_id: int):
    try:
        menu = Menu.get_by_id(menu_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Menú no encontrado")

    lista_compra = {}

    # Recorrer todas las comidas agendadas en este menú
    for comida in menu.comidas:
        receta = comida.receta
        comensales_reales = comida.num_comensales
        factor_escalado = comensales_reales / receta.porciones_base

        for rel in receta.ingredientes_rel:
            ing = rel.ingrediente
            cantidad_escalada = rel.cantidad_base * factor_escalado

            if ing.id not in lista_compra:
                lista_compra[ing.id] = {
                    "nombre": ing.nombre,
                    "unidad": ing.unidad_medida,
                    "cantidad_total": 0.0,
                    "coste_estimado": 0.0
                }

            lista_compra[ing.id]["cantidad_total"] += cantidad_escalada
            lista_compra[ing.id]["coste_estimado"] += cantidad_escalada * ing.coste_unidad

    # Redondear valores
    resultado = list(lista_compra.values())
    for item in resultado:
        item["cantidad_total"] = round(item["cantidad_total"], 2)
        item["coste_estimado"] = round(item["coste_estimado"], 2)

    return {"campamento": menu.nombre_campamento, "ingredientes": resultado}