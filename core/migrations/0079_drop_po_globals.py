"""Drop the long-dead Po_globals model and its table.

Po_globals stored "company-wide PO header" fields (reference, ABN,
project_address, three free-form notes, etc.) that the legacy PDF
generator (``core.views.pos.generate_po_pdf``) stamped onto every PO
PDF. The live PO send path (``core.views.dashboard.send_po_email`` ->
``generate_po_html``) doesn't read from this table at all, and the
legacy generator was removed during the audit fix-pass alongside the
``Po_globals``-using service module. With no consumers left there is no
reason to keep the table around — see B19/B21 in the PO audit notes.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0078_projecttypes_add_qs_flag'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Po_globals',
        ),
    ]
