import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListRenderer } from "@web/views/list/list_renderer";

import { Component, useSubEnv } from "@odoo/owl";

export class LineNumberCell extends Component {
    static template = "hc_line_number.LineNumberCell";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
        getLineNumber: Function,
    };
}

const lineNumberCellWidget = {
    component: LineNumberCell,
    listViewWidth: [48, 120],
    extractProps: ({ options }) => ({ getLineNumber: options.getLineNumber }),
};

export class LineNumberListRenderer extends ListRenderer {
    static template = "hc_line_number.ListRenderer";

    getActiveColumns(list) {
        const columns = super.getActiveColumns(list);
        // place the number column right after the drag handle, like sequence UIs
        const index = columns.findIndex((col) => col.widget === "handle") + 1;
        columns.splice(index, 0, this.makeLineNumberColumn());
        return columns;
    }

    makeLineNumberColumn() {
        const widgetInfo = {
            name: "line_number",
            widget: lineNumberCellWidget,
            attrs: {},
            options: { getLineNumber: this.getLineNumber.bind(this) },
        };
        return {
            ...widgetInfo,
            type: "widget",
            id: "column_line_number",
            label: this.env.lineNumberString || "#",
            props: { name: "line_number", widgetInfo },
        };
    }

    getLineNumber(record) {
        const list = this.props.list;
        // compare datapoint ids, not object identity: records may be wrapped
        // in distinct reactive proxies depending on where they are read from
        const index = list.records.findIndex((r) => r.id === record.id);
        if (index === -1) {
            return "";
        }
        return (list.offset || 0) + index + 1;
    }
}

export class LineNumberX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: LineNumberListRenderer,
    };
    static props = {
        ...X2ManyField.props,
        lineNumberString: { type: String, optional: true },
    };

    setup() {
        super.setup();
        useSubEnv({ lineNumberString: this.props.lineNumberString });
    }
}

export const lineNumberX2ManyField = {
    ...x2ManyField,
    component: LineNumberX2ManyField,
    displayName: _t("X2many with Line Numbers"),
    supportedOptions: [
        {
            label: _t("Line number label"),
            name: "line_number_string",
            type: "string",
            help: _t("Header of the line number column (default: #)."),
        },
    ],
    extractProps: (fieldInfo, dynamicInfo) => {
        const props = x2ManyField.extractProps(fieldInfo, dynamicInfo);
        if (fieldInfo.options.line_number_string) {
            props.lineNumberString = fieldInfo.options.line_number_string;
        }
        return props;
    },
};

registry.category("fields").add("x2many_line_number", lineNumberX2ManyField);
