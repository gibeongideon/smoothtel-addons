/** @odoo-module */

import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { PaymentMpesa } from '@custom_mpesa/js/mpesa_payment';

register_payment_method('mpesa', PaymentMpesa);