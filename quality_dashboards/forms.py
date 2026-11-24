from django import forms
from django.forms import modelformset_factory

from .models import ProcessMap, RawData

import pandas as pd

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

# A Class to validate the data uploaded to Raw Data has expected structure.
class RawDataForm(forms.ModelForm):
    required_columns = ('PartFamily','Station')

    class Meta:
        model = RawData
        fields = ('name', 'upload')

    def __init__(self, *args, **kwargs):
        super().__init__(*args,  **kwargs)
        self.process_map_pairs = None

    def clean_upload(self):
        upload = self.cleaned_data['upload']

        # Check if the data is from a new upload rather than an edit
        if not self.files.get(self.add_prefix('upload')):
            return upload

        try:
            # Check the expected columns from upload.
            dataframe = pd.read_csv(upload)
        except (
           pd.errors.EmptyDataError,
           pd.errors.ParserError,
           UnicodeDecodeError, 
        ) as exc:
            raise forms.ValidationError(
                'Upload data must be a readable CSV file with a header row.'
            ) from exc
        finally:
            upload.seek(0)

        missing = set(self.required_columns) - set(dataframe.columns)
        if missing:
            raise forms.ValidationError('Missing required column(s): ' + ', '.join(sorted(missing)))

        # Helper definitions for parsing to ProcessMap model downstream.
        pairs = (
            dataframe.loc[:, self.required_columns]
            .dropna()
            .drop_duplicates()
        )
        self.process_map_pairs = list(
            pairs.itertuples(index=False, name=None)
        )

        return upload