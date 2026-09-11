/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentForm } from "@payment/js/payment_form";
import { _t } from "@web/core/l10n/translation";

patch(PaymentForm.prototype, {
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== "mpesa_online") {
            return super._prepareInlineForm(...arguments);
        }
        if (flow === "token") {
            return;
        }
        this._setPaymentFlow("direct");
    },

    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== "mpesa_online") {
            return super._processDirectFlow(...arguments);
        }

        const mpesaNumber = document.getElementById("mpesa_phone_number");
        const phoneNumber = mpesaNumber?.value || "";
        if (!/^\d{9}$/.test(phoneNumber)) {
            this._enableButton();
            this._displayErrorDialog(
                _t("Invalid Details"),
                _t("Please enter a valid 9-digit phone number.")
            );
            return;
        }

        await this.rpc("/payment/mpesa_online/return", {
            phoneNumber,
            reference: processingValues.reference,
        });
        window.location = "/payment/status";
    },
});
