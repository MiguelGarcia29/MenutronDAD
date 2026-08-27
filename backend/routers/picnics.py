from fastapi import APIRouter, HTTPException
from models import MenuComida, CensoDiarioRama

router = APIRouter(prefix="/api/picnics", tags=["Picnics"])

@router.get("/{campamento_id}/hoja-preparacion/{fecha}")
def obtener_hoja_preparacion_picnic(campamento_id: int, fecha: str):
    # Buscar todas las comidas marcadas como picnic para la fecha indicada
    comidas_picnic = MenuComida.select().where(
        (MenuComida.campamento_id == campamento_id) &
        (MenuComida.fecha == fecha) &
        (MenuComida.es_picnic == True)
    )

    resultado = []

    for comida in comidas_picnic:
        rama = comida.rama_especifica
        
        # Calcular total de personas que van a la salida (Educandos + Scouters)
        censo = CensoDiarioRama.get_or_none(
            (CensoDiarioRama.campamento_id == campamento_id) &
            (CensoDiarioRama.fecha == fecha) &
            (CensoDiarioRama.rama == rama)
        )
        
        total_personas = (censo.num_participantes + censo.num_responsables) if censo else 0

        # Obtener los ítems que componen la bolsa de picnic
        items_bolsa = []
        for plato in comida.platos:
            receta = plato.receta
            items_bolsa.append({
                "item": receta.nombre,
                "cantidad_unidades": total_personas * receta.porciones_base
            })

        resultado.append({
            "rama": rama.nombre if rama else "General",
            "toma": comida.toma,
            "total_personas": total_personas,
            "nota": comida.nota_salida,
            "contenido_bolsa": items_bolsa
        })

    return {"fecha": fecha, "picnics_a_preparar": resultado}