# -*- coding: utf-8 -*-
import io
import os

from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import get_deleted_objects, model_ngettext
from django.core.exceptions import PermissionDenied
from django.db import models, router
from django.template.response import TemplateResponse
from django.utils.encoding import force_text
from django.utils.html import strip_tags
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.admin.utils import label_for_field, display_for_field, display_for_value, lookup_field

from django.template.loader import get_template
from django.template import RequestContext
from io import StringIO
import cgi

import csv
# from xhtml2pdf.pisa import pisaDocument
from xhtml2pdf.document import pisaDocument
from .stdlib import nvl

def export_as_csv_action(description=u"Exportar CSV", fields=None, header=True):
    def export_as_csv(modeladmin, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s.csv' % modeladmin.opts.db_table

        writer = csv.writer(response)
        if header:
            fields_header = []
            for field_name in fields:
                text, attr = label_for_field(
                    field_name, modeladmin.model,
                    model_admin=modeladmin,
                    return_attr=True
                )
                fields_header.append(text.capitalize())
            writer.writerow(fields_header)

        for obj in queryset:
            line = []
            for field_name in fields:
                f, attr, value = lookup_field(field_name, obj, modeladmin)
                if f is None or f.auto_created:
                    boolean = getattr(attr, 'boolean', False)
                    result_repr = display_for_value(value, boolean)
                else:
                    if isinstance(f.rel, models.ManyToOneRel):
                        field_val = getattr(obj, f.name)
                        if field_val is None:
                            result_repr = '-'
                        else:
                            result_repr = field_val
                    else:
                        result_repr = display_for_field(value, f, '-')
                line.append(strip_tags(u'%s' % result_repr))
            writer.writerow(line)
        return response
    export_as_csv.short_description = description
    return export_as_csv


def report_action(description=u"Impressão", fields=None, title='', template_name='admin/report.html'):

    def report(modeladmin, request, queryset):
        header = []
        linhas = []
        style = []
        for field in fields:
            field_detail = field.split(':')
            field_name = field_detail[0]
            text, attr = label_for_field(
                field_name, modeladmin.model,
                model_admin=modeladmin,
                return_attr=True
            )

            if len(fields) < 3:
                align = "text-align: %s;" % 'left'
                width = '"width: %s; %s"' % ('400px', align)
            else:
                align = "text-align: %s;" % (field_detail[2] if len(field_detail) > 2 else 'center')
                width = '"width: %s; %s"' % (field_detail[1] if len(field_detail) > 1 else '300px', align)


            style.append(width)

            header.append('<th class="border-top border-bottom" style=%s><b>%s</b></th>' % (width,text))

        for obj in queryset:
            line = ''
            fieldno = 0
            for field in fields:
                field_detail = field.split(':')
                field_name = field_detail[0]
                f, attr, value = lookup_field(field_name, obj, modeladmin)
                #print(f, attr, value)
                if f is None or f.auto_created:
                    boolean = getattr(attr, 'boolean', False)
                    result_repr = display_for_value(value, boolean)
                else:
                    if isinstance(f.rel, models.ManyToOneRel):
                        field_val = getattr(obj, f.name)
                        if field_val is None:
                            result_repr = ' '
                        else:
                            result_repr = field_val
                    else:
                        result_repr = display_for_field(value, f, None)
                result_repr = nvl(strip_tags(result_repr), ' ')
                line += '<td style=%s>%s</td>' % (style[fieldno], result_repr)
                fieldno += 1
            linhas.append(line)
        print(linhas)
        template = get_template(template_name)
        html = template.render({'title': title, 'header': header, 'linhas': linhas, })
        result = io.BytesIO()
        pdf = pisaDocument(io.BytesIO(html.encode("UTF-8")), dest=result, link_callback=lambda uri, rel: os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, "")))
        if not pdf.err:
            return HttpResponse(result.getvalue(), content_type='application/pdf')
        return HttpResponse('Erro na geração do relatório<pre>%s</pre>' % cgi.escape(html))
    report.short_description = description
    return report


def delete_selected(modeladmin, request, queryset):
    """
    Default action which deletes the selected objects.

    This action first displays a confirmation page whichs shows all the
    deleteable objects, or, if the user has no permission one of the related
    childs (foreignkeys), a "permission denied" message.

    Next, it deletes all selected objects and redirects back to the change list.
    """
    opts = modeladmin.model._meta
    app_label = opts.app_label

    # Check that the user has delete permission for the actual model
    if not modeladmin.has_delete_permission(request):
        raise PermissionDenied

    using = router.db_for_write(modeladmin.model)

    # Populate deletable_objects, a data structure of all related objects that
    # will also be deleted.
    deletable_objects, model_count, perms_needed, protected = get_deleted_objects(
        queryset, opts, request.user, modeladmin.admin_site, using)

    # The user has already confirmed the deletion.
    # Do the deletion and return a None to display the change list view again.
    if request.POST.get('post'):
        if perms_needed:
            raise PermissionDenied
        n = queryset.count()
        if n:
            for obj in queryset:
                obj_display = force_text(obj)
                modeladmin.log_deletion(request, obj, obj_display)
                modeladmin.delete_model(request, obj)
            modeladmin.message_user(request, _("Successfully deleted %(count)d %(items)s.") % {
                "count": n, "items": model_ngettext(modeladmin.opts, n)
            }, messages.SUCCESS)
        # Return None to display the change list page again.
        return None

    if len(queryset) == 1:
        objects_name = force_text(opts.verbose_name)
    else:
        objects_name = force_text(opts.verbose_name_plural)

    if perms_needed or protected:
        title = _("Cannot delete %(name)s") % {"name": objects_name}
    else:
        title = _("Are you sure?")

    context = dict(
        modeladmin.admin_site.each_context(request),
        title=title,
        objects_name=objects_name,
        deletable_objects=[deletable_objects],
        model_count=dict(model_count).items(),
        queryset=queryset,
        perms_lacking=perms_needed,
        protected=protected,
        opts=opts,
        action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
    )

    request.current_app = modeladmin.admin_site.name

    # Display the confirmation page
    return TemplateResponse(request, modeladmin.delete_selected_confirmation_template or [
        "admin/%s/%s/delete_selected_confirmation.html" % (app_label, opts.model_name),
        "admin/%s/delete_selected_confirmation.html" % app_label,
        "admin/delete_selected_confirmation.html"
    ], context)

delete_selected.short_description = ugettext_lazy("Delete selected %(verbose_name_plural)s")