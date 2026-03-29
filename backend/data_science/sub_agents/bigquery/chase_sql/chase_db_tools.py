import enum
import os

from google.adk.tools import ToolContext
from .dc_prompt_template import DC_PROMPT_TEMPLATE
from .llm_utils import GeminiModel
from .qp_prompt_template import QP_PROMPT_TEMPLATE
from .sql_postprocessor import sql_translator

# pylint: enable=g-importing-member

BQ_PROJECT_ID = os.getenv("BQ_PROJECT_ID")


class GenerateSQLType(enum.Enum):
    """Enum for the different types of SQL generation methods.

    DC: Divide and Conquer ICL prompting
    QP: Query Plan-based prompting
    """

    DC = "dc"
    QP = "qp"


def exception_wrapper(func):
    """A decorator to catch exceptions in a function and return the exception as a string.

    Args:
       func (callable): The function to wrap.

    Returns:
       callable: The wrapped function.
    """

    def wrapped_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Exception occurred in {func.__name__}: {str(e)}"

    return wrapped_function


def parse_response(response: str) -> str:
    """Parses the output to extract SQL content from the response.

    Args:
       response (str): The output string containing SQL query.

    Returns:
       str: The SQL query extracted from the response.
    """
    query = response
    try:
        if "```sql" in response and "```" in response:
            query = response.split("```sql")[1].split("```")[0]
    except ValueError as e:
        print(f"Error in parsing response: {e}")
        query = response
    return query.strip()


def initial_bq_nl2sql(
    question: str,
    tool_context: ToolContext,
) -> str:
    """Generates an initial SQL query from a natural language question.

    Args:
      question: Natural language question.
      tool_context: Function context.

    Returns:
      str: An SQL statement to answer this question.
    """
    print("****** Running agent with ChaseSQL algorithm.")
    # Retrieve the settings for BigQuery specifically
    bq_settings = tool_context.state["database_settings"]["bigquery"]
    
    bq_schema = bq_settings["schema"]
    project = bq_settings["data_project_id"]
    db = bq_settings["dataset_id"]
    
    # FIX: Retrieve these settings from 'bq_settings', not the root 'database_settings'
    transpile_to_bigquery = bq_settings["transpile_to_bigquery"]
    process_input_errors = bq_settings["process_input_errors"]
    process_tool_output_errors = bq_settings["process_tool_output_errors"]
    number_of_candidates = bq_settings["number_of_candidates"]
    model = bq_settings["model"]
    temperature = bq_settings["temperature"]
    generate_sql_type = bq_settings["generate_sql_type"]

    # Use the project from database_settings (authoritative) rather than env var
    effective_project = project or BQ_PROJECT_ID

    if generate_sql_type == GenerateSQLType.DC.value:
        prompt = DC_PROMPT_TEMPLATE.format(
            SCHEMA=bq_schema,
            QUESTION=question,
            BQ_PROJECT_ID=effective_project,
        )
    elif generate_sql_type == GenerateSQLType.QP.value:
        prompt = QP_PROMPT_TEMPLATE.format(
            SCHEMA=bq_schema,
            QUESTION=question,
            BQ_PROJECT_ID=effective_project,
        )
    else:
        raise ValueError(f"Unsupported generate_sql_type: {generate_sql_type}")

    model_obj = GeminiModel(model_name=model, temperature=temperature)

    # Use direct single call when number_of_candidates == 1 to avoid
    # ThreadPoolExecutor overhead, which adds ~1-2s of latency.
    if number_of_candidates == 1:
        responses = model_obj.call(prompt, parser_func=parse_response)
    else:
        requests = [prompt for _ in range(number_of_candidates)]
        responses = model_obj.call_parallel(requests, parser_func=parse_response)
        responses = responses[0]

    # If postprocessing of the SQL to transpile it to BigQuery is required,
    # then do it here.
    if transpile_to_bigquery:
        translator = sql_translator.SqlTranslator(
            model=model_obj,
            temperature=temperature,
            process_input_errors=process_input_errors,
            process_tool_output_errors=process_tool_output_errors,
        )
        responses: str = translator.translate(
            responses, ddl_schema=bq_schema, db=db, catalog=effective_project
        )

    return responses