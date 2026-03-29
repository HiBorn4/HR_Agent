"""
dynamic_prompting/prompt_manager.py
-------------------------------------
PERFORMANCE FIX: Schema is cached in-process for 10 minutes.

Previously the SchemaProfiler fetched live schema from BigQuery via
SQLAlchemy on every single request — a cold connection + query that took ~9s.
Now it is fetched once and cached until TTL expires.

Result: First request pays 9s. Every subsequent request pays 0s for schema.
"""

import time
import yaml
import json
import os
import logging
from typing import List, Optional
from .schema_profiler import SchemaProfiler

logger = logging.getLogger(__name__)

_SCHEMA_CACHE_TTL = 3600  # 10 minutes


class PromptManager:
    def __init__(self, schema_profiler: SchemaProfiler, rules_path: str):
        self.profiler = schema_profiler
        self.rules = self._load_rules(rules_path)
        self._schema_cache: dict[str, tuple[float, str]] = {}  # table_key → (ts, schema_str)

    def _load_rules(self, path: str):
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _identify_domain(self, query: str) -> str:
        query_lower = query.lower()
        if any(x in query_lower for x in ['lead time', 'ship', 'inventory', 'stock']):
            return 'SCM'
        elif any(x in query_lower for x in ['revenue', 'cost', 'profit', 'budget']):
            return 'Finance'
        else:
            return 'HR'

    def _get_schema_cached(self, target_tables: list) -> str:
        """Return schema from cache, or fetch from BigQuery and cache it."""
        cache_key = ",".join(sorted(target_tables))
        now = time.monotonic()

        if cache_key in self._schema_cache:
            ts, schema_str = self._schema_cache[cache_key]
            if now - ts < _SCHEMA_CACHE_TTL:
                logger.debug("⚡ Schema cache HIT for tables: %s", target_tables)
                return schema_str

        logger.info("🔄 Schema cache MISS — fetching from BigQuery for: %s", target_tables)
        schema_str = self.profiler.get_dynamic_schema(target_tables)
        self._schema_cache[cache_key] = (now, schema_str)
        return schema_str

    def assemble_prompt(self, user_query: str, specific_tables: Optional[List[str]] = None) -> str:
        """Constructs the JIT (Just-In-Time) prompt with cached schema."""
        try:
            domain = self._identify_domain(user_query)
            domain_config = self.rules['domains'].get(domain, self.rules['domains']['HR'])
            business_rules = "\n".join([f"- {rule}" for rule in domain_config['rules']])
            target_tables = specific_tables or ['successfactors_employee_master']
        except Exception as e:
            logger.error("Error in domain identification: %s", e)
            domain = 'HR'
            business_rules = ""
            target_tables = ['successfactors_employee_master']

        # Use cached schema — avoids 9s BigQuery round-trip on every request
        try:
            schema_context = self._get_schema_cached(target_tables)
        except Exception as e:
            schema_context = f"Error fetching schema: {str(e)}"

        prompt = f"""
        You are a Data Agent specializing in {domain}.
        
        ### USER QUERY:
        "{user_query}"

        ### DYNAMIC DATABASE SCHEMA:
        The following tables exist in the database. Use ONLY these columns. 
        3 Sample rows are provided for context on data formats.
        
        {schema_context}

        ### BUSINESS RULES & DOMAIN CONTEXT:
        Follow these definitions strictly when generating SQL:
        {business_rules}

        ### INSTRUCTIONS:
        1. Generate a BigQuery SQL query to answer the user's question.
        2. Do not use columns that do not exist in the schema above.
        3. If the answer cannot be found, reply "I cannot answer this based on available data."
        """

        return prompt