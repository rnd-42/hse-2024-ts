from sqlalchemy import create_engine
import pandas as pd
from sqlalchemy.sql import text


def get_engine():
    return create_engine("postgresql://hsedb4:gfkT78kjk@db.int.y.rnd-42.ru:6432/hsedb4")


def merge_and_store_elasticities(regression_df_7, regression_df_14, regression_df_30, pointwise_df_7, pointwise_df_14, pointwise_df_30, engine=None):
    if engine is None:
        engine = get_engine()

    dfs = [regression_df_7, regression_df_14, regression_df_30, pointwise_df_7, pointwise_df_14, pointwise_df_30]

    merged_df = pd.concat(dfs, ignore_index=True)

    min_date = merged_df["date"].min()
    max_date = merged_df["date"].max()

    delete_query = text("""
        DELETE FROM ts_schema.product_elasticities 
        WHERE date BETWEEN :min_date AND :max_date
    """)

    with engine.connect() as conn:
        conn.execute(delete_query, {"min_date": min_date, "max_date": max_date})
        conn.commit()

    merged_df.to_sql("product_elasticities", engine, schema="ts_schema", if_exists="append", index=False)

    print(f"Загружено {len(merged_df)} записей в ts_schema.product_elasticities")


def read_from_postgres(engine=None):
    if engine is None:
        engine = get_engine()
    query = """
    select val as trips, att_val as attribute, t5.dt as date, t5.product_id, t5.attribute_id
    from (select sum(t1.value::float) as val,
        start_dt as dt, t4.product_id, t1.attribute_id
    from ts_schema.timestamps t1
    join ts_schema.attributes t2 
    on t1.attribute_id = t2.attribute_id
    join ts_schema.time_series t3
    on t1.time_series_id = t3.time_series_id
    join ts_schema.products t4
    on t3.product_id = t4.product_id
    group by dt, t4.product_id, t1.time_series_id, t1.attribute_id) t5
    join (select avg(t1.value::float) as att_val,
        start_dt as dt, t4.product_id, t1.attribute_id
    from ts_schema.timestamps t1
    join ts_schema.attributes t2 
    on t1.attribute_id = t2.attribute_id
    join ts_schema.time_series t3
    on t1.time_series_id = t3.time_series_id
    join ts_schema.products t4
    on t3.product_id = t4.product_id
    group by dt, t4.product_id, t1.attribute_id) t6
    on t5.dt = t6.dt
    and t5.product_id = t6.product_id
    and t5.attribute_id = t6.attribute_id
    order by date
    """
    df = pd.read_sql(query, engine)
    print(f"Данные успешно загружены из таблицы")
    return df
