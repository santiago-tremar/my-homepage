from django import forms
from django.forms import modelformset_factory
from .models import ProcessMap

# A Class to feed the following function.
class StationProcessForm(forms.ModelForm):
    class Meta:
        model = ProcessMap
        # ONLY include the field users are allowed to edit.
        fields = ['operation_id', 'result_filter']

# This creates a formset that allows editing multiple StationProcess rows at once.
StationProcessFormSet = modelformset_factory(
    ProcessMap, 
    form=StationProcessForm,
    extra=0
)