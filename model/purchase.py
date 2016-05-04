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


class PurchaseOrderLine(models.Model):
	_inherit = 'purchase.order.line'

	product_cantidad_total= fields.Float('Cantidad Total m2', readonly=False, help="Cantidad Total de materia prima a Utilizar",default=0.0)

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
				self.product_template.id, self.product_uom_qty or 1.0,
				self.order_id.partner_id.id)[self.order_id.pricelist_id.id]


class ProductAttributeValuePurchaseLine(models.Model):
	_inherit = 'purchase.order.line.attribute'


	@api.one
	@api.depends('value', 'purchase_line.product_template')
	def _get_price_extra(self):
		price_extra = 0.0
		for price in self.value.price_ids:
			if price.product_tmpl_id.id == self.purchase_line.product_template.id:
				price_extra = price.price_extra

	price_extra = fields.Float(
		compute='_get_price_extra', readonly=False, string='Precio',
		digits=dp.get_precision('Product Price'),
		help="")
	size_x = fields.Float(digits=(16,2), string='Largo')
	size_y = fields.Float(digits=(16,2), string='Ancho/Alto')
	size_z = fields.Float(digits=(16,2), string='qty')
