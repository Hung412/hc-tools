import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { formatInteger } from "@web/views/fields/formatters";
import { parseInteger } from "@web/views/fields/parsers";
import { useInputField } from "@web/views/fields/input_field_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component } from "@odoo/owl";

export class IntegerPercentageField extends Component {
    static template = "hc_integer_percentage.IntegerPercentageField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
    };

    setup() {
        useInputField({
            getValue: () => {
                const value = this.props.record.data[this.props.name];
                return value === false || value === null ? "" : String(value);
            },
            refName: "input",
            parse: (v) => {
                const stripped = v.endsWith("%") ? v.slice(0, -1) : v;
                return parseInteger(stripped);
            },
        });
    }

    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        if (value === false || value === null || value === undefined) {
            return "";
        }
        return `${formatInteger(value)}%`;
    }
}

export const integerPercentageField = {
    component: IntegerPercentageField,
    displayName: _t("Integer Percentage"),
    supportedTypes: ["integer"],
    extractProps: ({ attrs }) => ({
        placeholder: attrs.placeholder,
    }),
};

registry.category("fields").add("integer_percentage", integerPercentageField);
