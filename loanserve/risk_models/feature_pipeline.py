from pathlib import Path
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from config.constants import (
    CATEGORICAL_MODELLING_COLUMNS,
    HOLDOUT_SHARE,
    NUMERIC_MODELLING_COLUMNS,
    RANDOM_SEED,
    TARGET_COLUMN,
)


def build_feature_pipeline(extra_numeric=(), extra_categorical=()):
    """Builds an unfitted ColumnTransformer preprocessor for modelling columns."""
    numeric_cols = list(NUMERIC_MODELLING_COLUMNS) + list(extra_numeric)
    categorical_cols = list(CATEGORICAL_MODELLING_COLUMNS) + list(extra_categorical)

    numeric_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric_transformer, numeric_cols),
            ("categorical", categorical_transformer, categorical_cols),
        ],
        sparse_threshold=0,
    )

    return preprocessor


def select_modelling_columns(records, extra_numeric=(), extra_categorical=()):
    """Extracts numeric and categorical modelling columns from DataFrame."""
    numeric_cols = [c for c in list(NUMERIC_MODELLING_COLUMNS) + list(extra_numeric) if c in records.columns]
    categorical_cols = [c for c in list(CATEGORICAL_MODELLING_COLUMNS) + list(extra_categorical) if c in records.columns]
    return records[numeric_cols + categorical_cols]


def split_for_modelling(cleaned_file_path, extra_numeric=(), extra_categorical=()):
    """Splits cleaned training data into stratified train and holdout sets."""
    df = pd.read_csv(cleaned_file_path)
    X = select_modelling_columns(df, extra_numeric=extra_numeric, extra_categorical=extra_categorical)
    y = df[TARGET_COLUMN]

    X_train, X_holdout, y_train, y_holdout = train_test_split(
        X,
        y,
        test_size=HOLDOUT_SHARE,
        stratify=y,
        random_state=RANDOM_SEED,
    )

    return X_train, X_holdout, y_train, y_holdout


if __name__ == "__main__":
    cleaned = pd.read_csv("processed_data/loan_applications_cleaned.csv")
    pipe = build_feature_pipeline()
    transformed = pipe.fit_transform(select_modelling_columns(cleaned))
    print(transformed.shape)
