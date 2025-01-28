# recursive_union_upwards 
Сбор всех таймстемпов для всех рядов, снизу вверх начиная с конкретного младшего
```sql
WITH RECURSIVE ts_hierarchy AS (
    -- Базовая часть: начинаем с самого младшего дочернего временного ряда
    SELECT time_series_id, parent_time_series_id
    FROM ts_schema.time_series
    WHERE time_series_id = <начальный_id>  -- Начальный временной ряд (младший ребенок)

    UNION ALL

    -- Рекурсивная часть: идем вверх по иерархии, выбираем родительские ряды
    SELECT ts.time_series_id, ts.parent_time_series_id
    FROM ts_schema.time_series ts
    INNER JOIN ts_hierarchy th ON th.parent_time_series_id = ts.time_series_id
)
SELECT t.*
FROM ts_schema.timestamps t
INNER JOIN ts_hierarchy th ON t.time_series_id = th.time_series_id
ORDER BY t.start_dt;
```

# recursive_union_downwards
Сбор всех таймстемпов всех рядов, начиная с некоторого родителя и вниз по всем детям
```sql
WITH RECURSIVE ts_hierarchy AS (
    -- Базовая часть: выбираем все строки с конкретным time_series_id
    SELECT time_series_id, parent_time_series_id
    FROM ts_schema.time_series
    WHERE time_series_id = <начальный_id>  -- Здесь указываем start time_series_id

    UNION ALL

    -- Рекурсивная часть: выбираем все потомки (children)
    SELECT ts.time_series_id, ts.parent_time_series_id
    FROM ts_schema.time_series ts
    INNER JOIN ts_hierarchy th ON th.time_series_id = ts.parent_time_series_id
)
SELECT t.*
FROM ts_schema.timestamps t
INNER JOIN ts_hierarchy th ON t.time_series_id = th.time_series_id
ORDER BY t.start_dt;
```

# recursive_union_upwards_substitute
```sql
WITH RECURSIVE ts_hierarchy AS (
    SELECT time_series_id, parent_time_series_id, 1 AS depth,
    FROM ts_schema.time_series
    WHERE time_series_id = <начальный_id>

    UNION ALL

    SELECT ts.time_series_id, ts.parent_time_series_id, th.depth + 1
    FROM ts_schema.time_series ts
    INNER JOIN ts_hierarchy th ON th.parent_time_series_id = ts.time_series_id
)
, all_timestamps AS (
    SELECT 
        t.*,
        th.depth
    FROM ts_schema.timestamps t
    INNER JOIN ts_hierarchy th ON t.time_series_id = th.time_series_id
)
SELECT DISTINCT ON (attribute_id, start_dt, end_dt) *
FROM all_timestamps
ORDER BY attribute_id, start_dt, end_dt, depth ASC;
```

# view_recursive_union_upwards_substitute

```sql
CREATE OR REPLACE VIEW ts_schema.full_hierarchy_timestamps AS
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
ORDER BY root_time_series_id, attribute_id, start_dt, end_dt, depth ASC;
```