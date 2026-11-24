from django.db import models


class RawData(models.Model):
    """ DataBase entry for files containing mock Production Data for the Dashboard. """
    name = models.CharField(max_length=50)
    upload = models.FileField(upload_to='quality_files/')
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}"

class ProcessMap(models.Model):
    """Define the process ID for each Station Type."""
    family = models.CharField(max_length=100)
    station_type = models.CharField(max_length=100)
    operation_id = models.IntegerField()
    result_filter = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.family} {self.station_type} ({self.operation_id})"
