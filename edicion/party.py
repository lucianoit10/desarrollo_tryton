from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Bool, Eval, And, Not, Get
from trytond.pool import Pool

STATES = {
    'readonly': ~Eval('active', True),
}
DEPENDS = ['active','dni','usa_dni','vat_number']



class Party(ModelSQL, ModelView):
    "Party"
    __name__ = 'party.party'
    name = fields.Char('Name', required=True, select=True, states=STATES, depends=DEPENDS)
    facturacion = fields.Selection([('a','Factura A'),('b','Factura B')],'TIPO DE FACTURACION', required=True)
    dni = fields.Char('DNI', 
        states={
            'readonly': Not(Bool(Eval('usa_dni'))),
            'required': Bool(Eval('usa_dni')),
            },
        depends=['active', 'usa_dni'])
    usa_dni = fields.Boolean('USA DNI', select=False)
    vat_number = fields.Char('VAT Number', help="Value Added Tax number",
        states={
            'readonly': ~Eval('active', True),
            'required': And(Bool(Eval('vat_country')),Not(Bool(Eval('usa_dni')))),
            },
        depends=['active', 'vat_country'])

    @classmethod
    def default_facturacion(self):
        return 'b'


    def get_rec_name(self, name):
        if self.usa_dni:
            if self.dni:
                return self.name +' [' + self.dni + ']'
        else:
            if self.vat_number:
                return self.name + ' [' + self.vat_number + ']'
        return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        ids = map(int, cls.search([('dni',) + tuple(clause[1:])], order=[]))
        if ids:
            ids += map(int,
                cls.search([('name',) + tuple(clause[1:])], order=[]))
            return [('id', 'in', ids)]
        ids = map(int, cls.search([('vat_number',) + tuple(clause[1:])], order=[]))
        if ids:
            ids += map(int,
                cls.search([('name',) + tuple(clause[1:])], order=[]))
            return [('id', 'in', ids)]
        return [('name',) + tuple(clause[1:])]