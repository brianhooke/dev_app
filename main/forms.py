# forms.py in your contract_admin app
from django import forms

class CSVUploadForm(forms.Form):
    csv_file = forms.FileField()
