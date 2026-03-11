from pathlib import Path
import logging

from comparators.data_comparator import DataComparator
from comparators.data_comparator_pbit import PbitDataComparator

logger = logging.getLogger(__name__)


def run_data_comparison(twbx_tables, powerbi_tables, powerbi_path, verbose=False):

    ext = Path(powerbi_path).suffix.lower()

    if ext == ".pbix":
        logger.info("Using PBIX DataComparator")
        comparator = DataComparator()

    elif ext == ".pbit":
        logger.info("Using PBIT DataComparator")
        comparator = PbitDataComparator()

    else:
        raise ValueError(f"Unsupported Power BI file type: {ext}")

    return comparator.compare_tables(
        twbx_tables,
        powerbi_tables,
        verbose=verbose
    )