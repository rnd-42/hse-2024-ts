from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseNotFound
from django.contrib.auth.decorators import login_required
from ..models import TimeSeries, Product, Attribute, Timestamp
import zipfile
from .utils import Echo, export_to_csv
import io
import csv
from datetime import datetime

def home(request):
    """
    Домашняя страница приложения.
    """
    return render(request, 'home.html')


@login_required
def export_all_database(request):
    """
    Экспортирует все таблицы базы данных в CSV-файлы и создает ZIP-архив
    с использованием потоковой передачи для эффективной обработки.
    """
    models_to_export = [
        ('products.csv', Product),
        ('attributes.csv', Attribute),
        ('timeseries.csv', TimeSeries),
        ('timestamps.csv', Timestamp),
    ]
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"database_export_{timestamp}.zip"
    
    # Класс для создания потоковой передачи ZIP-файла
    class ZipFileStreamer:
        def __init__(self):
            self.buffer = io.BytesIO()
            self.zip_file = zipfile.ZipFile(self.buffer, 'w', zipfile.ZIP_DEFLATED)
            self.position = 0
            self.finished = False
        
        def write_model_to_zip(self, filename, model):
            pseudo_buffer = Echo()
            writer = csv.writer(pseudo_buffer)
            
            # Получаем имена полей
            field_names = [field.name for field in model._meta.fields]
            
            # Создаем CSV итератор
            def csv_row_generator():
                # Заголовок CSV
                yield writer.writerow(field_names)
                
                # Применяем префетч для оптимизации
                queryset = model.objects.all()
                if hasattr(queryset, 'select_related'):
                    for field in model._meta.fields:
                        if field.is_relation and field.many_to_one:
                            queryset = queryset.select_related(field.name)
                
                # Итерация по частям
                chunk_size = 1000
                start_pk = 0
                has_more = True
                pk_field = model._meta.pk.name
                
                while has_more:
                    # Запрашиваем данные с фильтрацией по первичному ключу для эффективности
                    chunk = list(queryset.filter(**{f"{pk_field}__gt": start_pk}).order_by(pk_field)[:chunk_size])
                    if not chunk:
                        break
                    
                    # Обновляем начальное значение PK для следующего чанка
                    start_pk = getattr(chunk[-1], pk_field)
                    
                    # Обработка текущего чанка
                    for obj in chunk:
                        row_data = []
                        for field in field_names:
                            value = getattr(obj, field)
                            # Форматирование даты/времени для CSV
                            if hasattr(value, 'strftime'):
                                value = value.strftime('%Y-%m-%d %H:%M:%S')
                            row_data.append(value)
                        yield writer.writerow(row_data)
                    
                    # Если получили меньше записей, чем размер чанка, значит это последний чанк
                    has_more = len(chunk) == chunk_size
            
            # Записываем CSV в архив
            content = ''.join(csv_row_generator())
            self.zip_file.writestr(filename, content.encode('utf-8'))
        
        def __iter__(self):
            return self
            
        def __next__(self):
            # Если закончили обработку всех моделей
            if self.finished:
                raise StopIteration
            
            # Добавляем каждую модель в архив
            for filename, model in models_to_export:
                try:
                    self.write_model_to_zip(filename, model)
                except Exception as e:
                    # Логируем ошибку, но продолжаем с другими моделями
                    print(f"Error exporting {filename}: {str(e)}")
            
            # Закрываем ZIP-файл
            self.zip_file.close()
            
            # Получаем содержимое буфера
            zip_data = self.buffer.getvalue()
            
            # Помечаем, что закончили
            self.finished = True
            
            # Возвращаем данные
            return zip_data
    
    # Создаем потоковый ответ
    response = StreamingHttpResponse(
        ZipFileStreamer(),
        content_type='application/zip',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    
    return response


def timeseries_tree_json(request):
    """
    Представление для получения данных о дереве временных рядов в формате JSON.
    Используется для построения динамического дерева на клиентской стороне.
    """
    parent_id = request.GET.get('parent_id')

    if parent_id in (None, '', 'null', 'None'):
        children = TimeSeries.objects.filter(parent_time_series__isnull=True)
    else:
        children = TimeSeries.objects.filter(parent_time_series_id=parent_id)

    data = []
    for ts in children:
        has_children = TimeSeries.objects.filter(parent_time_series=ts).exists()
        data.append({
            "id": ts.time_series_id,
            "text": ts.name,
            "children": has_children,
        })

    return JsonResponse(data, safe=False)


def delete_object(request, model_name, pk):
    """
    Общая функция для удаления объекта любой модели.
    """
    if request.method == 'POST':
        model_map = {
            'product': Product,
            'timeseries': TimeSeries,
        }
        model = model_map.get(model_name.lower())
        if not model:
            messages.error(request, "Неверная модель для удаления.")
            return redirect('home')

        instance = get_object_or_404(model, pk=pk)
        instance.delete()
        messages.success(request, f"{model_name.capitalize()} успешно удалён(а).")
        return redirect(f'/{model_name}/')  # или используй reverse()
    else:
        messages.error(request, "Удаление возможно только методом POST.")
        return redirect('home')


@login_required
def time_series_tree_view(request):
    """
    Представление для страницы с древовидной структурой временных рядов.
    """
    # Получаем корневые временные ряды
    root_series = TimeSeries.objects.filter(parent_time_series__isnull=True)

    # Рекурсивная функция для получения иерархии
    def get_children(parent_id):
        children = TimeSeries.objects.filter(parent_time_series_id=parent_id)
        data = []
        for child in children:
            child_data = {
                'id': child.time_series_id,
                'name': child.name,
                'product': child.product.name if child.product else 'Не указан',
            }
            
            # Получаем детей текущего узла
            child_children = get_children(child.time_series_id)
            child_data['children'] = child_children
            
            # Считаем общее количество потомков (включая потомков потомков)
            total_descendants = len(child_children)
            for descendant in child_children:
                total_descendants += descendant.get('total_descendants', 0)
            child_data['total_descendants'] = total_descendants
            
            data.append(child_data)
        return data

    # Строим дерево с корневыми элементами
    time_series = []
    for root in root_series:
        # Получаем детей корневого элемента
        children = get_children(root.time_series_id)
        
        # Считаем общее количество потомков
        total_descendants = len(children)
        for child in children:
            total_descendants += child.get('total_descendants', 0)
        
        time_series.append({
            'id': root.time_series_id,
            'name': root.name,
            'product': root.product.name if root.product else 'Не указан',
            'children': children,
            'total_descendants': total_descendants
        })

    return render(request, 'time_series_tree.html', {'time_series': time_series})


@login_required
def export_single_table(request, model_name):
    """
    Экспортирует данные из отдельной таблицы в CSV-файл.
    
    Args:
        request: HTTP запрос
        model_name: Имя модели для экспорта
    """
    model_map = {
        'Product': Product,
        'Attribute': Attribute,
        'TimeSeries': TimeSeries,
        'Timestamp': Timestamp,
    }
    
    model = model_map.get(model_name)
    if not model:
        return HttpResponseNotFound("Указанная модель не найдена")
    
    # Получаем все записи модели
    queryset = model.objects.all()
    
    # Используем существующую функцию для экспорта в CSV
    return export_to_csv(queryset, model=model) 