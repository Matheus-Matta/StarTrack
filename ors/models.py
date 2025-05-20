from django.db import models

class Rota(models.Model):
    cor = models.CharField(max_length=7, default='#3498db')
    nome = models.CharField(max_length=100, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    paradas = models.IntegerField()
    distancia_km = models.FloatField()
    tempo_min = models.FloatField()
    geojson = models.JSONField()
    pontos = models.JSONField()
    entregas = models.JSONField()

    def __str__(self):
        return self.nome

class ComposicaoRota(models.Model):
    nome = models.CharField(max_length=100)
    data_criacao = models.DateTimeField(auto_now_add=True)
    rotas = models.ManyToManyField('Rota', related_name='composicoes')
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nome

    @property
    def total_paradas(self):
        return sum(rota.paradas for rota in self.rotas.all())

    @property
    def total_distancia(self):
        return round(sum(rota.distancia_km for rota in self.rotas.all()), 2)

    @property
    def total_tempo(self):
        return round(sum(rota.tempo_min for rota in self.rotas.all()), 1)