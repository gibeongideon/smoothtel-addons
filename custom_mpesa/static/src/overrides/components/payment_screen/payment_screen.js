/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { rpc, RPCError } from "@web/core/network/rpc";

patch(PaymentScreen.prototype, {

    addNewPaymentLine(paymentMethod) {
        const order = this.pos.get_order();
        const res = super.addNewPaymentLine(...arguments);
        if (paymentMethod.use_payment_terminal === "mpesa") {
            rpc("/web/dataset/call_kw/", {
                model: "res.users",
                method: "search",
                args: [
                    []
                ],
                kwargs: {},
            }).then(() => {
                console.log("MPesa Payment Selected : POS Available Online");
            }).catch(error => {
                if (!(error instanceof RPCError)) {
                    console.log("Offline");
                    this.deletePaymentLine(this.selectedPaymentLine.cid);
                    this.dialog.add(AlertDialog, {
                        title: _t("Error"),
                        body: _t("POS offline, transaction cannot be processed!"),
                    });
                    return false;
                }
            });
        }

        if (res && paymentMethod.mpesa_payment_provider_id) {
            order.selected_paymentline.mpesa_swipe_pending = true;
        }
    },
});
