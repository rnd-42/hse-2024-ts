CREATE TABLE time_series.products (
  "product_id" INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "name" varchar,
  "category" varchar,
  "parameters" jsonb
);

CREATE TABLE time_series.timestamps (
  "timestamp_id" INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "time_series_id" integer NOT NULL,
  "attribute_id" integer NOT NULL,
  "value" text,
  "start_dt" timestamp NOT NULL,
  "end_dt" timestamp
);

CREATE TABLE time_series.attributes (
  "attribute_id" INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "name" text,
  "data_type" text NOT NULL
);

CREATE TABLE time_series.time_series (
  "time_series_id" INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "parent_time_series_id" integer,
  "name" text,
  "product_id" integer NOT NULL
);

ALTER TABLE time_series.time_series ADD FOREIGN KEY ("product_id") REFERENCES time_series.products ("product_id");

ALTER TABLE time_series.timestamps ADD FOREIGN KEY ("time_series_id") REFERENCES time_series.time_series ("time_series_id");

ALTER TABLE time_series.timestamps ADD FOREIGN KEY ("attribute_id") REFERENCES time_series.attributes ("attribute_id");

ALTER TABLE time_series.time_series ADD FOREIGN KEY ("parent_time_series_id") REFERENCES time_series.time_series ("time_series_id");

CREATE TABLE time_series.forecasting_models (
  "model_id" INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "time_series_id" integer NOT NULL,
  "feature_attribute_id" integer NOT NULL,
  "target_attribute_id" integer NOT NULL,
  "model_file_path" varchar(255)
);

ALTER TABLE time_series.forecasting_models ADD FOREIGN KEY ("time_series_id") REFERENCES time_series.time_series ("time_series_id");
ALTER TABLE time_series.forecasting_models ADD FOREIGN KEY ("feature_attribute_id") REFERENCES time_series.attributes ("attribute_id");
ALTER TABLE time_series.forecasting_models ADD FOREIGN KEY ("target_attribute_id") REFERENCES time_series.attributes ("attribute_id");
