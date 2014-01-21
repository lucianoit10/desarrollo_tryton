from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pyson import If, Eval, Bool, Id, Not
from trytond.transaction import Transaction
from trytond.tools import reduce_ids
from trytond.pool import Pool
from sql.aggregate import Count, Sum
from sql.conditionals import Coalesce
from decimal import Decimal


_STATES = {
    'readonly': Eval('state') != 'draft',
}
_DEPENDS = ['state']


_ZERO = Decimal('0.0')

class Invoice(Workflow, ModelSQL, ModelView):
    'Invoice'
    __name__ = 'account.invoice'
    _order_name = 'number'
    number = fields.Char('Number', size=None, readonly=True, select=True)
    
    untaxed_amount = fields.Function(fields.Numeric('Untaxed',
            digits=(16, Eval('currency_digits', 2)), states= {'invisible': Not(Bool(Eval('es_a')))},            
            depends=['currency_digits','party']),
        'get_amount', searcher='search_untaxed_amount')
    tax_amount = fields.Function(fields.Numeric('Tax', digits=(16,
            Eval('currency_digits', 2)), states= {'invisible': Not(Bool(Eval('es_a')))}, 
            depends=['currency_digits','party']),
        'get_amount', searcher='search_tax_amount')
    es_a = fields.Boolean('A', on_change_with=['party'])
    

    def on_change_with_es_a(self):
        try:
            if self.party.facturacion =='a':
                return True
            else:
                return False 
        except:
            return False


    @classmethod
    def search_untaxed_amount(cls, name, clause):
        return super(Invoice,cls).search_untaxed_amount(invoices, name, clause)

    @classmethod
    def search_tax_amount(cls, name, clause):
        return super(Invoice,cls).search_tax_amount(name, clause)

    @classmethod
    def get_amount(cls, invoices, names):
        pool = Pool()
        InvoiceTax = pool.get('account.invoice.tax')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        cursor = Transaction().cursor

        untaxed_amount = dict((i.id, _ZERO) for i in invoices)
        tax_amount = dict((i.id, _ZERO) for i in invoices)
        total_amount = dict((i.id, _ZERO) for i in invoices)

        type_name = cls.tax_amount._field.sql_type().base
        in_max = cursor.IN_MAX
        tax = InvoiceTax.__table__()
        for i in range(0, len(invoices), in_max):
            sub_ids = [i.id for i in invoices[i:i + in_max]]
            red_sql = reduce_ids(tax.invoice, sub_ids)
            cursor.execute(*tax.select(tax.invoice,
                    Coalesce(Sum(tax.amount), 0).as_(type_name),
                    where=red_sql,
                    group_by=tax.invoice))
            for invoice_id, sum_ in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(sum_, Decimal):
                    sum_ = Decimal(str(sum_))
                tax_amount[invoice_id] = sum_

        invoices_move = []
        invoices_no_move = []
        for invoice in invoices:
            if invoice.move:
                invoices_move.append(invoice)
            else:
                invoices_no_move.append(invoice)

        type_name = cls.total_amount._field.sql_type().base
        invoice = cls.__table__()
        move = Move.__table__()
        line = MoveLine.__table__()
        for i in range(0, len(invoices_move), in_max):
            sub_ids = [i.id for i in invoices_move[i:i + in_max]]
            red_sql = reduce_ids(invoice.id, sub_ids)
            cursor.execute(*invoice.join(move,
                    condition=invoice.move == move.id
                    ).join(line, condition=move.id == line.move
                    ).select(invoice.id,
                    Coalesce(Sum(line.debit - line.credit), 0).cast(type_name),
                    where=(invoice.account == line.account) & red_sql,
                    group_by=invoice.id))
            for invoice_id, sum_ in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(sum_, Decimal):
                    sum_ = Decimal(str(sum_))
                total_amount[invoice_id] = sum_

        for invoice in invoices_move:
            if invoice.type in ('in_invoice', 'out_credit_note'):
                total_amount[invoice.id] *= -1
            untaxed_amount[invoice.id] = (
                total_amount[invoice.id] - tax_amount[invoice.id])

        for invoice in invoices_no_move:
            untaxed_amount[invoice.id] = sum(
                (line.amount for line in invoice.lines
                    if line.type == 'line'), _ZERO)
            total_amount[invoice.id] = (
                untaxed_amount[invoice.id] + tax_amount[invoice.id])
        if not(invoice.es_a):
            result = {
                'untaxed_amount': untaxed_amount,
                'tax_amount': tax_amount,
                'total_amount': untaxed_amount,
            }
        else:
            result = {
                'untaxed_amount': untaxed_amount,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
            }    
        for key in result.keys():
            if key not in names:
                del result[key]
        return result

class InvoiceLine(ModelSQL, ModelView):
    'Invoice Line'
    __name__ = 'account.invoice.line'
    _rec_name = 'description'

    amount = fields.Function(fields.Numeric('Amount',
            digits=(16, Eval('_parent_invoice', {}).get('currency_digits',
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            on_change_with=['type', 'quantity', 'unit_price',
                '_parent_invoice.currency', 'currency'],
            depends=['type', 'currency_digits']), 'get_amount')

    def get_amount(self, name):
        if self.type == 'line':
            valor = self.on_change_with_amount()
            if not(self.invoice.es_a):
                Tax = Pool().get('account.tax')
                amount_tax = 0
                for tax in self.taxes:
                    amount_tax += Tax(tax)._process_tax(valor)['amount']
                valor += amount_tax
            return valor
        elif self.type == 'subtotal':
            subtotal = _ZERO
            for line2 in self.invoice.lines:
                if line2.type == 'line':
                    subtotal += line2.invoice.currency.round(
                        Decimal(str(line2.quantity)) * line2.unit_price)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    subtotal = _ZERO
            return subtotal
        else:
            return _ZERO