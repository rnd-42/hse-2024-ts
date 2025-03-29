from calculate_regression import compute_rolling_elasticity
from calculate_pointwise import compute_pointwise_elasticity
from db_interaction import merge_and_store_elasticities, read_from_postgres


def run_elasticity():
    df = read_from_postgres()

    regression_df_7 = compute_rolling_elasticity(df, 7 * 24)
    regression_df_14 = compute_rolling_elasticity(df, 14 * 24)
    regression_df_30 = compute_rolling_elasticity(df, 30 * 24)
    pointwise_df_7 = compute_pointwise_elasticity(df, 7)
    pointwise_df_14 = compute_pointwise_elasticity(df, 14)
    pointwise_df_30 = compute_pointwise_elasticity(df, 30)

    merge_and_store_elasticities(regression_df_7, regression_df_14, regression_df_30, pointwise_df_7, pointwise_df_14,
                                 pointwise_df_30)
