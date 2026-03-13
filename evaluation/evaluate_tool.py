import pandas as pd

file_path = "Book1.xlsx"   # your Excel file name

# Read sheets
expected = pd.read_excel(file_path, sheet_name="Sheet1")
tool = pd.read_excel(file_path, sheet_name="Sheet2")

expected.columns = expected.columns.str.strip()
tool.columns = tool.columns.str.strip()

print("Expected columns:", expected.columns)
print("Tool columns:", tool.columns)

# Merge on test_id
df = pd.merge(expected, tool, on="test_id", suffixes=("_expected", "_pred"))

# Compare predictions
df["visual_correct"] = (df["visual_result_expected"] == df["visual_result_pred"]).astype(int)
df["semantic_correct"] = (df["semantic_result_expected"] == df["semantic_result_pred"]).astype(int)
df["data_correct"] = (df["data_result_expected"] == df["data_result_pred"]).astype(int)

# Calculate accuracy
visual_acc = df["visual_correct"].mean()
semantic_acc = df["semantic_correct"].mean()
data_acc = df["data_correct"].mean()

print("\nValidation Accuracy")
print("-------------------")
print(f"Visual Accuracy   : {visual_acc:.2%}")
print(f"Semantic Accuracy : {semantic_acc:.2%}")
print(f"Data Accuracy     : {data_acc:.2%}")

# Save comparison file
df.to_excel("evaluation_comparison.xlsx", index=False)

print("\nDetailed comparison saved to evaluation_comparison.xlsx")