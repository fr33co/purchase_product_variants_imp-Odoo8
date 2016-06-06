# -*- encoding: utf-8 -*-
##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses/.
#
##############################################################################

from openerp import models, fields, api, exceptions, _
from openerp.addons import decimal_precision as dp


class ProductAttributeValuePurchaseLine(models.Model):
	_inherit = 'purchase.order.line.attribute'

	@api.one
	@api.depends('value', 'purchase_line.product_template', 'size_x','size_y','size_z')
	def _get_qty(self):
		mp_qty = 1
		for mpqty in self.value.price_ids:
			print mpqty
			if mpqty.product_tmpl_id.id == self.purchase_line.product_template.id:
				mp_qty = mpqty.raw_qty
		self.mp_qty = 1 * (self.size_x or 1.0) * (self.size_y or 1.0) * (self.size_z)

	@api.one
	@api.depends('value', 'purchase_line.product_template', 'mp_qty')
	def _get_price_extra(self):
		price_extra = 0.0
		for price in self.value.price_ids:
			if price.product_tmpl_id.id == self.purchase_line.product_template.id:
				price_extra = price.price_extra
				if price_extra == 0:
					if price.value_id.id!=66 and price.value_id.id!=67:
						self.price_extra = self.purchase_line.product_template.standard_price * self.mp_qty
				else:
					self.price_extra = price_extra * self.mp_qty

	@api.one
	@api.depends('attribute',
                 'purchase_line.product_template',
                 'purchase_line.product_template.attribute_line_ids')
	def _get_possible_attribute_values(self):
		attr_values = self.env['product.attribute.value']
		for attr_line in \
        	self.purchase_line.product_template.attribute_line_ids:
			if attr_line.attribute_id.id == self.attribute.id:
				attr_values |= attr_line.value_ids
		self.possible_values = attr_values.sorted()

	price_extra = fields.Float(
		compute='_get_price_extra', readonly=False, string='Precio',
		digits=dp.get_precision('Product Price'),
		help="")
	mp_qty = fields.Float(compute='_get_qty', readonly=False, string='Cantidad', help="Cantidad de materia prima a Utilizar")
	size_x = fields.Float(digits=(16,2), string='Largo')
	size_y = fields.Float(digits=(16,2), string='Ancho/Alto')
	size_z = fields.Float(digits=(16,2), string='qty')


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_attributes_count = fields.Integer(compute="_get_product_attributes_count")
    order_state = fields.Selection(related='order_id.state', readonly=False)
    product_cantidad_total= fields.Float('Cantidad Total M2 por pieza', readonly=False,default=0.0)
    cantidad_total = fields.Float('Cantidad Total M2 de la Orden', readonly=False, help="Cantidad Total de materia prima a Utilizar",default=0.0)

    @api.one
    @api.depends('product_attributes')
    def _get_product_attributes_count(self):
        self.product_attributes_count = len(self.product_attributes)


    def _get_product_description(self, template, product, product_attributes):
        name = product and product.name or template.name
        group = self.env.ref(
            'sale_product_variants.group_product_variant_extended_description')
        extended = group in self.env.user.groups_id
        if not product_attributes and product:
            product_attributes = product.attribute_value_ids
        if extended:
            description = " ".join(self.product_attributes.mapped(
                lambda x: ("%s: Largo %s X Ancho %s" % (x.attribute.name,x.size_x or 0.0, x.size_y or 0.0)) if x.size_y>0 else ""))
        else:
            description = ", ".join(product_attributes.mapped('name'))
        if not description:
            return name
        return ("%s\n%s" if extended else "%s (%s)") % (name, description)

    @api.multi
    def product_id_change(
            self, pricelist, product_id, qty=0, uom=False, qty_uos=0,
            uos=False, name='', partner_id=False, lang=False, update_tax=True,
            date_order=False, packaging=False, fiscal_position=False,
            flag=False):
        product_obj = self.env['product.product']
        res = super(PurchaseOrderLine, self).product_id_change(
            pricelist, product_id, qty=qty, uom=uom, qty_uos=qty_uos, uos=uos,
            name=name, partner_id=partner_id, lang=lang, update_tax=update_tax,
            date_order=date_order, packaging=packaging,
            fiscal_position=fiscal_position, flag=flag)
        if product_id:
            product = product_obj.browse(product_id)
            res['value']['product_attributes'] = (
                product._get_product_attributes_values_dict())
            res['value']['name'] = self._get_product_description(
                product.product_tmpl_id, product, product.attribute_value_ids)
        return res

    @api.multi
    def onchange_product_id(
            self, pricelist_id, product_id, qty, uom_id, partner_id,
            date_order=False, fiscal_position_id=False, date_planned=False,
            name=False, price_unit=False, state='draft'):
        res = super(PurchaseOrderLine, self).onchange_product_id(
            pricelist_id, product_id, qty, uom_id, partner_id,
            date_order=date_order, fiscal_position_id=fiscal_position_id,
            date_planned=date_planned, name=name, price_unit=price_unit,
            state=state)
        if product_id:
            product_obj = self.env['product.product']
            product = product_obj.browse(product_id)
            attributes = [(0, 0, x) for x in
                          product._get_product_attributes_values_dict()]
            res['value'].update(
                {'product_attributes': attributes,
                 'product_template': product.product_tmpl_id.id})
        return res

    @api.multi
    @api.onchange('product_template')
    def onchange_product_template(self):
        self.ensure_one()
        self.name = self.product_template.name
        if not self.product_template.attribute_line_ids:
            self.product_id = (
                self.product_template.product_variant_ids and
                self.product_template.product_variant_ids[0])
        else:
            self.product_id = False
            self.product_uom = self.product_template.uom_id
            self.product_uos = self.product_template.uos_id
            self.price_unit = self.order_id.pricelist_id.with_context(
                {'uom': self.product_uom.id,
                 'date': self.order_id.date_order}).template_price_get(
                self.product_template.id or 1.0,
                self.order_id.partner_id.id)[self.order_id.pricelist_id.id]
        self.product_attributes = (
            self.product_template._get_product_attributes_dict())
        # Update taxes
        fpos = self.order_id.fiscal_position
        if not fpos:
            fpos = self.order_id.partner_id.property_account_position
        self.tax_id = fpos.map_tax(self.product_template.taxes_id)

    @api.one
    @api.onchange('product_attributes')
    def onchange_product_attributes(self):
		if not self.product_id:
			self.name = self._get_product_description(
            	self.product_template, False,
            	self.product_attributes.mapped('value'))
		if self.product_template:
			self.update_price_unit()
			self.update_uom_qty()

    @api.multi
    def action_duplicate(self):
        self.ensure_one()
        self.copy()
        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'purchase.order',
            'res_id': self.order_id.id,
            'type': 'ir.actions.act_window',
        }

 	@api.one
	def _check_line_confirmability(self):
		if any(not bool(line.value) for line in self.product_attributes):
			raise exceptions.Warning(
                _("You can not confirm before configuring all attribute "
                  "values."))

    @api.multi
    def button_confirm(self):
        product_obj = self.env['product.product']
        for line in self:
            if not line.product_id:
                line._check_line_confirmability()
                attr_values = line.product_attributes.mapped('value')
                domain = [('product_tmpl_id', '=', line.product_template.id)]
                for attr_value in attr_values:
                    domain.append(('attribute_value_ids', '=', attr_value.id))
                products = product_obj.search(domain)
                # Filter the product with the exact number of attributes values
                product = False
                for prod in products:
                    if len(prod.attribute_value_ids) == len(attr_values):
                        product = prod
                        break
                if not product:
                    product = product_obj.create(
                        {'product_tmpl_id': line.product_template.id,
                         'attribute_value_ids': [(6, 0, attr_values.ids)]})
                line.write({'product_id': product.id})
        super(PurchaseOrderLine, self).button_confirm()

    @api.multi
    def update_price_unit(self):
        self.ensure_one()
        if not self.product_id:
            price_extra = 0.0
            for attr_line in self.product_attributes:
                price_extra += attr_line.price_extra
            self.price_unit = self.order_id.pricelist_id.with_context(
                {
                    'uom': self.product_uom.id,
                    'date': self.order_id.date_order,
                    'price_extra': price_extra,
                }).template_price_get(
                self.product_template.id or 1.0,
                self.order_id.partner_id.id)[self.order_id.pricelist_id.id]

    @api.multi
    def update_uom_qty(self):
        self.ensure_one()
        if not self.product_id:
            self.product_cantidad_total = 0.0
            for attr_line in self.product_attributes:
                if attr_line.size_y > 0:
                    self.product_cantidad_total += attr_line.mp_qty


	@api.onchange('product_qty','product_cantidad_total')
	def on_change_qty(self):
		self.cantidad_total = self.product_qty * self.product_cantidad_total
