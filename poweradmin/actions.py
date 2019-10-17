# -*- coding: utf-8 -*-
import unicodecsv as csv
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
import cStringIO as StringIO
import cgi
from xhtml2pdf.pisa import pisaDocument


def export_as_csv_action(description=u"Exportar CSV", fields=None, header=True):
    def export_as_csv(modeladmin, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode(modeladmin.opts).replace('.', '_')

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


def report_action(description=u"Impressão", fields=None, header='', template_name='admin/report.html'):
    def report(modeladmin, request, queryset):
        results = {'header': [], 'results': []}
        for field_name in fields:
            text, attr = label_for_field(
                field_name, modeladmin.model,
                model_admin=modeladmin,
                return_attr=True
            )
            results['header'].append(text.capitalize())

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
            results['results'].append(line)


        template = get_template(template_name)
        html  = template.render(RequestContext(request, {
            'header': header,
            'results': results,
        }))
        #return HttpResponse(html)
        result = StringIO.StringIO()
        pdf = pisaDocument(StringIO.StringIO(html.encode("UTF-8")), dest=result, link_callback=lambda uri, rel: os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, "")))
        if not pdf.err:
            return HttpResponse(result.getvalue(), content_type='application/pdf')
        return HttpResponse('We had some errors<pre>%s</pre>' % cgi.escape(html))
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