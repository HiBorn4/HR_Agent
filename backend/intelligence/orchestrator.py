import logging
from typing import List, Dict, Optional, Union
import html
from datetime import datetime
import traceback

from intelligence.extractor import MahindraDataExtractor
from intelligence.engine import MahindraIntelligenceEngine
from intelligence.charts import MahindraChartGenerator
from intelligence.ploty import MahindraPlotlyGenerator


class MahindraInsightOrchestrator:
    """Orchestrator with Mahindra theme and collapsible sections"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.extractor = MahindraDataExtractor()
        self.matplotlib_gen = MahindraChartGenerator()
        self.plotly_gen = MahindraPlotlyGenerator()
        self.intelligence = MahindraIntelligenceEngine()

    def _is_data_chartable(self, data: List[Dict], text: str) -> bool:
        """Checks if the extracted data is high-quality enough to be charted."""
        negative_keywords = [
            "no data found", "no attrition data", "unable to retrieve",
            "no results", "cannot be generated", "returned no results",
            "unable to find", "could not find", "i cannot provide",
            "information is not available", "data is unavailable",
            "failed to retrieve", "i'm sorry, but i cannot answer"
        ]

        if any(keyword in text.lower() for keyword in negative_keywords):
            self.logger.info("Insight generation skipped: Negative keywords detected in response text.")
            return False

        if not data or len(data) < 2:
            self.logger.warning("Data not chartable: Less than 2 data points found.")
            return False

        valid_values = {item.get('value') for item in data if isinstance(item.get('value'), (int, float))}

        if not valid_values:
            self.logger.warning("Data not chartable: No valid numerical values found.")
            return False

        if len(valid_values) == 1:
            self.logger.warning("Data not chartable: All extracted numerical values are identical.")
            return False

        junk_labels = [
            'result', 'there are', 'the count is', 'total is', 'query returned',
            'includes', 'explanation', 'identified', 'limiting the output',
            'no data', 'not found', 'error', 'failed', 'within the year', 'consequently'
        ]

        for item in data:
            label_lower = str(item.get('label', '')).lower()
            if any(junk in label_lower for junk in junk_labels):
                self.logger.warning(f"Data not chartable: Found junk keyword in label '{item.get('label', 'N/A')}'.")
                return False

        avg_label_length = sum(len(str(item.get('label', ''))) for item in data) / len(data)
        if avg_label_length < 3:
            self.logger.warning(f"Data not chartable: Average label length ({avg_label_length:.1f}) is too short.")
            return False

        return True

    def _convert_table_to_data_points(self, tables: List[Dict]) -> List[Dict]:
        """
        Fast heuristic: Converts pre-parsed tables (list of row dicts)
        directly into the {label, value} format expected by the charter.
        """
        if not tables or not isinstance(tables, list):
            return []

        # Use the first row to detect column types
        sample_row = tables[0]
        keys = list(sample_row.keys())
        
        numeric_keys = []
        string_keys = []
        
        for k, v in sample_row.items():
            if isinstance(v, (int, float)):
                numeric_keys.append(k)
            elif isinstance(v, str):
                string_keys.append(k)
                
        label_key = None
        value_key = None
        
        # Scenario A: Standard Categorical (e.g. Region [str] | Sales [num])
        if string_keys and numeric_keys:
            label_key = string_keys[0] 
            value_key = numeric_keys[0]
            
        # Scenario B: Numeric Time Series (e.g. Year [int] | Sales [int]) 
        elif len(numeric_keys) >= 2 and not string_keys:
            label_key = keys[0] 
            value_key = keys[1] if keys[1] != label_key else (numeric_keys[1] if len(numeric_keys) > 1 else None)

        if not label_key or not value_key:
            return []

        data_points = []
        for row in tables:
            if label_key not in row or value_key not in row: 
                continue
            
            val = row[value_key]
            lbl = row[label_key]
            
            # Ensure value is float/int
            if not isinstance(val, (int, float)):
                try: val = float(val)
                except: continue
                
            data_points.append({
                "label": str(lbl), 
                "value": val,
                "unit": ""
            })
        
        return data_points

    async def generate_insights_from_text(
        self,
        text: str,
        ui_card_id: str,
        debug_mode: bool = False,
        query: str = "",
        pre_parsed_tables: List[Dict] = None
    ) -> Optional[Dict]:

        negative_keywords = [
            "no data found", "no attrition data", "unable to retrieve",
            "no results", "cannot be generated", "returned no results"
        ]

        if any(keyword in text.lower() for keyword in negative_keywords):
            return None

        try:
            data = None

            # -------------------------------------------------
            # 1️⃣ FAST TABLE OPTIMIZATION PATH
            # -------------------------------------------------
            if pre_parsed_tables:
                self.logger.info("🚀 Using pre-parsed tables...")
                data = self._convert_table_to_data_points(pre_parsed_tables)

            if not data:
                if not self.extractor._needs_visualization(text):
                    self.logger.info("⛔ Skipping extractor — no visualization needed.")
                    return None

                extraction_result = await self.extractor.extract_business_data(
                    text,
                    debug_mode
                )

                if extraction_result and extraction_result.get("data"):
                    data = extraction_result["data"]
                if extraction_result and extraction_result.get("data"):
                    data = extraction_result["data"]

            if not data or len(data) < 2:
                return None

            # -------------------------------------------------
            # 3️⃣ INTELLIGENCE ENGINE DECISION
            # -------------------------------------------------
            intent = self.intelligence.detect_insight_intent(query, text)

            # 🔥 THIS IS THE CRITICAL FIX
            if not intent.get("should_visualize"):
                self.logger.info(
                    f"Visualization skipped: {intent.get('trigger_reason')}"
                )
                return None

            # -------------------------------------------------
            # 4️⃣ SORT & RECOMMEND
            # -------------------------------------------------
            sorted_data = sorted(data, key=lambda x: x["value"], reverse=True)

            recommendations = self.intelligence.get_chart_recommendations(
                sorted_data,
                intent,
                query
            )

            primary_chart_type = recommendations[0] if recommendations else "bar"

            title = self.intelligence.generate_title(
                sorted_data,
                intent,
                query,
                primary_chart_type
            )

            # -------------------------------------------------
            # 5️⃣ GENERATE INTERACTIVE CHART
            # -------------------------------------------------
            interactive_chart_html = self.plotly_gen.generate_plotly_chart(
                sorted_data,
                primary_chart_type,
                title=title,
                palette="vibrant_mix"
            )

            if interactive_chart_html:
                return {
                    "plotly_html": interactive_chart_html,
                    "chart_type": primary_chart_type,
                    "data_points": sorted_data,
                    "intent": intent,
                    "summary": f"Generated interactive {primary_chart_type}"
                }

            # -------------------------------------------------
            # 6️⃣ FALLBACK STATIC IMAGE
            # -------------------------------------------------
            static_image_base64 = self.matplotlib_gen.generate_chart(
                sorted_data,
                primary_chart_type,
                title=title
            )

            if static_image_base64:
                return {
                    "image_base64": static_image_base64,
                    "chart_type": primary_chart_type,
                    "data_points": sorted_data,
                    "intent": intent,
                    "summary": f"Generated static {primary_chart_type}"
                }

            return None

        except Exception as e:
            self.logger.error(f"Insight generation failed: {e}")
            return None