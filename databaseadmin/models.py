from django.db import models
from django.db import connection
from typing import List, Optional, TypedDict, TypeVar, Type
from datetime import datetime
from django.db.models import QuerySet

class HierarchyDict(TypedDict):
    id: int
    name: str
    product: str
    children: List['HierarchyDict']

class TimestampDict(TypedDict):
    root_time_series_id: int
    timestamp_id: int
    initial_time_series_id: int
    attribute_id: int
    value: str
    start_dt: datetime
    end_dt: Optional[datetime]
    depth: int

T = TypeVar('T', bound=models.Model)

class Product(models.Model):
    product_id: models.AutoField = models.AutoField(primary_key=True, verbose_name="product_id")
    name: models.CharField = models.CharField(max_length=255, verbose_name="name")
    category: models.CharField = models.CharField(max_length=255, blank=True, null=True, verbose_name="category")
    parameters: models.JSONField = models.JSONField(blank=True, null=True, default=dict, verbose_name="parameters")

    class Meta:
        db_table = 'products'
        verbose_name = "Product"
        verbose_name_plural = "Products"
        managed = True

    def __str__(self) -> str:
        return self.name

    def display_name(self) -> str:
        return f"{self.name} (ID: {self.product_id})"

class Attribute(models.Model):
    attribute_id: models.AutoField = models.AutoField(primary_key=True, verbose_name="attribute_id")
    name: models.TextField = models.TextField(verbose_name="name")
    data_type: models.TextField = models.TextField(verbose_name="data_type")

    class Meta:
        db_table = 'attributes'
        verbose_name = "Attribute"
        verbose_name_plural = "Attributes"
        managed = True

    def __str__(self) -> str:
        return self.name

    def display_name(self) -> str:
        return f"{self.name} (ID: {self.attribute_id})"

class TimeSeries(models.Model):
    time_series_id: models.AutoField = models.AutoField(primary_key=True, verbose_name="time_series_id")
    parent_time_series: models.ForeignKey = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="parent_time_series"
    )
    name: models.TextField = models.TextField(verbose_name="name")
    product: models.ForeignKey = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="product")

    class Meta:
        db_table = 'time_series'
        verbose_name = "Time Series"
        verbose_name_plural = "TimeSeries"
        managed = True

    def __str__(self) -> str:
        return f"{self.name} (ID: {self.time_series_id})"

    def display_name(self) -> str:
        return f"{self.name} (ID: {self.time_series_id})"

    @classmethod
    def get_available_series(cls: Type['TimeSeries']) -> QuerySet['TimeSeries']:
        return cls.objects.all().order_by('time_series_id')

    def get_hierarchy_data(self) -> List[TimestampDict]:
        """Получает все таймстемпы для данного временного ряда и его родительских рядов"""
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH RECURSIVE ts_hierarchy AS (
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
            
            if cursor.description is None:
                return []
                
            columns = [col[0] for col in cursor.description]
            return [
                dict(zip(columns, row))  # type: ignore
                for row in cursor.fetchall()
            ]

    def get_hierarchy(self) -> HierarchyDict:
        """Возвращает иерархическую структуру временных рядов"""
        hierarchy: HierarchyDict = {
            'id': self.time_series_id,
            'name': self.name,
            'product': self.product.name,
            'children': []
        }
        
        children: QuerySet['TimeSeries'] = TimeSeries.objects.filter(parent_time_series=self)
        for child in children:
            hierarchy['children'].append(child.get_hierarchy())
            
        return hierarchy

    @classmethod
    def get_root_hierarchy(cls: Type['TimeSeries']) -> List[HierarchyDict]:
        """Возвращает иерархию всех корневых временных рядов"""
        root_series: QuerySet['TimeSeries'] = cls.objects.filter(parent_time_series__isnull=True)
        return [series.get_hierarchy() for series in root_series]

class Timestamp(models.Model):
    timestamp_id: models.AutoField = models.AutoField(primary_key=True, verbose_name="timestamp_id")
    time_series: models.ForeignKey = models.ForeignKey(TimeSeries, on_delete=models.CASCADE, verbose_name="time_series")
    attribute: models.ForeignKey = models.ForeignKey(Attribute, on_delete=models.CASCADE, verbose_name="attribute")
    value: models.TextField = models.TextField(verbose_name="value")
    start_dt: models.DateTimeField = models.DateTimeField(verbose_name="start_dt")
    end_dt: models.DateTimeField = models.DateTimeField(null=True, blank=True, verbose_name="end_dt")

    class Meta:
        db_table = 'timestamps'
        verbose_name = "Timestamp"
        verbose_name_plural = "Timestamps"
        managed = True

    def __str__(self) -> str:
        return f"{self.time_series.name} - {self.attribute.name}: {self.value}"

    def display_name(self) -> str:
        return f"{self.time_series.name} - {self.attribute.name}: {self.value} (ID: {self.timestamp_id})"
