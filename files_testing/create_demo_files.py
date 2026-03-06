import zipfile, json, csv, io, os

ORDERS = [
    {"OrderID": "1001", "Product": "Laptop",   "Category": "Electronics", "Sales": 1200.00, "Quantity": 2,   "Region": "East"},
    {"OrderID": "1002", "Product": "Chair",    "Category": "Furniture",   "Sales": 350.00,  "Quantity": 5,   "Region": "West"},
    {"OrderID": "1003", "Product": "Notebook", "Category": "Office",      "Sales": 15.00,   "Quantity": 100, "Region": "North"},
    {"OrderID": "1004", "Product": "Monitor",  "Category": "Electronics", "Sales": 450.00,  "Quantity": 3,   "Region": "East"},
    {"OrderID": "1005", "Product": "Desk",     "Category": "Furniture",   "Sales": 600.00,  "Quantity": 2,   "Region": "South"},
    {"OrderID": "1006", "Product": "Keyboard", "Category": "Electronics", "Sales": 80.00,   "Quantity": 10,  "Region": "West"},
    {"OrderID": "1007", "Product": "Lamp",     "Category": "Office",      "Sales": 45.00,   "Quantity": 7,   "Region": "North"},
    {"OrderID": "1008", "Product": "Tablet",   "Category": "Electronics", "Sales": 750.00,  "Quantity": 4,   "Region": "South"},
]
REGIONS = [
    {"Region": "East",  "RegionManager": "Alice", "Target": 50000},
    {"Region": "West",  "RegionManager": "Bob",   "Target": 45000},
    {"Region": "North", "RegionManager": "Carol", "Target": 40000},
    {"Region": "South", "RegionManager": "David", "Target": 42000},
]

def header_only(rows):
    """Header-only CSV (0 data rows). pbix_parser.get_data_tables() always returns
    0-row DataFrames, so TWBX CSVs must also be 0 rows for row counts to match."""
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=rows[0].keys()).writeheader()
    return buf.getvalue().encode()

def full_csv(rows):
    """Full CSV with data — used by fail_data TWBX to create intentional row mismatch."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=rows[0].keys())
    w.writeheader(); w.writerows(rows)
    return buf.getvalue().encode()


def create_twbx(path, fail_mode=None):
    od = [dict(r) for r in ORDERS]
    rd = [dict(r) for r in REGIONS]
    # fail_mode=model: keep columns identical, difference is in measure expression
    qty = "Quantity"  # always Quantity in TWBX

    # type="manyToOne" matches PBIX cardinality="manyToOne" after normalization
    rel = ('<!-- no relationship -->' if fail_mode == "relationship" else
           '<relation join="inner" type="manyToOne" left="Orders" right="Regions" '
           'left_key="Region" right_key="Region"/>')

    # Expressions use table-qualified syntax to exactly match PBIX measure expressions
    xml = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2023.1.0' source-platform='win' version='18.1'>
  <datasources>
    <datasource caption='MigrateIQ Demo' name='demo' version='18.1'>
      <connection class='textscan' filename='Data/Orders.csv'/>
      <connection class='textscan' filename='Data/Regions.csv'/>
      {rel}
      <column datatype='string'  name='[OrderID]'       role='dimension' type='nominal'/>
      <column datatype='string'  name='[Product]'       role='dimension' type='nominal'/>
      <column datatype='string'  name='[Category]'      role='dimension' type='nominal'/>
      <column datatype='real'    name='[Sales]'         role='measure'   type='quantitative'/>
      <column datatype='integer' name='[{qty}]'         role='measure'   type='quantitative'/>
      <column datatype='string'  name='[Region]'        role='dimension' type='nominal'/>
      <column datatype='string'  name='[RegionManager]' role='dimension' type='nominal'/>
      <column datatype='integer' name='[Target]'        role='measure'   type='quantitative'/>
      <calculated-field caption='Total Sales' name='Total Sales'
        formula='SUM(Orders[Sales])' type='real'/>
      <calculated-field caption='Profit' name='Profit'
        formula='SUM(Orders[Sales]) * 0.3' type='real'/>
    </datasource>
  </datasources>
  <worksheets><worksheet name='Sales by Region'><table><view>
    <datasources><datasource caption='MigrateIQ Demo' name='demo'/></datasources>
    <shelf type='columns'><field>[Region]</field></shelf>
    <shelf type='rows'><field>[Total Sales]</field></shelf>
  </view></table></worksheet></worksheets>
  <dashboards><dashboard name='Overview'>
    <zones><zone name='Sales by Region' type='worksheet' w='1000' h='600'/></zones>
  </dashboard></dashboards>
</workbook>"""

    orders_csv  = full_csv(od) if fail_mode == "data" else header_only(od)
    regions_csv = full_csv(rd) if fail_mode == "data" else header_only(rd)

    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('workbook.xml',     xml.encode())
        zf.writestr('Data/Orders.csv',  orders_csv)
        zf.writestr('Data/Regions.csv', regions_csv)
    print(f"  Created: {path}")


def create_pbix(path, fail_mode=None):
    qty = "Quantity"  # always Quantity (model fail is via measure expression, not column rename)
    orders_cols = [
        {"name": "OrderID",   "dataType": "string", "sourceColumn": "OrderID"},
        {"name": "Product",   "dataType": "string", "sourceColumn": "Product"},
        {"name": "Category",  "dataType": "string", "sourceColumn": "Category"},
        {"name": "Sales",     "dataType": "double", "sourceColumn": "Sales"},
        {"name": qty,         "dataType": "int64",  "sourceColumn": qty},
        {"name": "Region",    "dataType": "string", "sourceColumn": "Region"},
    ]
    regions_cols = [
        {"name": "Region",        "dataType": "string", "sourceColumn": "Region"},
        {"name": "RegionManager", "dataType": "string", "sourceColumn": "RegionManager"},
        {"name": "Target",        "dataType": "int64",  "sourceColumn": "Target"},
    ]
    rels = [] if fail_mode == "relationship" else [{
        "fromColumn": {"name": "Region"}, "toTable": "Regions",
        "toColumn":   {"name": "Region"}, "cardinality": "manyToOne",
        "isActive": True, "crossFilteringBehavior": "oneDirection"
    }]
    profit_expr = "SUM(Orders[Sales]) * 0.25" if fail_mode == "model" else "SUM(Orders[Sales]) * 0.3"
    measures = [
        {"name": "Total Sales", "expression": "SUM(Orders[Sales])",  "dataType": "real", "formatString": "#,##0.00"},
        {"name": "Profit",      "expression": profit_expr,              "dataType": "real", "formatString": "#,##0.00"},
    ]
    model = {"name": "MigrateIQ Demo", "compatibilityLevel": 1550, "model": {"tables": [
        {"name": "Orders",  "columns": orders_cols, "relationships": rels,  "measures": measures},
        {"name": "Regions", "columns": regions_cols,"relationships": [],    "measures": []},
    ]}}
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="json" ContentType="application/json"/></Types>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('DataModelSchema.json', json.dumps(model, indent=2).encode())
        zf.writestr('Report/Layout.json',   b'{"sections":[]}')
        zf.writestr('Version',              b'2.128.751.0')
        zf.writestr('[Content_Types].xml',  ct.encode())
    print(f"  Created: {path}")


out = os.path.dirname(os.path.abspath(__file__))

print("\n PASS — data/model/relationships all match...")
create_twbx(f"{out}/demo_pass.twbx");        create_pbix(f"{out}/demo_pass.pbix")

print("\n FAIL — Data: TWBX 8 rows vs PBIX 0 rows...")
create_twbx(f"{out}/demo_fail_data.twbx", fail_mode="data")
create_pbix(f"{out}/demo_fail_data.pbix")

print("\n FAIL — Model: Profit measure expression differs (0.3 vs 0.25)...")
create_twbx(f"{out}/demo_fail_model.twbx")
create_pbix(f"{out}/demo_fail_model.pbix", fail_mode="model")

print("\n FAIL — Relationship: missing in PBIX...")
create_twbx(f"{out}/demo_fail_rel.twbx")
create_pbix(f"{out}/demo_fail_rel.pbix", fail_mode="relationship")

print("\n All 8 demo files created!\n")
print(f"Files written to: {out}")
for f in sorted(os.listdir(out)):
    if f.endswith(('.twbx', '.pbix', '.py')):
        print(f"  {f:42s}  {os.path.getsize(f'{out}/{f}'):>6} bytes")