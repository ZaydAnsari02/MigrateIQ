import pandas as pd

xls = pd.ExcelFile("Book1.xlsx")
print(xls.sheet_names)