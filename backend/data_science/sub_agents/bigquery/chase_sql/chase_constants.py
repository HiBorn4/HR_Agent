# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Constants used by the ChaseSQL algorithm."""
import os
from typing import Any
import immutabledict


# Parameters for ChaseSQL.
chase_sql_constants_dict: immutabledict.immutabledict[str, Any] = (
    immutabledict.immutabledict(
        {
            # Whether to transpile the SQL to BigQuery.
            "transpile_to_bigquery": True,
            # Whether to process input errors.
            "process_input_errors": True,
            # Whether to process SQLGlot tool output errors.
            "process_tool_output_errors": True,
            # Number of candidates to generate.
            # Keep at 1 for speed; increase only for accuracy experiments.
            "number_of_candidates": 1,
            # Model to use for CHASE SQL generation.
            # Set CHASE_NL2SQL_MODEL env var to override (e.g. gemini-2.5-pro).
            # Falls back to gemini-2.5-pro if env var is unset.
            "model": os.getenv("CHASE_NL2SQL_MODEL", "gemini-2.5-pro"),
            # Temperature for generation — lower = faster + more deterministic.
            "temperature": 0.2,
            # Type of SQL generation method: "dc" (Divide & Conquer) or "qp" (Query Plan).
            "generate_sql_type": "dc",
        }
    )
)
