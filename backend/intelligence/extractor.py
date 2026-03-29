import os
import json
import logging
import traceback
import re
import asyncio
from typing import Dict, Optional
import google.generativeai as genai
from app.startup import RAG_CONFIGURED

# --- NEW: Added for Vertex AI Image Generation ---
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# RAG Corpus Configuration
BQML_RAG_CORPUS_NAME = os.getenv('BQML_RAG_CORPUS_NAME')

VIZ_KEYWORDS = {
    # Direct chart requests
    "chart", "graph", "plot", "visualize", "visualization",
    "dashboard", "diagram",

    # Analytical language
    "trend", "trends", "distribution", "breakdown",
    "comparison", "compare", "versus", "vs",
    "analysis", "analyze", "insight", "insights",
    "summary", "statistics", "stats",

    # Business metrics
    "attrition", "headcount", "revenue", "sales",
    "growth", "increase", "decrease", "decline",
    "profit", "loss", "performance", "ranking",
    "top", "bottom", "highest", "lowest",

    # HR / Workforce
    "tenure", "experience", "employees", "department",
    "division", "workforce", "hiring", "turnover",

    # Financial / KPIs
    "kpi", "metrics", "percentage", "percent",
    "ratio", "average", "mean", "total"
}


class MahindraDataExtractor:
    """
    ✅ Data extraction for business formats, now with Gemini intelligence.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _needs_visualization(response_text: str) -> bool:
        """
        Determines whether visualization extraction is required.
        Prevents Gemini from being called on simple text responses.
        """

        if not response_text or len(response_text) < 50:
            return False

        text_lower = response_text.lower()

        # 1️⃣ Keyword trigger
        if any(keyword in text_lower for keyword in VIZ_KEYWORDS):
            return True

        # 2️⃣ Check for at least 3 distinct numeric values (chartable data)
        numbers = re.findall(r"\b\d+\.?\d*\b", response_text)
        distinct_numbers = set(numbers)

        if len(distinct_numbers) >= 3:
            return True

        return False

    async def _extract_data_with_gemini(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """
        🧠 NEW: Uses Gemini to intelligently extract data points from text.
        """
        # Ensure the Gemini API is configured before proceeding
        if not RAG_CONFIGURED:
            if debug_mode:
                self.logger.warning("📊 Gemini Extractor: RAG not configured, skipping.")
            return None

        # This is the prompt that instructs Gemini how to behave and what to return.
        prompt = f"""
        You are a highly intelligent data extraction assistant. Your task is to analyze the following text and extract any quantifiable data points suitable for a chart.

        **Instructions:**
        1. Identify all pairs of labels (like categories, items, or departments) and their corresponding numerical values.
        2. Also, identify the unit for each value if it's mentioned (e.g., "employees", "%", "years").
        3. Format your findings as a valid JSON object containing a single key "data".
        4. The value of "data" must be a list of JSON objects, where each object has three keys: "label", "value", and "unit".
        5. The "value" must be a number (integer or float), not a string. Remove any commas or symbols.
        6. If you cannot find any chartable data, return a JSON object with an empty list: {{"data": []}}.
        7. Do not include any explanation or commentary outside of the JSON object.

        **Example Input Text:**
        "The analysis shows that the Auto Division has 4,500 employees, the FES Division has 3,200, and TWS has 1,850."

        **Example JSON Output:**
        ```json
        {{
          "data": [
            {{"label": "Auto Division", "value": 4500, "unit": "employees"}},
            {{"label": "FES Division", "value": 3200, "unit": "employees"}},
            {{"label": "TWS", "value": 1850, "unit": "employees"}}
          ]
        }}
        ```

        **Now, analyze this text and provide the JSON output:**

        ---
        {text}
        ---
        """

        try:
            if debug_mode:
                self.logger.info("📊 Calling Gemini for data extraction...")
                
            model = genai.GenerativeModel("gemini-2.5-pro")
            # Use asyncio.to_thread to run the synchronous SDK call in a non-blocking way
            response = await asyncio.to_thread(model.generate_content, prompt)

            # Clean up the response to ensure it's valid JSON
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            if not cleaned_text:
                if debug_mode: self.logger.warning("📊 Gemini returned an empty response.")
                return None

            data_payload = json.loads(cleaned_text)
            
            extracted_data = data_payload.get("data", [])

            # Final validation to ensure the data is in the correct format
            if isinstance(extracted_data, list) and len(extracted_data) >= 2:
                # Ensure all items have the required keys
                for item in extracted_data:
                    if not ('label' in item and 'value' in item and isinstance(item['value'], (int, float))):
                        raise ValueError("Malformed data item from Gemini.")
                
                return {
                    'data': extracted_data,
                    'type': 'gemini_extracted',
                    'confidence': 0.98 # High confidence as it's from a powerful model
                }
            else:
                if debug_mode: self.logger.info("📊 Gemini found less than 2 data points.")
                return None

        except json.JSONDecodeError as e:
            if debug_mode: self.logger.error(f"📊 Gemini JSON parsing failed: {e}. Response was: {cleaned_text}")
            return None
        except Exception as e:
            if debug_mode: self.logger.error(f"📊 Gemini extraction failed with an unexpected error: {e}")
            return None

    async def extract_business_data(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """
        ✅ Enhanced data extraction with comprehensive strategies.
        NOW WITH GEMINI!
        """
        if debug_mode:
            self.logger.info(f"📊 EXTRACTION: Analyzing {len(text)} characters")

        # --- MODIFICATION: Add the Gemini function as the FIRST strategy ---
        # The first successful extraction will be used, so order matters.
        gemini_result = await self._extract_data_with_gemini(text, debug_mode)
        if gemini_result and gemini_result.get('data'):
            score = self._calculate_quality_score(gemini_result)
            if debug_mode:
                self.logger.info(f"✅ GEMINI SUCCESS with {gemini_result['type']}: {len(gemini_result['data'])} items, score: {score:.2f}")
            return gemini_result # If Gemini succeeds, we use its result immediately.

        if debug_mode:
            self.logger.info("📊 Gemini extraction failed or found no data. Falling back to regex strategies.")
            
        strategies = [
            self._extract_table_data,
            self._extract_numbered_list_with_text,
            self._extract_hyphen_bullet_points,
            self._extract_asterisk_bullet_points,
            self._extract_department_data,
            self._extract_financial_data,
            self._extract_percentage_data,
            self._extract_any_numerical_data
        ]
        best_result = None
        best_score = 0
        for i, strategy in enumerate(strategies):
            try:
                result = strategy(text, debug_mode) # These are synchronous
                if result and result.get('data'):
                    score = self._calculate_quality_score(result)
                    if debug_mode:
                        self.logger.info(f"📊 Strategy {strategy.__name__}: {len(result['data'])} items, score: {score:.2f}")
                    if score > best_score:
                        best_result = result
                        best_score = score
            except Exception as e:
                if debug_mode:
                    self.logger.error(f"📊 Strategy {strategy.__name__} failed: {e}")
                continue
                
        if best_result and best_score > 0.3:
            if debug_mode:
                self.logger.info(f"✅ REGEX SUCCESS with {best_result['type']}: {len(best_result['data'])} items, score: {best_score:.2f}")
            return best_result
            
        if debug_mode:
            self.logger.warning("❌ EXTRACTION: No suitable data found by any method.")
        return None

    def _extract_numbered_list_with_text(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """Extracts data from a numbered list format like '1. Label with 1234 units'."""
        # This regex captures the label, the numeric value, and the unit.
        pattern = r'^\d+\.\s*(.+?)\s+(?:with|has|:|is)\s+([\d,]+\.?\d*)\s*([a-zA-Z\s]*)'
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if len(matches) >= 2:
            data = []
            for match in matches:
                try:
                    label = self._clean_label(match[0])
                    value = float(match[1].replace(',', ''))
                    unit = match[2].strip()
                    if value > 0 and len(label) > 1:
                        data.append({
                            'label': label,
                            'value': value,
                            'unit': unit
                        })
                except (ValueError, IndexError):
                    continue
            if len(data) >= 2:
                return {
                    'data': data,
                    'type': 'numbered_list_with_text',
                    'confidence': 0.95
                }
        return None

    def _extract_hyphen_bullet_points(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """
        Extract data from hyphen bullet point format.
        FIXED: This version is more robust and handles formats like '- Label: 1234' and '- Label with 1234'.
        """
        # This single, more robust pattern looks for lines starting with a hyphen, a label,
        # a separator (common words or a colon), a number, and an optional unit.
        pattern = r'^\s*-\s*(.+?)\s+(?:with|has|is|:)\s+([\d,]+\.?\d*)\s*([a-zA-Z%]*)'
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if len(matches) >= 2:
            data = []
            for match in matches:
                try:
                    label = self._clean_label(match[0])
                    value = float(match[1].replace(',', ''))
                    unit = match[2].strip() if len(match) > 2 else ''
                    if value > 0 and len(label) > 2:
                        data.append({
                            'label': label,
                            'value': value,
                            'unit': unit
                        })
                except (ValueError, IndexError) as e:
                    if debug_mode:
                        self.logger.warning(f"📊 Hyphen-point parsing error: {e}")
                    continue
            if len(data) >= 2:
                return {
                    'data': data,
                    'type': 'robust_hyphen_format',
                    'confidence': 0.95 # Higher confidence due to the specific pattern
                }
        return None

    def _extract_asterisk_bullet_points(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """
        FIXED: Robustly extract data from various bullet point lists (*, -, •).
        This is now the primary method for lists.
        """
        # This single pattern handles lines starting with *, -, or •, followed by a label, a colon, a number, and an optional unit.
        # It's anchored to the start of the line (^) to prevent matching text inside paragraphs.
        pattern = r'^\s*[\*\-•]\s*([^:]+?):\s*([\d,]+\.?\d*)\s*([a-zA-Z%]*)'

        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)

        if len(matches) >= 2:
            data = []
            for match in matches:
                try:
                    label = self._clean_label(match[0])
                    value = float(match[1].replace(',', ''))
                    unit = match[2].strip()
                    if value >= 0 and len(label) > 1: # Allow zero values
                        data.append({
                            'label': label,
                            'value': value,
                            'unit': unit
                        })
                except (ValueError, IndexError):
                    continue

            if len(data) >= 2:
                return {
                    'data': data,
                    'type': 'structured_bullet_points', # More descriptive type
                    'confidence': 0.95 # High confidence due to the structured format
                }
        return None

    def _extract_table_data(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """
        Robustly extract data from complex multi-column markdown tables.
        It transforms wide tables into a long format suitable for charting.
        """
        lines = [line.strip() for line in text.strip().split('\n')
                 if '|' in line and '---' not in line]
        if len(lines) < 2: # Need at least a header and one data row
            return None
        header_parts = [h.strip() for h in lines[0].split('|') if h.strip()]
        data_rows = lines[1:]
        # Identify label and value columns
        label_cols_indices = []
        value_cols_indices = []
        # Get the first data row to help determine column types
        first_row_parts = [p.strip() for p in data_rows[0].split('|') if p.strip()]
        for i, h in enumerate(header_parts):
            # Heuristic: If a column in the first data row contains only numbers (and related chars), it's a value column.
            is_numeric = False
            if i < len(first_row_parts):
                # This regex checks for integers, floats, and numbers with commas.
                if re.fullmatch(r'-?[\d,]+\.?\d*', first_row_parts[i]):
                    is_numeric = True
            if is_numeric:
                value_cols_indices.append(i)
            else:
                label_cols_indices.append(i)
        if not value_cols_indices or not label_cols_indices:
            if debug_mode: self.logger.warning("Table found, but couldn't distinguish label/value columns.")
            return None
        extracted_data = []
        for row_line in data_rows:
            parts = [p.strip() for p in row_line.split('|') if p.strip()]
            if len(parts) != len(header_parts):
                continue
            # Combine multiple label columns into one unique base label
            base_label = " - ".join([parts[i] for i in label_cols_indices])
            for val_idx in value_cols_indices:
                try:
                    value_str = parts[val_idx]
                    value = float(value_str.replace(',', ''))
                    # Create a specific label for this data point using the column header
                    series_label = header_parts[val_idx]
                    full_label = f"{base_label} ({series_label})"
                    extracted_data.append({
                        'label': self._clean_label(full_label),
                        'value': value,
                        'unit': '' # Unit is hard to determine reliably from tables
                    })
                except (ValueError, IndexError):
                    continue
        if len(extracted_data) >= 2:
            return {
                'data': extracted_data,
                'type': 'multi_column_table',
                'confidence': 0.85
            }
        return None

    def _extract_department_data(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """Extract department-specific data patterns"""
        dept_patterns = [
            r'([A-Z][A-Za-z\s\-&()]{5,50}(?:Division|Department|Sector|Group))[^0-9]*?([\d,]+\.?\d*)\s*([a-zA-Z%]*)',
            r'(Auto[^0-9]*?)[^0-9]*?([\d,]+\.?\d*)\s*(years?|employees?)',
            r'(FES[^0-9]*?)[^0-9]*?([\d,]+\.?\d*)\s*(years?|employees?)',
            r'(TWS[^0-9]*?)[^0-9]*?([\d,]+\.?\d*)\s*(years?|employees?)',
        ]
        dept_data = []
        seen_labels = set()
        for pattern in dept_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    label = self._clean_label(match[0])
                    value = float(match[1].replace(',', ''))
                    unit = match[2].strip()
                    if value > 0 and len(label) > 3 and label.lower() not in seen_labels:
                        dept_data.append({
                            'label': label,
                            'value': value,
                            'unit': unit
                        })
                        seen_labels.add(label.lower())
                except (ValueError, IndexError):
                    continue
        if len(dept_data) >= 2:
            return {
                'data': dept_data,
                'type': 'department_data',
                'confidence': 0.9
            }
        return None

    def _extract_financial_data(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """Extract financial data patterns"""
        financial_patterns = [
            r'([A-Za-z\s\-&()]{3,40})[^0-9]*?([\d,]+\.?\d*)\s*(million|billion|thousand|crore|lakh|USD|EUR|INR|\$|€|₹)',
            r'Revenue[^0-9]*?([A-Za-z\s\-&()]{3,40})[^0-9]*?([\d,]+\.?\d*)',
            r'Sales[^0-9]*?([A-Za-z\s\-&()]{3,40})[^0-9]*?([\d,]+\.?\d*)',
        ]
        financial_data = []
        for pattern in financial_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if len(match) >= 3:
                        label = self._clean_label(match[0])
                        value = float(match[1].replace(',', ''))
                        unit = match[2] if len(match) > 2 else 'currency'
                    else:
                        label = self._clean_label(match[0])
                        value = float(match[1].replace(',', ''))
                        unit = 'currency'
                    if value > 0 and len(label) > 2:
                        financial_data.append({
                            'label': label,
                            'value': value,
                            'unit': unit
                        })
                except (ValueError, IndexError):
                    continue
        if len(financial_data) >= 2:
            return {
                'data': financial_data,
                'type': 'financial_data',
                'confidence': 0.8
            }
        return None

    def _extract_percentage_data(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """Extract percentage data"""
        percent_patterns = [
            r'([A-Za-z\s\-&()]{3,40})[^0-9]*?([\d,]+\.?\d*)\s*%',
            r'([A-Za-z\s\-&()]{3,40})[^0-9]*?([\d,]+\.?\d*)\s*percent',
        ]
        percent_data = []
        for pattern in percent_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    label = self._clean_label(match[0])
                    value = float(match[1].replace(',', ''))
                    if 0 <= value <= 100 and len(label) > 2:
                        percent_data.append({
                            'label': label,
                            'value': value,
                            'unit': '%'
                        })
                except (ValueError, IndexError):
                    continue
        if len(percent_data) >= 2:
            return {
                'data': percent_data,
                'type': 'percentage_data',
                'confidence': 0.8
            }
        return None

    def _extract_any_numerical_data(self, text: str, debug_mode: bool = False) -> Optional[Dict]:
        """Fallback: Extract any numerical data with context"""
        # --- FIX: Stricter patterns to avoid matching numbers inside sentences ---
        # Pattern 1: Looks for 'Label: 123' format
        pattern1 = r'^\s*([A-Za-z][A-Za-z\s\-&(),.]{3,40}?)\s*:\s*([\d,]+\.?\d*)\s*([a-zA-Z%]*)?$'
        # Pattern 2: Looks for 'Label 123' at the end of a line
        pattern2 = r'^\s*([A-Za-z][A-Za-z\s\-&(),.]{3,40}?)\s+([\d,]+\.?\d*)\s*([a-zA-Z%]*)?$'

        data = []
        seen_labels = set()

        for pattern in [pattern1, pattern2]:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                try:
                    label = self._clean_label(match[0])
                    value = float(match[1].replace(',', ''))
                    unit = match[2].strip() if len(match) > 2 else ''

                    if (value >= 0 and len(label) > 2 and
                        label.lower() not in seen_labels and
                        not label.isdigit() and
                        'http' not in label.lower()):

                        data.append({
                            'label': label,
                            'value': value,
                            'unit': unit
                        })
                        seen_labels.add(label.lower())
                except (ValueError, IndexError):
                    continue

        if len(data) >= 2:
            return {
                'data': data[:15], # Increased limit
                'type': 'general_numerical',
                'confidence': 0.6 # Slightly higher confidence for stricter patterns
            }
        return None
    def _clean_label(self, label: str) -> str:
        """Enhanced label cleaning"""
        if not label:
            return ""
        # Remove HTML/markdown formatting
        label = re.sub(r'<[^>]+>', '', label)
        label = re.sub(r'\*\*([^*]+)\*\*', r'\1', label)
        label = re.sub(r'\*([^*]+)\*', r'\1', label)
        # Remove bullet markers and extra characters
        label = label.strip().strip('*-•:').strip()
        # Remove common prefixes
        label = re.sub(r'^(the\s+|a\s+)', '', label, flags=re.IGNORECASE)
        # Clean up extra whitespace
        label = re.sub(r'\s+', ' ', label).strip()
        # Handle very long labels
        if len(label) > 40:
            words = label.split()
            if len(words) > 4:
                label = ' '.join(words[:4]) + "..."
            else:
                label = label[:37] + "..."
        return label

    def _calculate_quality_score(self, result: Dict) -> float:
        """Calculate quality score for extracted data"""
        if not result or not result.get('data'):
            return 0.0
        data = result['data']
        base_confidence = result.get('confidence', 0.5)
        count_factor = min(len(data) / 5.0, 1.0)
        avg_label_length = sum(len(item['label']) for item in data) / len(data)
        label_factor = min(avg_label_length / 20.0, 1.0)
        values = [item['value'] for item in data]
        if values:
            max_val = max(values)
            min_val = min(values)
            diversity_factor = min((max_val / min_val) / 10.0, 1.0) if min_val > 0 else 0.5
        else:
            diversity_factor = 0.0
        final_score = base_confidence * 0.5 + count_factor * 0.2 + label_factor * 0.2 + diversity_factor * 0.1
        return min(final_score, 1.0)

