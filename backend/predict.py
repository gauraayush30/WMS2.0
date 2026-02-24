import pandas as pd
import joblib
from datetime import datetime, timedelta


model = joblib.load("model.pkl")


last_day_number = 2500  
future_days = [[last_day_number + i] for i in range(1, 8)]


predictions = model.predict(future_days)


future_dates = [datetime.today().date() + timedelta(days=i) for i in range(1, 8)]

result = pd.DataFrame({
    "date": future_dates,
    "predicted_sales_qty": predictions
})

print("\nNext 7 Days Sales Prediction:")
print(result)
