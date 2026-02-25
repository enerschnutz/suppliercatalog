const original_settings = frappe.listview_settings['Sales Invoice'] || {};
const original_onload = original_settings.onload;

frappe.listview_settings['Sales Invoice'] = original_settings;

frappe.listview_settings['Sales Invoice'].onload = function(listview) {

  if (original_onload) {
    original_onload(listview);
  }

    // ---------------------------------------
    // Progress Listener
    // ---------------------------------------

    frappe.realtime.on("bulk_email_progress", function(data) {

      frappe.show_progress(
        __("Sending Emails"),
        data.current,
        data.total
      );

    });

    frappe.realtime.on("bulk_email_done", function(data) {

      frappe.hide_progress();

      if (data.failed_docs.length) {

        frappe.msgprint({
          title: __("Email Job Finished with Errors"),
          message: __(
            "Successfully sent {0} of {1} documents.<br><br><b>Failed:</b><br>{2}",
            [
              data.success_count,
              data.total,
              data.failed_docs.join("<br>")
            ]
          ),
          indicator: "orange"
        });

      } else {

        frappe.msgprint({
          title: __("Email Job Finished"),
          message: __(
            "Successfully sent {0} of {1} documents.",
            [data.success_count, data.total]
          ),
          indicator: "green"
        });

      }

      listview.refresh();
    });

    // ---------------------------------------
    // Action Button
    // ---------------------------------------

    listview.page.add_action_item(__('Send Email'), async () => {

      const selected = listview.get_checked_items();

      if (!selected.length) {
        frappe.msgprint(__('Please select at least one invoice.'));
        return;
      }

      const not_submitted = selected
        .filter(d => d.docstatus !== 1)
        .map(d => d.name);

      if (not_submitted.length) {
        frappe.throw(
          __('Only submitted documents can be sent. Remove:<br><br>{0}',
            [not_submitted.join('<br>')])
        );
        return;
      }

      const dialog = new frappe.ui.Dialog({
        title: __('Send Email'),
        size: "large",
        fields: [
          {
            label: __('Email Template'),
            fieldname: 'email_template',
            fieldtype: 'Link',
            options: 'Email Template',
            reqd: 1
          },
          { fieldtype: "Section Break" },
          {
            label: __('Preview Subject'),
            fieldname: 'preview_subject',
            fieldtype: 'Data',
            read_only: 1
          },
          {
            label: __('Preview Message'),
            fieldname: 'preview_message',
            fieldtype: 'HTML'
          }
        ],
        primary_action_label: __('Send'),
        primary_action: async (values) => {

          const template = values.email_template;
          const names = selected.map(r => r.name);

          dialog.hide();

          if (names.length > 5) {

            await frappe.call({
              method: "suppliercatalog.german_accounting.utils.quick_mail.enqueue_bulk_sales_invoice_email",
              args: {
                invoice_names: names,
                template_name: template
              }
            });

            frappe.show_alert({
              message: __("Background job started."),
              indicator: "blue"
            });

            return;
          }

          frappe.show_progress(__('Sending Emails'), 0, names.length);

          let success = 0;
          let failed_docs = [];

          for (let i = 0; i < names.length; i++) {

            try {
              await frappe.call({
                method: "suppliercatalog.german_accounting.utils.quick_mail.send_sales_invoice_email",
                args: {
                  invoice_name: names[i],
                  template_name: template
                }
              });

              success++;

            } catch (e) {
              failed_docs.push(names[i]);
            }

            frappe.show_progress(
              __('Sending Emails'),
              i + 1,
              names.length
            );
          }

          frappe.hide_progress();

          if (failed_docs.length) {

            frappe.msgprint({
              title: __("Email Job Finished with Errors"),
              message: __(
                "Successfully sent {0} of {1} documents.<br><br><b>Failed:</b><br>{2}",
                [
                  success,
                  names.length,
                  failed_docs.join("<br>")
                ]
              ),
              indicator: "orange"
            });

          } else {

            frappe.msgprint({
              title: __("Email Job Finished"),
              message: __(
                "Successfully sent {0} of {1} documents.",
                [success, names.length]
              ),
              indicator: "green"
            });

          }

          listview.refresh();
        }
      });

      // ---------------------------------------
      // Template Preview on Change
      // ---------------------------------------

      dialog.fields_dict.email_template.df.onchange = async () => {

        const template = dialog.get_value("email_template");
        if (!template) return;

        const preview_invoice = selected[0].name;

        const r = await frappe.call({
          method: "suppliercatalog.german_accounting.utils.quick_mail.preview_sales_invoice_template",
          args: {
            invoice_name: preview_invoice,
            template_name: template
          }
        });

        const data = r.message || {};

        dialog.set_value("preview_subject", data.subject || "");
        dialog.fields_dict.preview_message.$wrapper.html(data.message || "");
      };

      dialog.show();
    });
};