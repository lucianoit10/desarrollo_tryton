from trytond.pool import Pool
from .edicion import *
from .party import *
from .invoice import *

def register():
    Pool.register(
        Edicion,
        PublicacionDiario,
        PublicacionRadio,
        PublicacionDigital,
        PublicacionPresupuestadaDiario,
        PublicacionPresupuestadaRadio,
        PublicacionPresupuestadaDigital,
        EdicionPublicacionDigital,
        TipoYCategoria,
        Producto,
        AvisoComun,
        AvisoEspecial,
        FunebreDestacado,
        ClasificadoDestacado,
        SeleccionFechas,
        Finalizar,
        Party,
        Invoice,
        InvoiceLine,
        module='edicion', type_='model')
    
    Pool.register(
        PresupuestacionCentimetros,
        module='edicion', type_='wizard')
