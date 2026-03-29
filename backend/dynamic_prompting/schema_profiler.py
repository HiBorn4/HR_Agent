import os
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from google.oauth2 import service_account
import logging

logger = logging.getLogger(__name__)

class SchemaProfiler:
    def __init__(self, project_id: str, credentials_path: str, dataset_id: str):
        self.project_id = project_id
        self.dataset_id = dataset_id
        
        # Construct SQLAlchemy Engine for BigQuery
        # Note: Requires sqlalchemy-bigquery installed
        self.engine_url = f'bigquery://{project_id}/{dataset_id}' if dataset_id else f'bigquery://{project_id}'
        
        self.credentials_path = credentials_path
        self._db = None

    def _get_db_connection(self):
        """Lazy load the database connection with LangChain wrapper."""
        if self._db is None:
            try:
                # Load credentials for SQLAlchemy
                # (SQLAlchemy-BigQuery automatically looks for GOOGLE_APPLICATION_CREDENTIALS)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
                
                # Initialize LangChain SQLDatabase
                # include_tables: Optional filter to scan only specific tables if needed
                # sample_rows_in_table_info: Fetches 3 rows to show the LLM real data (The "Samples" block)
                self._db = SQLDatabase.from_uri(
                    self.engine_url,
                    sample_rows_in_table_info=3 
                )
                logger.info(f"✅ Connected to Database: {self.project_id}.{self.dataset_id}")
            except Exception as e:
                logger.error(f"❌ Failed to connect to DB: {e}")
                raise e
        return self._db

    def get_dynamic_schema(self, table_names: list = None) -> str:
        """
        Scans the DB and returns a formatted string containing:
        1. DDL (CREATE TABLE statements with types)
        2. 3 Sample rows per table
        """
        db = self._get_db_connection()
        if table_names:
            # Get info only for relevant tables
            return db.get_table_info(table_names)
        else:
            # Get info for ALL tables in the dataset (Caution with context window)
            return db.get_table_info()

    def get_table_names(self) -> list:
        """Returns a list of all available tables."""
        db = self._get_db_connection()
        return db.get_usable_table_names()