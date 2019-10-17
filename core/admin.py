from django.contrib import admin
from django.core.urlresolvers import reverse
from poweradmin.admin import *
from .models import Aluno

class MyModelAdmin(PowerModelAdmin):
    def get_buttons(self, request, object_id):
        buttons = super(MyModelAdmin, self).get_buttons(request, object_id)
        if object_id: # Button into change
            buttons.append(PowerButton(url=reverse('admin:myapp_mymodel_changelist'), label=u'Back'))
        else: # Button on list display
            buttons.append(PowerButton(url=u'http://google.com.br/', label=u'Google', attrs={'target': '_blank'}))
        return buttons
        
    multi_search = (
        ('q1', u'Nome', ['nome']), 
        ('q2', u'Idade', ['idade'])               
    )

    list_csv = ('nome', 'idade',)
    list_display = ('nome', 'idade', )

admin.site.register(Aluno, MyModelAdmin)