# -*- coding: utf-8 -*-
from datetime import date
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse

EMPTY_VALUES = (None, '', [], (), {})


def is_empty(value):
    return value in EMPTY_VALUES


# simula a função clássica do Oracle: Retorna uma alternativa caso o objeto esteja vazio
def nvl(objeto, alternativa):
    if is_empty(objeto):
        return alternativa
    else:
        return objeto


def normalizar_data(data_string):
    if '/' in data_string:
        dia, mes, ano = data_string.split('/')
    else:
        ano, mes, dia = data_string.split('-')
    if len(ano) == 2:
        ano = '20%s' % ano
    return date(day=int(dia), month=int(mes), year=int(ano))


def url_display(obj):
    content_type = ContentType.objects.get_for_model(obj)
    try:
        return u'<a href="%s">%s</a>' % (
            reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model), args=(obj.pk, )),
            obj,
        )
    except Exception as E:
        return u'%s' % obj
