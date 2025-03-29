from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Cast
from django.db.models import Q
from django.db import connection

class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=255, blank=True, null=True)
    parameters = models.JSONField()

    class Meta:
        db_table = 'products'
        verbose_name = "Product"
        verbose_name_plural = "Products"
        managed=True
        
    def __str__(self):
        return self.name

class Attribute(models.Model):
    attribute_id = models.AutoField(primary_key=True)
    name = models.TextField()
    data_type = models.TextField()

    class Meta:
        db_table = 'attributes'
        verbose_name = "Attribute"
        verbose_name_plural = "Attributes"
        managed=True
        
    def __str__(self):
        return self.name

class TimeSeries(models.Model):
    time_series_id = models.AutoField(primary_key=True)
    parent_time_series = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.TextField(verbose_name="Название")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    class Meta:
        db_table = 'time_series'
        verbose_name = "Time Series"
        verbose_name_plural = "TimeSeries"
        managed=True
        
    def __str__(self):
        return f"{self.name} (ID: {self.time_series_id})"

    @classmethod
    def get_available_series(cls):
        """Возвращает список всех временных рядов для выбора"""
        return cls.objects.all().order_by('time_series_id')

    def get_hierarchy_data(self):
        """Получает все таймстемпы для данного временного ряда и его родительских рядов"""
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH RECURSIVE ts_hierarchy AS (
                    -- Рекурсивная часть для построения иерархии для каждого time_series_id
                    SELECT 
                        ts_root.time_series_id AS root_time_series_id, 
                        ts.time_series_id, 
                        ts.parent_time_series_id, 
                        1 AS depth 
                    FROM ts_schema.time_series ts_root
                    INNER JOIN ts_schema.time_series ts ON ts_root.time_series_id = ts.time_series_id

                    UNION ALL

                    SELECT 
                        th.root_time_series_id, 
                        ts.time_series_id, 
                        ts.parent_time_series_id, 
                        th.depth + 1 
                    FROM ts_schema.time_series ts
                    INNER JOIN ts_hierarchy th ON th.parent_time_series_id = ts.time_series_id
                )
                , all_timestamps AS (
                    -- Связываем иерархию с временными метками
                    SELECT 
                        th.root_time_series_id,
                        t.timestamp_id,
                        t.time_series_id AS initial_time_series_id,
                        t.attribute_id,
                        t.value,
                        t.start_dt,
                        t.end_dt,
                        th.depth
                    FROM ts_schema.timestamps t
                    INNER JOIN ts_hierarchy th ON t.time_series_id = th.time_series_id
                )
                -- Убираем дубли по (attribute_id, start_dt, end_dt), оставляя минимальную глубину
                SELECT DISTINCT ON (root_time_series_id, attribute_id, start_dt, end_dt)
                    root_time_series_id,
                    timestamp_id,
                    initial_time_series_id,
                    attribute_id,
                    value,
                    start_dt,
                    end_dt,
                    depth
                FROM all_timestamps
                WHERE root_time_series_id = %s
                ORDER BY root_time_series_id, attribute_id, start_dt, end_dt, depth ASC
            """, [self.time_series_id])
            
            columns = [col[0] for col in cursor.description]
            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

    def get_hierarchy(self):
        """Возвращает иерархическую структуру временных рядов"""
        hierarchy = {
            'id': self.time_series_id,
            'name': self.name,
            'product': self.product.name,
            'children': []
        }
        
        # Получаем все дочерние временные ряды
        children = TimeSeries.objects.filter(parent_time_series=self)
        for child in children:
            hierarchy['children'].append(child.get_hierarchy())
            
        return hierarchy

    @classmethod
    def get_root_hierarchy(cls):
        """Возвращает иерархию всех корневых временных рядов"""
        root_series = cls.objects.filter(parent_time_series__isnull=True)
        return [series.get_hierarchy() for series in root_series]

class Timestamp(models.Model):
    timestamp_id = models.AutoField(primary_key=True)
    time_series = models.ForeignKey(TimeSeries, on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.TextField()
    start_dt = models.DateTimeField()
    end_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'timestamps'
        verbose_name = "Timestamp"
        verbose_name_plural = "Timestamps"
        managed=True
        
    def __str__(self):
        return f"{self.time_series.name} - {self.attribute.name}: {self.value}"
