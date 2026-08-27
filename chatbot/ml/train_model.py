import os
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score


# Project root
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


# Dataset location
DATA_PATH = os.path.join(
    BASE_DIR,
    "student_data.csv"
)


# Model save location
MODEL_PATH = os.path.join(
    BASE_DIR,
    "chatbot",
    "ml",
    "student_performance_model.pkl"
)


# =========================
# LOAD DATA
# =========================

df = pd.read_csv(DATA_PATH)

print("Dataset loaded successfully.")
print("Number of students:", len(df))


# =========================
# FEATURES
# =========================

features = [
    "attendance",
    "study_hours",
    "assignment_score",
    "quiz_score",
    "previous_marks"
]

X = df[features]

y = df["marks"]


# =========================
# TRAIN / TEST SPLIT
# =========================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)


# =========================
# CREATE MODEL
# =========================

model = LinearRegression()


# =========================
# TRAIN MODEL
# =========================

model.fit(X_train, y_train)

print("Model trained successfully.")


# =========================
# TEST MODEL
# =========================

predictions = model.predict(X_test)

mae = mean_absolute_error(
    y_test,
    predictions
)

r2 = r2_score(
    y_test,
    predictions
)


print()
print("Model Evaluation")
print("-----------------")
print("Mean Absolute Error:", round(mae, 2))
print("R2 Score:", round(r2, 2))


# =========================
# SAVE MODEL
# =========================

joblib.dump(
    model,
    MODEL_PATH
)

print()
print("Model saved successfully.")
print("Location:", MODEL_PATH)