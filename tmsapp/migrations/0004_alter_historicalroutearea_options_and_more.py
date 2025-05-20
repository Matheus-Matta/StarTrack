from django.db import migrations, connection, models

def normalize_geojson(apps, schema_editor):
    if connection.vendor == 'sqlite':
        schema_editor.execute("""
            UPDATE route_area
            SET geojson = NULL
            WHERE geojson = '' OR json_valid(geojson) = 0;
        """)

class Migration(migrations.Migration):
    dependencies = [
        ('tmsapp', '0003_historicalroutearea_status_routearea_status'),
    ]

    operations = [
        # 1º passo: limpa todos os geojson inválidos
        migrations.RunPython(normalize_geojson, reverse_code=migrations.RunPython.noop),

        # 2º passo: aí sim altera o campo para JSONField
        migrations.AlterField(
            model_name='routearea',
            name='geojson',
            field=models.JSONField(
                'GeoJSON', null=True, blank=True, default=None,
                help_text='GeoJSON válido ou NULL'
            ),
        ),

        # ... demais operações da 0004 ...
    ]