from pathlib import Path
import logging

from comparators.data_comparator import DataComparator
from comparators.data_comparator_pbit import PbitDataComparator

logger = logging.getLogger(__name__)


def run_data_comparison(
    twbx_tables,
    powerbi_tables,
    powerbi_path,
    verbose=False,
    schema_only_tables=None,
):
    ext = Path(powerbi_path).suffix.lower()

    if ext == ".pbix":
        logger.info("Using PBIX DataComparator")
        comparator = DataComparator()

    elif ext == ".pbit":
        logger.info("Using PBIT DataComparator")
        comparator = PbitDataComparator()

    else:
        raise ValueError(f"Unsupported Power BI file type: {ext}")

    kwargs = {"verbose": verbose}
    if schema_only_tables is not None and ext == ".pbix":
        kwargs["schema_only_tables"] = schema_only_tables

    return comparator.compare_tables(twbx_tables, powerbi_tables, **kwargs)