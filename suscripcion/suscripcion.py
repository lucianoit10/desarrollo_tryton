from decimal import Decimal
from trytond.pool import Pool
from trytond.pyson import Eval
from datetime import timedelta
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button

select_apariciones=    [
                           ('1', '1- Dia/s especifico/s'),
                           ('7', '2- Semana/s(7 dias)'),
                           ('30', '3- Mes/es (30 dias)'),
                           ('365', '4- ANUAL(365 dias)'),
                       ]

def crear_linea_producto(sale,producto,cantidad,descripcion):
    linea = Pool().get('sale.line')
    nueva = linea.create([{
                'sale':sale,
                'product': producto,
                'sequence':'0',
                'type':'line',
                'unit': producto.default_uom,
                'unit_price':producto.list_price,
                'quantity':Decimal(cantidad),
                'description':descripcion
                }])[0]
    nueva.save()

def crear_factura(suscrip,cant,desc):
    date = Pool().get('ir.date')
    sale = Pool().get('sale.sale')
    producto = Pool().get('product.product')
    pay_term = Pool().get('account.invoice.payment_term')
    p = producto.search([('name','=','Diario Impreso')])[0]
    p_term = pay_term.search([('name','=','Cuenta Corriente')])[0]
    #calculo del invoice address
    invoice_address = suscrip.cliente.address_get(type='invoice')
    shipment_address = suscrip.cliente.address_get(type='delivery')
    nueva = sale.create([{
                'party':suscrip.cliente,
                'payment_term': p_term,
                'suscripcion':suscrip,
                'invoice_address' : invoice_address,
                'shipment_address' : shipment_address,
                'sale_date' :date.today(),
                }])[0]
    nueva.save()
    crear_linea_producto(nueva,p,cant,desc)
    nueva.state = 'processing'
    nueva.save()
    #crea factura
    nueva.create_invoice('out_invoice')
    nueva.create_invoice('out_credit_note')
    nueva.set_invoice_state()
    nueva.create_shipment('out')
    nueva.create_shipment('return')
    nueva.set_shipment_state()



class Suscripcion(Workflow,ModelSQL,ModelView):
    'Suscripcion'
    __name__ = 'suscripcion.suscripcion'
    _rec_name = 'fecha'
    cliente = fields.Many2One('party.party', 'CLIENTE', states={'readonly' : Eval('state') != 'activa'}, depends=['state'], required=True, ondelete='CASCADE')
    fecha = fields.Function (fields.Date('ULTIMA EDICION ABONADA'), 'get_fecha')
    fecha_abonada = fields.Date('FECHA')
    creacion = fields.Date('FECHA DE CREACION', readonly=True)
    ediciones = fields.One2Many('suscripcion.diarios', 'suscripcion', 'EDICIONES',states={'readonly' : Eval('state') != 'activa'}, depends=['state'])
    ventas = fields.One2Many('sale.sale', 'suscripcion', 'PAGOS', states={'readonly' : Eval('state') != 'activa'}, depends=['state'])
    state = fields.Selection([  ('activa','activa'),
                                ('concretada','concretada'),
                                ('cancelada','cancelada')],'ESTADO', readonly=True, required=True)

    @classmethod
    def default_creacion(self):
        date = Pool().get('ir.date')
        return date.today()

    @classmethod
    def default_state(self):
        return 'activa'

    def get_fecha(self, name):
        if self.fecha_abonada !=None:
            return self.fecha_abonada
        else:
            return None

    @classmethod
    def __setup__(cls):
        super(Suscripcion, cls).__setup__()
        cls._transitions |= set((
                ('activa', 'concretada'),
                ('activa', 'cancelada'),
                ))
        cls._buttons.update({
                'cancelada': {
                    'invisible': Eval('state')!='activa',
                    'icon': 'tryton-cancel',
                    },
                'pagar': {
                    'invisible': Eval('state')!='activa',
                    'icon': 'tryton-go-next',
                    },
                'suscribir': {
                    'invisible': Eval('state')!='activa',
                    'icon': 'tryton-ok',
                    },
                })


    @classmethod
    @ModelView.button
    @Workflow.transition('cancelada')
    def cancelada(cls, suscrip):
        diarios = Pool().get('suscripcion.diarios')
        for s in suscrip:
            ediciones = s.ediciones
            cant = 0
            text = 'Fechas Entregadas:\n'
            for e in ediciones:
                if e.state == 'entregado':
                    cant = cant + 1
                    e.state = 'pagada'
                    e.save()
                    s.fecha_abonada = e.fecha
                    text += ' - '+ str(e.fecha)
            text += ' - '
            for e in ediciones:
                if e.state == 'pendiente':
                    diarios.delete([e])
            s.save()
            crear_factura(s,cant,text)

    @classmethod
    @ModelView.button_action('suscripcion.wizard_pagar')
    def pagar(cls, suscrip):
        pass

    @classmethod
    @ModelView.button_action('suscripcion.wizard_suscripcion')
    def suscribir(cls, suscrip):
        pass

#EDICIONES
class Diarios(Workflow,ModelSQL,ModelView):
    'Diarios'
    __name__ = 'suscripcion.diarios'
    fecha = fields.Function (fields.Date('FECHA'), 'get_fecha')
    suscripcion = fields.Many2One('suscripcion.suscripcion', 'SUSCRIPCION', ondelete='CASCADE')
    edicion = fields.Many2One('edicion.edicion', 'EDICION', states={'readonly' : Eval('estado') == 'entregado'}, required=True)
    state = fields.Selection([  ('pendiente','Sin Entregar'),
                                 ('entregado','Entregada'),
                                 ('pagada','Pagada'),
                              ],'ESTADO', readonly=True, required=True)

    def get_fecha(self, name):
        if self.edicion !=None:
            return self.edicion.fecha
        else:
            return None

    @classmethod
    def default_state(self):
        return 'pendiente'

    @classmethod
    def __setup__(cls):
        super(Diarios, cls).__setup__()
        cls._transitions |= set((
                ('pendiente', 'entregado'),
                ('entregado', 'pagada'),
                ))
        cls._buttons.update({
                'entregado': {
                    'invisible': Eval('state')!='pendiente',
                    'icon': 'tryton-ok',
                    },
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('entregado')
    def entregado(cls, publ):
        pass
#VENTAS
class Sale(Workflow, ModelSQL, ModelView):
    'Sale'
    __name__ = 'sale.sale'
    suscripcion = fields.Many2One('suscripcion.suscripcion', 'SUSCRIPCION')


#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#-------------------------------<WIZARD>---------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

class CantidadApariciones(ModelView):
    'CantidadApariciones'
    __name__ = 'suscripcion.cantidad_apariciones'
    apariciones = fields.Selection(select_apariciones, 'ENTREGAS',  on_change=['apariciones'], required=True)
    cant_apariciones = fields.Numeric('NRO.', states={'readonly': (Eval('apariciones') == '365')}, required=True)
    inicio = fields.Date('INICIO', states={'readonly': (Eval('apariciones') == '1')}, required=True)

    def on_change_apariciones(self):
        if self.apariciones == '365':
            v = 1
            return {'cant_apariciones': v}
        return{}


class SeleccionFechas(ModelView):
    'SeleccionFechas'
    __name__ = 'suscripcion.seleccion_fechas'
    cant_apariciones = fields.Numeric('CANTIDAD DE APARICIONES YA CARGADAS:', readonly=True)
    fecha = fields.Date('FECHA DE LA EDICION O MENCION', required=True)

class Finalizar(ModelView):
    'Finalizar'
    __name__ = 'suscripcion.finalizar'
    texto = fields.Char('EL PROCESO DE SUSCRIPCION A TERMINADO CON EXITO', readonly=True)

class WizardSuscripcion(Wizard):
    'WizardSuscripcion'
    __name__ = 'suscripcion.wizard_suscripcion'
    #-----------------------------------------INICIO-----------------------------------------#
    start_view = StateView('suscripcion.cantidad_apariciones',
                      'suscripcion.cantidad_apariciones_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Siguiente', 'trans_seleccion_fecha', 'tryton-go-next', default=True)])

    #-----------------------------------ELECCION DE FECHAS----------------------------------#
    seleccion_fechas = StateView('suscripcion.seleccion_fechas',
                      'suscripcion.seleccion_fechas_form',
                      [Button('Siguiente', 'final_seleccion', 'tryton-go-next', default=True)])

    #-----------------------------------------FIN-----------------------------------------#
    finalizar = StateView('suscripcion.finalizar',
                  'suscripcion.finalizar_form',
                  [Button('Finalizar', 'end', 'tryton-ok', default=True)])

    start = StateTransition()
    trans_seleccion_fecha = StateTransition()
    final_seleccion = StateTransition()

    def crear_diarios(self,fecha):
        edicion = Pool().get('edicion.edicion')
        diario = Pool().get('suscripcion.diarios')
        suscrip = Pool().get('suscripcion.suscripcion')
        edic = 0
        try:
            edic= edicion(edicion.search([('fecha', '=', fecha)])[0])
        except:
            edic=edicion.create([{
            'fecha':fecha
            }])[0]
            edic.save()
        d = diario.create([{
                'suscripcion': suscrip(Transaction().context.get('active_id')),
                'edicion' : edic,
                }])[0]
        d.save()


    def default_start_view(self,fields):
        default = {}
        default['apariciones']='1'
        default['cant_apariciones']=1
        return default

    def default_seleccion_fechas(self,fields):
        default = {}
        try:
            default['cant_apariciones']=Decimal(self.seleccion_fechas.cant_apariciones) +1
        except:
            default['cant_apariciones']=1
        return default

    def transition_start(self):
        suscrip = Pool().get('suscripcion.suscripcion')
        if (suscrip(Transaction().context.get('active_id'))!=None):
            return 'start_view'
        else:
            return 'start_view'

    def transition_trans_seleccion_fecha(self):
        if self.start_view.apariciones!='1':
            repeticion = self.start_view.cant_apariciones*Decimal(self.start_view.apariciones)
            fecha = self.start_view.inicio
            for i in range(repeticion):
                self.crear_diarios(fecha)
                fecha = fecha +timedelta(days=1)
            return 'finalizar'
        else:
            return 'seleccion_fechas'

    def transition_final_seleccion(self):
        self.crear_diarios(self.seleccion_fechas.fecha)
        if self.seleccion_fechas.cant_apariciones<self.start_view.cant_apariciones:
            return 'seleccion_fechas'
        else:
            return 'finalizar'


#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#-------------------------------<WIZARD>---------------------------------------
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------


class SeleccionFechasPagar(ModelView):
    'SeleccionFechasPagar'
    __name__ = 'suscripcion.seleccion_fechas_pagar'
    fecha_desde = fields.Date('DESDE', required=True)
    fecha_hasta = fields.Date('HASTA', required=True)


class WizardPagar(Wizard):
    'WizardSuscripcion'
    __name__ = 'suscripcion.wizard_pagar'
    #-----------------------------------------INICIO-----------------------------------------#
    start_view = StateView('suscripcion.seleccion_fechas_pagar',
                      'suscripcion.seleccion_fechas_pagar_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Siguiente', 'final_seleccion', 'tryton-go-next', default=True)])

    #-----------------------------------------FIN-----------------------------------------#
    finalizar = StateView('suscripcion.finalizar',
                  'suscripcion.finalizar_pagar_form',
                  [Button('Finalizar', 'end', 'tryton-ok', default=True)])

    start = StateTransition()
    final_seleccion = StateTransition()

    def esta_pagada(self, suscrip):
        esta_entregadas = True
        ediciones = suscrip.ediciones
        for e in ediciones:
            if e.state !='pagada' :
                esta_entregadas = False
        if esta_entregadas:
            suscrip.state = 'concretada'
            suscrip.save()


    def default_start_view(self,fields):
        default = {}
        suscrip = Pool().get('suscripcion.suscripcion')
        actual = suscrip(Transaction().context.get('active_id'))
        if actual.fecha_abonada != None:
            default['fecha_desde']=actual.fecha_abonada
        return default

    def transition_start(self):
        return 'start_view'

    def transition_final_seleccion(self):
        suscrip = Pool().get('suscripcion.suscripcion')
        actual = suscrip(Transaction().context.get('active_id'))
        ediciones = actual.ediciones
        cant = 0
        text = 'Fechas Entregadas:\n'
        for e in ediciones:
            if(self.start_view.fecha_desde <= e.fecha) and (e.fecha <= self.start_view.fecha_hasta):
                if e.state == 'entregado':
                    cant = cant + 1
                    e.state = 'pagada'
                    e.save()
                    actual.fecha_abonada = e.fecha
                    text += ' - '+ str(e.fecha)
        text += ' - '
        actual.save()
        crear_factura(actual,cant,text)
        self.esta_pagada(actual)
        return 'finalizar'
