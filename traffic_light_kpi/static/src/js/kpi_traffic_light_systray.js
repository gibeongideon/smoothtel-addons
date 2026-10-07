/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

const STATUS_LABELS = {
    blue: "Outstanding",
    green: "Performing Well",
    yellow: "Moderate Performance",
    red: "Needs Attention",
    grey: "Not Evaluated",
};

const RATING_LABELS = {
    1: "1 – Unacceptable",
    2: "2 – Needs Improvement",
    3: "3 – Meets Expectations",
    4: "4 – Exceeds Expectations",
    5: "5 – Outstanding",
};

/**
 * KPI Traffic Light Systray Component
 *
 * Displays a coloured dot (Blue/Green/Yellow/Red) in the top navigation bar.
 * Red and Yellow blink via CSS animation.
 * Clicking opens a popup panel with KPI details.
 */
class KpiTrafficLightSystray extends Component {
    static template = "traffic_light_kpi.KpiTrafficLightSystray";
    static components = { Dropdown, DropdownItem };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            status: "grey",
            rating: false,
            overall_percentage: 0,
            kpis: [],
            loading: true,
            panelOpen: false,
        });

        this._refreshInterval = null;

        onWillStart(async () => {
            await this._fetchStatus();
        });

        onMounted(() => {
            // Refresh every 5 minutes
            this._refreshInterval = setInterval(() => this._fetchStatus(), 5 * 60 * 1000);
            // Also refresh on window focus (user returns to tab)
            this._onFocus = () => this._fetchStatus();
            window.addEventListener("focus", this._onFocus);
        });

        onWillUnmount(() => {
            if (this._refreshInterval) {
                clearInterval(this._refreshInterval);
            }
            window.removeEventListener("focus", this._onFocus);
        });
    }

    async _fetchStatus() {
        try {
            const result = await this.orm.call(
                "kpi.result",
                "get_my_kpi_summary",
                [],
                {}
            );
            this.state.status = result.overall_status || "grey";
            this.state.rating = result.overall_rating || false;
            this.state.overall_percentage = result.overall_percentage || 0;
            this.state.kpis = result.kpis || [];
            this.state.loading = false;
        } catch (e) {
            // Silently fail — do not block user on systray error
            this.state.status = "grey";
            this.state.loading = false;
        }
    }

    get statusLabel() {
        return RATING_LABELS[this.state.rating] || STATUS_LABELS[this.state.status] || "Unknown";
    }

    async openDashboard() {
        const action = await this.orm.call(
            "kpi.result",
            "action_open_dashboard_from_systray",
            [],
            {}
        );
        this.action.doAction(action);
    }
}

// Register in the systray
registry.category("systray").add(
    "traffic_light_kpi.KpiTrafficLightSystray",
    {
        Component: KpiTrafficLightSystray,
        sequence: 5,  // Show near the right side, before notifications
    }
);

export { KpiTrafficLightSystray };
