from trytond.pool import Pool
from trytond.pyson import Eval, Or, Bool, Equal, Not
from trytond.modules.company import CompanyReport
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button, StateAction
from decimal import Decimal
from datetime import timedelta
import datetime
from trytond.transaction import Transaction


tyc_cat_diario =[
                    ('Aviso Comun', '1- Aviso Comun'),
                    ('Aviso Especial', '2- Aviso Especial'),
                    ('Clasificado', '3- Clasificado Destacado'),
                    ('Funebre', '4- Funebre Destacado'),
                ]

aviso_ubicacion=[
                    ('0', '1- Libre'),
                    ('1', '2- Pagina Par'),
                    ('2', '3- Pagina Impar'),
                    ('3', '4- Tapa'),
                    ('4', '5- Central'),
                    ('5', '6- Contratapa'),
                    ('6', '7- Suplemento'),
                 ]

select_apariciones=    [
                           ('1', '1- Dia/s especifico/s'),
                           ('7', '2- Semana/s(7 dias)'),
                           ('30', '3- Mes/es (30 dias)'),
                           ('365', '4- ANUAL(365 dias)'),
                       ]

tipo_bonificacion= [
                       ('$', '$- Fijo'),
                       ('p', '%- Porcentual'),
                   ]

lista_origen = [
                ('0','Ninguno'),
                ('1','Composicion'),
                ('2','E-mail'),
                ('3','Scanner'),
                ('4','Sigue'),
                ('5','Sin cargo'),
                ]

class Edicion(ModelSQL,ModelView):
    'Edicion'
    __name__ = 'edicion.edicion'
    _rec_name = 'fecha'
    fecha = fields.Date('FECHA', readonly=False, required=True)
    publicacionesDiario = fields.One2Many('edicion.publicacion_diario', 'edicion', 'DIARIO')
    publicacionesRadio = fields.One2Many('edicion.publicacion_radio', 'edicion','RADIO')
    publicacionesDigital = fields.Many2Many('edicion.edicion_publicacion_digital', 'edicion_id', 'digital_id','DIGITAL')

    @classmethod
    def __setup__(cls):
        super(Edicion, cls).__setup__()
        cls._sql_constraints = [
            ('edicion_fecha', 'UNIQUE(fecha)',
                'no se pueden crear 2 ediciones con la misma fecha'),
            ]

    def get_rec_name(self, name):
        return self.fecha.strftime('%d/%m/%Y')

class EdicionPublicacionDigital(ModelSQL):
    'EdicionPublicacionDigital'
    __name__ = 'edicion.edicion_publicacion_digital'

    edicion_id = fields.Many2One('edicion.edicion', 'Edicion')
    digital_id = fields.Many2One('edicion.publicacion_digital', 'Digital')




#PUBLICACIONES
class PublicacionDiario(Workflow,ModelSQL,ModelView):
    'PublicacionDiario'
    __name__ = 'edicion.publicacion_diario'
    termino_pago = fields.Many2One('account.invoice.payment_term','TERMINO PAGO')
    fecha = fields.Function (fields.Date('FECHA'), 'get_fecha')
    linea = fields.Many2One('sale.line', 'LINEA', ondelete='CASCADE')
    cliente = fields.Many2One('party.party', 'CLIENTE',
        states={'readonly': Or(Or((Or((Eval('state') == 'cancelada'),(Eval('state') == 'publicada'))),(Eval('state') == 'reprogramar')),Equal(Eval('venta_cm'),'si'))},
                 depends=['state'], required=True)
    categoria = fields.Function(fields.Many2One('product.category', 'CATEGORIA'), 'get_categoria')
    producto = fields.Many2One('product.product', 'PRODUCTO',domain=[('category.parent', '=', 'Diario')],
        states={'readonly': Or(Or((Or((Eval('state') == 'cancelada'),(Eval('state') == 'publicada'))),(Eval('state') == 'reprogramar')),Equal(Eval('venta_cm'),'si'))}, depends=['state'], required=True)
    ubicacion = fields.Char('UBICACION', depends=['state'],
        states={'readonly': Or(Or((Or((Eval('state') == 'cancelada'),(Eval('state') == 'publicada'))),(Eval('state') == 'reprogramar')),Equal(Eval('venta_cm'),'si'))}, required=True)
    medidas = fields.Char('MEDIDAS', depends=['state'],
        states={'readonly': Or((Or((Eval('state') == 'cancelada'),(Eval('state') == 'publicada'))),(Eval('state') == 'reprogramar'))}, required=True)
    edicion = fields.Many2One('edicion.edicion', 'EDICION',
    states={'readonly': Or(Or((Eval('state') == 'cancelada'),(Eval('state') == 'publicada')),Equal(Eval('venta_cm'),'si')),
            'required':Equal(Eval('venta_cm'),'no')},depends=['state'])
    descrip = fields.Text('DESCRIPCION', depends=['state'],
        states={'readonly': Or((Or((Eval('state') == 'cancelada'),(Eval('state') == 'publicada'))),(Eval('state') == 'reprogramar'))})
    state = fields.Selection([  ('reprogramar','reprogramar'),
                                ('pendiente','pendiente'),
                                ('publicada','publicada'),
                                ('cancelada','cancelada')],'State', readonly=True, required=True)
    venta_cm = fields.Char('VENTA POR CM',size = 2,readonly=True)
    viene_de_cm = fields.Boolean("CM")
    en_guia = fields.Boolean('IMPRESO EN GUIA ANTERIOR', select=False)
    impresion = fields.Selection([  ('pendiente','Pendiente'),
                                    ('imprimiendo','Imprimiendo'),
                                    ('impreso','Impreso')], 'Esta Impreso', on_change_with=['en_guia'])
    venta = fields.Many2One('sale.sale', 'VENTA')
    origen = fields.Selection(lista_origen,'Origen')

    @classmethod
    def default_state(self):
        return 'pendiente'

    @classmethod
    def default_impresion(self):
        return 'pendiente'

    def on_change_with_impresion(self):
        if self.en_guia:
            return 'impreso'
        else:
            return 'pendiente'

    @classmethod
    def default_venta_cm(self):
        return 'no'

    @classmethod
    def default_origen(self):
        return '0'


    @classmethod
    def __setup__(cls):
        super(PublicacionDiario, cls).__setup__()
        cls._transitions |= set((
                ('reprogramar', 'pendiente'),
                ('reprogramar', 'cancelada'),
                ('pendiente', 'reprogramar'),
                ('pendiente', 'publicada'),
                ('pendiente', 'cancelada'),
                ))
        cls._buttons.update({
                'reprogramar': {
                    'invisible': Or(Eval('state').in_(['reprogramar','publicada', 'cancelada']),Equal(Eval('venta_cm'),'si')),
                    'icon': 'tryton-clear',
                    },
                'pendiente': {
                    'invisible': Or(~Eval('state').in_(['reprogramar']),Equal(Eval('venta_cm'),'si')),
                    'icon': 'tryton-go-next',
                    },
                'publicada': {
                    'invisible': Or(Eval('state') != 'pendiente',Equal(Eval('venta_cm'),'si')),
                    'icon': 'tryton-ok',
                    },
                'cancelada': {
                    'invisible': Or(Eval('state').in_(['publicada', 'cancelada']),Equal(Eval('venta_cm'),'si')),
                    'icon': 'tryton-cancel',
                    },
                'presupuestar': {
                    'invisible': Equal(Eval('venta_cm'),'no'),
                    'icon': 'tryton-ok',
                    },
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('reprogramar')
    def reprogramar(cls, publ):
        pass


    @classmethod
    @ModelView.button
    @Workflow.transition('pendiente')
    def pendiente(cls, publ):
        pass

    @classmethod
    def crear_factura(cls,publ):
        date = Pool().get('ir.date')
        sale = Pool().get('sale.sale')

        #calculo del invoice address
        invoice_address = publ.cliente.address_get(type='invoice')
        shipment_address = publ.cliente.address_get(type='delivery')
        nueva = sale.create([{
                    'party':publ.cliente,
                    'payment_term': publ.termino_pago,
                    'invoice_address' : invoice_address,
                    'shipment_address' : shipment_address,
                    'sale_date' :date.today(),
                    }])[0]
        nueva.save()

        publ.linea.sale = nueva
        publ.linea.save()
        nueva.state = 'processing'
        nueva.save()
        #crea factura
        nueva.create_invoice('out_invoice')
        nueva.create_invoice('out_credit_note')
        nueva.set_invoice_state()
        nueva.create_shipment('out')
        nueva.create_shipment('return')
        nueva.set_shipment_state()


    @classmethod
    @ModelView.button
    @Workflow.transition('publicada')
    def publicada(cls, publ):
        for p in publ:
            if(p.linea != None):
                if(p.viene_de_cm):
                    linea = Pool().get('sale.line')
                    cantidad = Decimal(p.medidas.split(' ')[-1])
                    nueva_linea = linea.create([{
                                'sale':p.venta,
                                'product': p.producto,
                                'sequence':'0',
                                'type':'line',
                                'unit': p.producto.default_uom,
                                'unit_price':0,
                                'quantity':cantidad,
                                'description':str(p.descrip)
                                }])[0]
                    nueva_linea.save()

                    p.linea = nueva_linea
                    p.linea.save()
                else:
                    cls.crear_factura(p)
            else:
                pass

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelada')
    def cancelada(cls, publ):
        line = Pool().get('sale.line')
        for p in publ:
            try:
                linea = p.linea
                p.linea=None
                p.save()
                line.delete([linea])
            except:
                pass

    @classmethod
    @ModelView.button_action('edicion.presupuestacion_centimetros')
    def presupuestar(cls, publ):
        pass

    def get_fecha(self, name):
        if self.edicion !=None:
            return self.edicion.fecha
        else:
            return None

    def get_categoria(self, name):
        return self.producto.category.id

class PublicacionRadio(ModelSQL,ModelView):
    'PublicacionRadio'
    __name__ = 'edicion.publicacion_radio'
    fecha = fields.Function (fields.Date('FECHA'), 'get_fecha')
    linea = fields.Many2One('sale.line', 'LINEA', ondelete='CASCADE')
    cliente = fields.Many2One('party.party', 'CLIENTE', required=True)
    categoria = fields.Selection([('Costo Provincial','1- Costo Provincial'),('Costo Nacional','2- Costo Nacional'),('Costo Oficial','3- Costo Oficial')],'CATEGORIA',required=True)
    producto = fields.Many2One('product.product', 'PRODUCTO',domain=[('category', '=', Eval('categoria')),('category.parent','=','Radio')], required=True)
    edicion = fields.Many2One('edicion.edicion', 'EDICION', required = True)
    descrip = fields.Text('DESCRIPCION')

    def get_fecha(self, name):
        return self.edicion.fecha



class PublicacionDigital(ModelSQL,ModelView):
    'PublicacionDigital'
    __name__ = 'edicion.publicacion_digital'
    fecha = fields.Function (fields.Date('FECHA INICIO'), 'get_fecha')
    linea = fields.Many2One('sale.line', 'LINEA', ondelete='CASCADE')
    cliente = fields.Many2One('party.party', 'CLIENTE', required=True)
    categoria = fields.Selection([('Costo Provincial','1- Costo Provincial'),('Costo Nacional','2- Costo Nacional'),('Costo Oficial','3- Costo Oficial')],'CATEGORIA',required=True)
    producto = fields.Many2One('product.product', 'PRODUCTO',domain=[('category', '=', Eval('categoria')),('category.parent','=','Digital')], required=True)
    edicion = fields.Many2Many('edicion.edicion_publicacion_digital','digital_id','edicion_id','EDICION')
    descrip = fields.Text('DESCRIPCION')

    def get_fecha(self, name):
        try:
            fecha_inicio = self.edicion[0].fecha
            return fecha_inicio
        except:
            return None



#PUBLICACIONES PRESUPUESTADAS
class PublicacionPresupuestadaDiario(ModelSQL,ModelView):
    'PublicacionPresupuestadaDiario'
    __name__ = 'edicion.publicacion_presupuestada_diario'
    fecha = fields.Date('FECHA')
    cliente = fields.Many2One('party.party', 'CLIENTE', required=True)
    venta = fields.Many2One('sale.sale', 'VENTA', required=True)
    linea = fields.Many2One('sale.line', 'LINEA', ondelete='CASCADE')
    producto = fields.Many2One('product.product', 'PRODUCTO', required=True)
    ubicacion = fields.Char('UBICACION', required=True)
    medidas = fields.Char('MEDIDAS', required=True)
    descrip = fields.Text('DESCRIPCION', required=True)

class PublicacionPresupuestadaRadio(ModelSQL,ModelView):
    'PublicacionPresupuestadaRadio'
    __name__ = 'edicion.publicacion_presupuestada_radio'
    fecha = fields.Date('FECHA')
    cliente = fields.Many2One('party.party', 'CLIENTE', required=True)
    venta = fields.Many2One('sale.sale', 'VENTA', required=True)
    linea = fields.Many2One('sale.line', 'LINEA', ondelete='CASCADE')
    producto = fields.Many2One('product.product', 'PRODUCTO', required=True)
    descrip = fields.Text('DESCRIPCION', required=True)

class PublicacionPresupuestadaDigital(ModelSQL,ModelView):
    'PublicacionPresupuestadaDigital'
    __name__ = 'edicion.publicacion_presupuestada_digital'
    fecha = fields.Date('FECHA')
    cliente = fields.Many2One('party.party', 'CLIENTE', required=True)
    venta = fields.Many2One('sale.sale', 'VENTA', required=True)
    linea = fields.Many2One('sale.line', 'LINEA', ondelete='CASCADE')
    producto = fields.Many2One('product.product', 'PRODUCTO', required=True)
    descrip = fields.Text('DESCRIPCION', required=True)

class TipoYCategoria(ModelSQL,ModelView):
    'Tipo y Categoria'
    __name__ = 'edicion.tipo_y_categoria.start'
    diario = fields.Char('DIARIO',readonly=True)
    categoriaDiario = fields.Selection(tyc_cat_diario, 'CATEGORIA',required=True)

    @staticmethod
    def default_diario():
        return 'DIARIO'

class Producto(ModelSQL,ModelView):
    'Producto'
    __name__ = 'edicion.producto'
    cat = fields.Char('Categoria Seleccionada', readonly=True)
    producto = fields.Many2One('product.template', 'Productos',domain=[('category', '=', Eval('cat'))], required=True)


class AvisoComun(ModelSQL,ModelView):
    'AvisoComun'
    __name__ = 'edicion.aviso_comun'
    ubicacion = fields.Selection(aviso_ubicacion, 'UBICACION', readonly=False, required=True)
    suplemento = fields.Char('SUPLEMENTO', states={'readonly': (Eval('ubicacion') != '6')})
    cant_centimetros = fields.Numeric('CENTIMETROS', required=True)
    cant_columnas = fields.Numeric('COLUMNAS', required=True)
    apariciones = fields.Selection(select_apariciones, 'APARICIONES',  on_change=['apariciones'], required=True)
    cant_apariciones = fields.Numeric('NRO.', states={'readonly': (Eval('apariciones') == '365')}, required=True)
    inicio = fields.Date('INICIO', states={'readonly': (Eval('apariciones') == '1')}, required=True)
    descripcion = fields.Text('DESCRIPCION',readonly=False)

    def on_change_apariciones(self):
        if self.apariciones == '365':
            v = 1
            return {'cant_apariciones': v}
        return{}


class AvisoEspecial(ModelSQL,ModelView):
    'AvisoEspecial'
    __name__ = 'edicion.aviso_especial'
    ubicacion = fields.Char('UBICACION', size=8, readonly=True)
    cant_centimetros = fields.Char('CENTIMETROS', size=8, readonly=True)
    cant_columnas = fields.Char('COLUMNAS', size=8, readonly=True)
    apariciones = fields.Selection(select_apariciones, 'APARICIONES',  on_change=['apariciones'], required=True)
    cant_apariciones = fields.Numeric('NRO.', states={'readonly': (Eval('apariciones') == '365')}, required=True)
    inicio = fields.Date('INICIO', states={'readonly': (Eval('apariciones') == '1')}, required=True)
    descripcion = fields.Text('DESCRIPCION',readonly=False)

    @staticmethod
    def default_ubicacion():
        return '1- Libre'

    def on_change_apariciones(self):
        if self.apariciones == '365':
            v = 1
            return {'cant_apariciones': v}
        return{}

class FunebreDestacado(ModelSQL,ModelView):
    'FunebreDestacado'
    __name__ = 'edicion.funebre_destacado'
    cant_centimetros = fields.Numeric('CENTIMETROS', readonly=False, required=True)
    cant_columnas = fields.Numeric('COLUMNAS', readonly=False, required=True)
    apariciones = fields.Selection(select_apariciones, 'APARICIONES',  on_change=['apariciones'], required=True)
    cant_apariciones = fields.Numeric('NRO.', states={'readonly': (Eval('apariciones') == '365')}, required=True)
    inicio = fields.Date('INICIO', states={'readonly': (Eval('apariciones') == '1')}, required=True)
    descripcion = fields.Text('DESCRIPCION',readonly=False)

    def on_change_apariciones(self):
        if self.apariciones == '365':
            v = 1
            return {'cant_apariciones': v}
        return{}


class ClasificadoDestacado(ModelSQL,ModelView):
    'ClasificadoDestacado'
    __name__ = 'edicion.clasificado_destacado'
    tipo = fields.Char('TIPO', readonly=True)
    cant_centimetros = fields.Numeric('CENTIMETROS', readonly=False, required=True)
    cant_columnas = fields.Numeric('COLUMNAS',  readonly=False, required=True)
    apariciones = fields.Selection(select_apariciones, 'APARICIONES',  on_change=['apariciones'], required=True)
    cant_apariciones = fields.Numeric('NRO.', states={'readonly': (Eval('apariciones') == '365')}, required=True)
    inicio = fields.Date('INICIO', states={'readonly': (Eval('apariciones') == '1')}, required=True)
    descripcion = fields.Text('DESCRIPCION',readonly=False)

    def on_change_apariciones(self):
        if self.apariciones == '365':
            v = 1
            return {'cant_apariciones': v}
        return{}


class SeleccionFechas(ModelSQL,ModelView):
    'SeleccionFechas'
    __name__ = 'edicion.seleccion_fechas'
    cant_apariciones = fields.Numeric('CANTIDAD DE APARICIONES YA CARGADAS:', readonly=True)
    fecha = fields.Date('FECHA DE LA EDICION O MENCION', required=True)

class Finalizar(ModelView):
    'Finalizar'
    __name__ = 'edicion.finalizar'
    texto = fields.Char('EL PROCESO DE PRESUPUESTACION A TERMINADO CON EXITO', readonly=True)


class PresupuestacionCentimetros(Wizard):
    'PresupuestacionCentimetros'
    __name__ = 'edicion.presupuestacion_centimetros'

    start = StateTransition()
    #-----------------------------------------INICIO-----------------------------------------#
    start_view = StateView('edicion.tipo_y_categoria.start',
                      'edicion.tipo_y_categoria_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Siguiente', 'eleccion_producto', 'tryton-go-next', default=True)])

    ##-----------------------------------------PRODUCTO-----------------------------------------#
    producto = StateView('edicion.producto',
                      'edicion.producto_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Atras', 'volver_start', 'tryton-go-previous'),
                      Button('Siguiente', 'datos_categoria', 'tryton-go-next', default=True)])

    #-----------------------------------------DIARIO-----------------------------------------#
    aviso_comun = StateView('edicion.aviso_comun',
                      'edicion.aviso_comun_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Atras', 'eleccion_producto', 'tryton-go-previous'),
                      Button('Siguiente', 'terminar_aviso_comun', 'tryton-go-next', default=True)])

    aviso_especial = StateView('edicion.aviso_especial',
                      'edicion.aviso_especial_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Atras', 'eleccion_producto', 'tryton-go-previous'),
                      Button('Siguiente', 'terminar_aviso_especial', 'tryton-go-next', default=True)])

    funebre_destacado = StateView('edicion.funebre_destacado',
                      'edicion.funebre_destacado_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Atras', 'eleccion_producto', 'tryton-go-previous'),
                      Button('Siguiente', 'terminar_funebre_destacado', 'tryton-go-next', default=True)])

    clasif_destacado = StateView('edicion.clasificado_destacado',
                      'edicion.clasificado_destacado_form',
                      [Button('Cancelar', 'end', 'tryton-cancel'),
                      Button('Atras', 'eleccion_producto', 'tryton-go-previous'),
                      Button('Siguiente', 'terminar_clasif_destacado', 'tryton-go-next', default=True)])

    edicion_aviso_comun = StateView('edicion.seleccion_fechas',
                      'edicion.seleccion_fechas_form',
                      [Button('Siguiente', 'terminar_edicion_aviso_comun', 'tryton-go-next', default=True)])

    edicion_aviso_especial = StateView('edicion.seleccion_fechas',
                      'edicion.seleccion_fechas_form',
                      [Button('Siguiente', 'terminar_edicion_aviso_especial', 'tryton-go-next', default=True)])

    edicion_funebre_destacado = StateView('edicion.seleccion_fechas',
                      'edicion.seleccion_fechas_form',
                      [Button('Siguiente', 'terminar_edicion_funebre_destacado', 'tryton-go-next', default=True)])

    edicion_clasif_destacado = StateView('edicion.seleccion_fechas',
                      'edicion.seleccion_fechas_form',
                      [Button('Siguiente', 'terminar_edicion_clasif_destacado', 'tryton-go-next', default=True)])

    #-----------------------------------------FIN-----------------------------------------#
    finalizar = StateView('edicion.finalizar',
                  'edicion.finalizar_form',
                  [Button('Finalizar', 'end', 'tryton-ok', default=True)])


    volver_start = StateTransition()
    eleccion_producto = StateTransition()
    datos_categoria = StateTransition()
    #--------------------------------------------------
    terminar_aviso_comun = StateTransition()
    terminar_edicion_aviso_comun = StateTransition()
    #--------------------------------------------------
    terminar_aviso_especial = StateTransition()
    terminar_edicion_aviso_especial = StateTransition()
    #--------------------------------------------------
    terminar_funebre_destacado = StateTransition()
    terminar_edicion_funebre_destacado = StateTransition()
    #--------------------------------------------------
    terminar_clasif_destacado = StateTransition()
    terminar_edicion_clasif_destacado = StateTransition()
    #--------------------------------------------------

    def crear_lineas_venta(self,producto,cantidad,descripcion):
        pub = Pool().get('edicion.publicacion_diario')
        linea = Pool().get('sale.line')
        nueva_linea = linea.create([{
                    'sale':pub(Transaction().context.get('active_id')).linea.sale,
                    'product': producto,
                    'sequence':'0',
                    'type':'line',
                    'unit': producto.default_uom,
                    'unit_price':0,
                    'quantity':cantidad,
                    'description':str(descripcion)
                    }])[0]
        nueva_linea.save()
        return nueva_linea


    def crear_linea_publicacion_diario(self,producto,descripcion,medida,fecha):
        edicion = Pool().get('edicion.edicion')
        publicacion = Pool().get('edicion.publicacion_diario')
        ubicacion = "NO POSEE"
        try:
            split = descripcion.split("\n")[1].split("Ubicacion:")
            ubicacion = split[0] + split[1]
        except:
            pass
        edic = 0
        try:
            edic= edicion(edicion.search([('fecha', '=', fecha)])[0])
        except:
            edic=edicion.create([{
            'fecha':fecha
            }])[0]
            edic.save()
        pub = publicacion.create([{
            'termino_pago':publicacion(Transaction().context.get('active_id')).termino_pago,
            'cliente':publicacion(Transaction().context.get('active_id')).cliente,
            'producto' : producto,
            'descrip' : descripcion,
            'medidas' : medida,
            'ubicacion': ubicacion,
            'edicion' : edic,
            'venta' : publicacion(Transaction().context.get('active_id')).venta,
            'viene_de_cm' : True,
            }])[0]
        pub.save()


    #valores por defecto de los estados de vista

    def default_producto(self,fields):
        default = {}
        default['cat']=str('Diario') + ' / ' + str(self.start_view.categoriaDiario)
        return default

    def default_aviso_comun(self,fields):
        default = {}
        default['ubicacion']='0'
        default['cant_centimetros']=3
        default['cant_columnas']=1
        default['apariciones']='1'
        default['cant_apariciones']=1
        return default

    def default_aviso_especial(self,fields):
        default = {}
        cm=str(self.producto.producto.name).split('x')[-1]
        col=(str(self.producto.producto.name).split('x')[0]).split(' ')[-1]
        default['cant_centimetros']=cm
        default['cant_columnas']=col
        default['apariciones']='1'
        default['cant_apariciones']=1
        return default

    def default_funebre_destacado(self,fields):
        default = {}
        default['cant_centimetros']=3
        default['cant_columnas']=1
        default['apariciones']='1'
        default['cant_apariciones']=1
        return default

    def default_clasif_destacado(self,fields):
        default = {}
        default['tipo']=self.producto.producto.name.split(' ')[0]
        default['cant_centimetros']=3
        default['cant_columnas']=1
        default['apariciones']='1'
        default['cant_apariciones']=1
        return default

    def default_edicion_aviso_comun(self,fields):
        default = {}
        try:
            default['cant_apariciones']=Decimal(self.edicion_aviso_comun.cant_apariciones) +1
        except:
            default['cant_apariciones']=1
        return default

    def default_edicion_aviso_especial(self,fields):
        default = {}
        try:
            default['cant_apariciones']=Decimal(self.edicion_aviso_especial.cant_apariciones) +1
        except:
            default['cant_apariciones']=1
        return default

    def default_edicion_funebre_destacado(self,fields):
        default = {}
        try:
            default['cant_apariciones']=Decimal(self.edicion_funebre_destacado.cant_apariciones) +1
        except:
            default['cant_apariciones']=1
        return default

    def default_edicion_clasif_destacado(self,fields):
        default = {}
        try:
            default['cant_apariciones']=Decimal(self.edicion_clasif_destacado.cant_apariciones) +1
        except:
            default['cant_apariciones']=1
        return default


    @classmethod
    def __setup__(cls):
        super(PresupuestacionCentimetros, cls).__setup__()

        cls._error_messages.update({
            'error_centimetros': 'Insuficiente cantidad de centimetros para el aviso',
            'error_producto' : 'Producto no corresponde a cuenta corriente de centimetros'
            })


    def transition_start(self):
        return 'start_view'

    def transition_volver_start(self):
        return 'start_view'

    def transition_eleccion_producto(self):
        return 'producto'

    def transition_datos_categoria(self):
        if self.start_view.diario:
            if(self.start_view.categoriaDiario == 'Aviso Comun'):
                return 'aviso_comun'
            elif(self.start_view.categoriaDiario == 'Aviso Especial'):
                return 'aviso_especial'
            elif(self.start_view.categoriaDiario == 'Funebre'):
                if(self.producto.producto.default_uom.symbol != 'cm'):
                    self.raise_user_error('error_producto')
                else:
                    return 'funebre_destacado'
            elif(self.start_view.categoriaDiario == 'Clasificado'):
                if(self.producto.producto.default_uom.symbol != 'cm'):
                    self.raise_user_error('error_producto')
                else:
                    return 'clasif_destacado'

    def transition_terminar_aviso_comun(self):
        if self.aviso_comun.apariciones!='1':
            publicacion = Pool().get('edicion.publicacion_diario')
            pub_centimetros = publicacion(Transaction().context.get('active_id'))
            prod = self.producto.producto.products[0]
            cant=self.aviso_comun.cant_centimetros * self.aviso_comun.cant_columnas
            repeticion = self.aviso_comun.cant_apariciones*Decimal(self.aviso_comun.apariciones)
            if ((cant*repeticion)<=Decimal(pub_centimetros.medidas)):
                desc = prod.name +', '+str(self.aviso_comun.cant_centimetros) +' centimetro/s por '+ str(self.aviso_comun.cant_columnas)+' columna/s.\n'
                #ubicacion
                ubic = ''
                if (self.aviso_comun.ubicacion == '6'):
                    ubic = 'Ubicacion: Suplemento - '+ self.aviso_comun.suplemento +'\n'
                elif (self.aviso_comun.ubicacion == '0'):
                    ubic = 'Ubicacion: Libre\n'
                elif (self.aviso_comun.ubicacion == '1'):
                    ubic = 'Ubicacion: Pagina Par\n'
                elif (self.aviso_comun.ubicacion == '2'):
                    ubic = 'Ubicacion: Pagina Impar\n'
                else:
                    if (self.aviso_comun.ubicacion == '3'):
                        ubic = 'Ubicacion: Tapa\n'
                    elif (self.aviso_comun.ubicacion == '4'):
                        ubic = 'Ubicacion: Central\n'
                    else:
                        ubic = 'Ubicacion: Contratapa\n'
                #--------------------------------------------------------
                texto = 'TEXTO:\n'+ self.aviso_comun.descripcion.encode('utf-8')
                desc = desc.encode('utf-8') + ubic + texto
                fecha = self.aviso_comun.inicio
                medida = str(self.aviso_comun.cant_centimetros)+ 'x' + str(self.aviso_comun.cant_columnas) + '= ' + str(cant)
                for i in range(repeticion):
                    self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
                    fecha = fecha +timedelta(days=1)
                #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cant*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
                self.raise_user_error('error_centimetros')
        else:
           return 'edicion_aviso_comun'

    def transition_terminar_edicion_aviso_comun(self):
        publicacion = Pool().get('edicion.publicacion_diario')
        pub_centimetros = publicacion(Transaction().context.get('active_id'))
        prod = self.producto.producto.products[0]
        cant=self.aviso_comun.cant_centimetros * self.aviso_comun.cant_columnas
        repeticion = self.aviso_comun.cant_apariciones*Decimal(self.aviso_comun.apariciones)
        if ((cant*repeticion)<=Decimal(pub_centimetros.medidas)):
            desc = prod.name +', '+str(self.aviso_comun.cant_centimetros) +' centimetro/s por '+ str(self.aviso_comun.cant_columnas)+' columna/s durante '  + str(repeticion) + ' dias.\n'
            #ubicacion
            ubic = ''
            if (self.aviso_comun.ubicacion == '6'):
                ubic = 'Ubicacion: Suplemento - '+ self.aviso_comun.suplemento +'\n'
            elif (self.aviso_comun.ubicacion == '0'):
                ubic = 'Ubicacion: Libre\n'
            elif (self.aviso_comun.ubicacion == '1'):
                ubic = 'Ubicacion: Pagina Par\n'
            elif (self.aviso_comun.ubicacion == '2'):
                ubic = 'Ubicacion: Pagina Impar\n'
            else:
                if (self.aviso_comun.ubicacion == '3'):
                    ubic = 'Ubicacion: Tapa\n'
                elif (self.aviso_comun.ubicacion == '4'):
                    ubic = 'Ubicacion: Central\n'
                else:
                    ubic = 'Ubicacion: Contratapa\n'
            #--------------------------------------------------------
            texto = 'TEXTO:\n' + self.aviso_comun.descripcion.encode('utf-8')
            desc = desc.encode('utf-8') + ubic + texto
            fecha = self.edicion_aviso_comun.fecha
            medida = str(self.aviso_comun.cant_centimetros) + 'x' + str(self.aviso_comun.cant_columnas) + '= ' + str(cant)
            self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
            if self.edicion_aviso_comun.cant_apariciones==self.aviso_comun.cant_apariciones:
                #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cant*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
                return 'edicion_aviso_comun'
        else:
            self.raise_user_error('error_centimetros')


    def transition_terminar_aviso_especial(self):
        if self.aviso_especial.apariciones!='1':
            publicacion = Pool().get('edicion.publicacion_diario')
            pub_centimetros = publicacion(Transaction().context.get('active_id'))
            prod = self.producto.producto.products[0]
            cantidad = Decimal(self.aviso_especial.cant_centimetros) * Decimal(self.aviso_especial.cant_columnas)
            repeticion = self.aviso_especial.cant_apariciones*Decimal(self.aviso_especial.apariciones)
            if ((cantidad*repeticion)<=Decimal(pub_centimetros.medidas)):
                desc = prod.name +', '+str(self.aviso_especial.cant_centimetros) +' centimetro/s por '+ str(self.aviso_especial.cant_columnas)+' columna/s.\n'
                ubic = 'Ubicacion: Libre\n'
                texto = 'TEXTO:\n' + self.aviso_especial.descripcion.encode('utf-8')
                desc = desc.encode('utf-8') + ubic + texto
                #nueva = 0
                fecha = self.aviso_especial.inicio
                medida = str(self.aviso_especial.cant_centimetros) + 'x' + str(self.aviso_especial.cant_columnas) + '= ' + str(cantidad)
                for i in range(repeticion):
                    self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
                    fecha = fecha +timedelta(days=1)
                #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cantidad*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
                self.raise_user_error('error_centimetros')
        else:
           return 'edicion_aviso_especial'

    def transition_terminar_edicion_aviso_especial(self):
        publicacion = Pool().get('edicion.publicacion_diario')
        pub_centimetros = publicacion(Transaction().context.get('active_id'))
        prod = self.producto.producto.products[0]
        repeticion = self.aviso_especial.cant_apariciones*Decimal(self.aviso_especial.apariciones)
        cantidad = Decimal(self.aviso_especial.cant_centimetros) * Decimal(self.aviso_especial.cant_columnas)
        if ((cantidad*repeticion)<=Decimal(pub_centimetros.medidas)):
            desc = prod.name +', '+str(self.aviso_especial.cant_centimetros) +' centimetro/s por '+ str(self.aviso_especial.cant_columnas)+' columna/s.\n'
            ubic = 'Ubicacion: Libre\n'
            texto = 'TEXTO:\n' + self.aviso_especial.descripcion.encode('utf-8')
            desc = desc.encode('utf-8') + ubic + texto
            fecha = self.edicion_aviso_especial.fecha
            medida = str(self.aviso_especial.cant_centimetros) + 'x' + str(self.aviso_especial.cant_columnas) + '= ' + str(cantidad)
            self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
            if self.edicion_aviso_especial.cant_apariciones==self.aviso_especial.cant_apariciones:
                #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cantidad*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
                return 'edicion_aviso_especial'
        else:
            self.raise_user_error('error_centimetros')


    def transition_terminar_funebre_destacado(self):
        if self.funebre_destacado.apariciones!='1':
            publicacion = Pool().get('edicion.publicacion_diario')
            pub_centimetros = publicacion(Transaction().context.get('active_id'))
            prod = self.producto.producto.products[0]
            repeticion = self.funebre_destacado.cant_apariciones*Decimal(self.funebre_destacado.apariciones)
            cantidad = self.funebre_destacado.cant_centimetros * self.funebre_destacado.cant_columnas
            if ((cantidad*repeticion)<=Decimal(pub_centimetros.medidas)):
                desc = prod.name +', '+str(self.funebre_destacado.cant_centimetros) +' centimetro/s por '+ str(self.funebre_destacado.cant_columnas)+' columna/s durante '  + str(repeticion) + ' dias.\n'
                texto = 'TEXTO:\n' + self.funebre_destacado.descripcion.encode('utf-8')
                ubic = 'Ubicacion: Libre\n'
                desc = desc.encode('utf-8') + ubic + texto
                fecha = self.funebre_destacado.inicio
                medida = str(self.funebre_destacado.cant_centimetros) +'x'+ str(self.funebre_destacado.cant_columnas) + '= ' + str(cantidad)
                for i in range(repeticion):
                    self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
                    fecha = fecha +timedelta(days=1)
                #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cantidad*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
                self.raise_user_error('error_centimetros')
        else:
            return 'edicion_funebre_destacado'


    def transition_terminar_edicion_funebre_destacado(self):
        publicacion = Pool().get('edicion.publicacion_diario')
        pub_centimetros = publicacion(Transaction().context.get('active_id'))
        prod = self.producto.producto.products[0]
        repeticion = self.funebre_destacado.cant_apariciones*Decimal(self.funebre_destacado.apariciones)
        cantidad = self.funebre_destacado.cant_centimetros * self.funebre_destacado.cant_columnas
        if ((cantidad*repeticion)<=Decimal(pub_centimetros.medidas)):
            desc = prod.name +', '+str(self.funebre_destacado.cant_centimetros) +' centimetro/s por '+ str(self.funebre_destacado.cant_columnas)+' columna/s durante '  + str(repeticion) + ' dias.\n'
            texto = 'TEXTO:\n' + self.funebre_destacado.descripcion.encode('utf-8')
            ubic = 'Ubicacion: Libre\n'
            desc = desc.encode('utf-8') + ubic + texto
            #nueva = 0
            fecha = self.edicion_funebre_destacado.fecha
            medida = str(self.funebre_destacado.cant_centimetros) +'x'+ str(self.funebre_destacado.cant_columnas) + '= ' + str(cantidad)
            self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
            if self.edicion_funebre_destacado.cant_apariciones==self.funebre_destacado.cant_apariciones:
               #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cantidad*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
                return 'edicion_funebre_destacado'
        else:
            self.raise_user_error('error_centimetros')

    def transition_terminar_clasif_destacado(self):
        if self.clasif_destacado.apariciones!='1':
            publicacion = Pool().get('edicion.publicacion_diario')
            pub_centimetros = publicacion(Transaction().context.get('active_id'))
            prod = self.producto.producto.products[0]
            repeticion = self.clasif_destacado.cant_apariciones*Decimal(self.clasif_destacado.apariciones)
            cantidad = Decimal(self.clasif_destacado.cant_centimetros) * Decimal(self.clasif_destacado.cant_columnas)
            if ((cantidad*repeticion)<=Decimal(pub_centimetros.medidas)):
                desc = prod.name +', '+str(self.clasif_destacado.cant_centimetros) +' centimetro/s por '+ str(self.clasif_destacado.cant_columnas)+' columna/s durante '  + str(repeticion) + ' dias.\n'
                tipo = 'Tipo: ' + self.clasif_destacado.tipo.encode('utf-8')
                texto = 'TEXTO:\n' + self.clasif_destacado.descripcion.encode('utf-8')
                ubic = 'Ubicacion: Libre\n'
                desc = desc.encode('utf-8') + tipo + '\n' + texto
                #nueva = 0
                fecha = self.clasif_destacado.inicio
                medida = str(self.clasif_destacado.cant_centimetros) +'x'+ str(self.clasif_destacado.cant_columnas) + '= ' + str(cantidad)
                for i in range(repeticion):
                    self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
                    fecha = fecha +timedelta(days=1)
                #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cantidad*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
                self.raise_user_error('error_centimetros')
        else:
           return 'edicion_clasif_destacado'

    def transition_terminar_edicion_clasif_destacado(self):
        publicacion = Pool().get('edicion.publicacion_diario')
        pub_centimetros = publicacion(Transaction().context.get('active_id'))
        prod = self.producto.producto.products[0]
        repeticion = self.clasif_destacado.cant_apariciones*Decimal(self.clasif_destacado.apariciones)
        cantidad = Decimal(self.clasif_destacado.cant_centimetros) * Decimal(self.clasif_destacado.cant_columnas)
        if ((cantidad*repeticion)<=Decimal(pub_centimetros.medidas)):
            desc = prod.name +', '+str(self.clasif_destacado.cant_centimetros)+' centimetro/s por '+str(self.clasif_destacado.cant_columnas)+' columna/s durante '  + str(repeticion) + ' dias.\n'
            tipo = 'Tipo: ' + self.clasif_destacado.tipo.encode('utf-8')
            texto = 'TEXTO:\n' + self.clasif_destacado.descripcion.encode('utf-8')
            ubic = 'Ubicacion: Libre\n'
            desc = desc.encode('utf-8') + tipo + '\n' + texto
            #nueva = 0
            fecha = self.edicion_clasif_destacado.fecha
            medida = str(self.clasif_destacado.cant_centimetros) +'x'+ str(self.clasif_destacado.cant_columnas) + '= ' + str(cantidad)
            self.crear_linea_publicacion_diario(prod,desc,medida,fecha)
            if self.edicion_clasif_destacado.cant_apariciones==self.clasif_destacado.cant_apariciones:
                #descuenta cms del nuevo aviso de la cantidad de cms
                pub_centimetros.medidas = str(Decimal(pub_centimetros.medidas)-(cantidad*repeticion))
                pub_centimetros.save()
                return 'finalizar'
            else:
               return 'edicion_clasif_destacado'
        else:
            self.raise_user_error('error_centimetros')
