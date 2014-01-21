from trytond.pool import Pool
from .suscripcion import *

def register():
    Pool.register(
        Suscripcion,
        Diarios,
        CantidadApariciones,
        SeleccionFechas,
        Finalizar,
        SeleccionFechasPagar,
        Sale,
        module='suscripcion', type_='model')

    Pool.register(
        WizardSuscripcion,
        WizardPagar,
        module='suscripcion', type_='wizard')