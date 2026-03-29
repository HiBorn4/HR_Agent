
import logging
from typing import List, Dict
import re

intent_title_map = {
    'performance_analysis': "Performance Analysis", 'business_distribution': "Distribution Analysis",
    'growth_trends': "Trend Analysis", 'ranking': "Rankings", 'summary': "Summary Overview"
}
context_title_map = {
    'department': "Department", 'division': "Division", 'employee': "Workforce",
    'staff': "Workforce", 'tenure': "Experience", 'year': "Experience",
    'revenue': "Financial", 'financial': "Financial"
}

class MahindraIntelligenceEngine:
    """
    🚗 MAHINDRA RISE: Auto-Intelligence engine with essential chart types
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.insight_keywords = {
            'direct_request': ['chart', 'graph', 'plot', 'visualize', 'show chart', 'display chart', 'visualization'],
            'performance_analysis': ['compare', 'vs', 'versus', 'difference', 'between', 'against', 'contrast'],
            'business_distribution': ['breakdown', 'distribution', 'share', 'composition', 'proportion', 'split'],
            'growth_trends': ['trend', 'over time', 'progression', 'change', 'timeline', 'history', 'evolution'],
            'ranking': ['top', 'bottom', 'highest', 'lowest', 'best', 'worst', 'ranking', 'ranked'],
            'summary': ['average', 'total', 'sum', 'overall', 'aggregate', 'summary'],
            'analysis': ['analyze', 'analysis', 'insights', 'findings', 'results', 'data'],
            'query_indicators': ['what', 'how', 'which', 'where', 'when', 'who', 'show', 'tell']
        }
        # Simplified to essential chart types
        self.chart_types = {
            'auto': 'Smart Selection',
            'bar': 'Bar Chart',
            'horizontal_bar': 'Horizontal Bar Chart',
            'pie': 'Pie Chart',
            'donut': 'Donut Chart',
            'line': 'Line Chart',
            'area': 'Area Chart',
            'scatter': 'Scatter Plot'
        }

    def detect_insight_intent(self, query: str, response: str) -> Dict:
        """
        🧠 Intent detection with chart type recommendations
        """
        query_lower = query.lower()
        response_lower = response.lower()
        intent_scores = {}
        total_keywords = 0
        # Score each intent category
        for intent, keywords in self.insight_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in query_lower:
                    score += 2 # Query keywords weighted higher
                if keyword in response_lower:
                    score += 1
                total_keywords += 1
            intent_scores[intent] = score
        # Determine if we should auto-visualize
        max_score = max(intent_scores.values()) if intent_scores else 0
        # Enhanced patterns for business data
        business_viz_patterns = [
            r'\d+\.?\d*\s*(years?|employees?|%|percent|million|billion)',
            r'[A-Za-z\s\-&()]+:\s*\d+\.?\d*',
            r'-\s*[A-Za-z\s\-&()]+:\s*\d+\.?\d*',
            r'\*\s*[A-Za-z\s\-&()]+:\s*\d+\.?\d*',
            r'Department[^0-9]*\d+',
            r'Division[^0-9]*\d+',
            r'average|mean|total|sum|count'
        ]
        has_business_patterns = any(re.search(pattern, response, re.IGNORECASE) for pattern in business_viz_patterns)
        # Question indicators that suggest data analysis
        business_indicators = any(word in query_lower for word in ['what', 'how', 'show', 'tell', 'which'])
        # Auto-visualize if conditions met
        should_visualize = (
                max_score >= 2 or
                (has_business_patterns and business_indicators) or
                (max_score >= 1 and has_business_patterns)
        )
        return {
            'should_visualize': should_visualize,
            'intent_scores': intent_scores,
            'primary_intent': max(intent_scores, key=intent_scores.get) if intent_scores else 'analysis',
            'confidence': min(max_score / 5.0, 1.0), # Normalize to 0-1
            'has_business_patterns': has_business_patterns,
            'has_business_queries': business_indicators,
            'trigger_reason': self._get_trigger_reason(max_score, has_business_patterns, business_indicators)
        }

    def get_chart_recommendations(self, data: List[Dict], intent: Dict, query: str) -> List[str]:
        """
        🎯 Chart type recommendations based on data and intent
        """
        data_count = len(data)
        values = [item['value'] for item in data]
        labels = [item['label'] for item in data]
        primary_intent = intent['primary_intent']
        # Analysis factors
        has_percentages = any('%' in item.get('unit', '') for item in data)
        has_time_data = any(any(keyword in label.lower() for keyword in ['month', 'year', 'quarter', 'week', 'day']) for label in labels)
        has_categories = any(any(keyword in label.lower() for keyword in ['department', 'division', 'category', 'type']) for label in labels)
        recommendations = []
        # Intent-based recommendations
        if primary_intent == 'performance_analysis':
            recommendations.extend(['horizontal_bar', 'bar'])
        elif primary_intent == 'business_distribution':
            recommendations.extend(['donut', 'pie'])
        elif primary_intent == 'growth_trends':
            recommendations.extend(['area', 'line'])
        elif primary_intent == 'ranking':
            recommendations.extend(['horizontal_bar', 'bar'])
        elif primary_intent == 'summary':
            recommendations.extend(['donut', 'pie'])
        # Data characteristic-based recommendations
        if has_percentages and data_count <= 8:
            recommendations.extend(['donut', 'pie'])
        elif has_time_data:
            recommendations.extend(['area', 'line'])
        elif has_categories:
            recommendations.extend(['horizontal_bar', 'bar'])
        elif data_count <= 6:
            recommendations.extend(['donut', 'pie'])
        elif data_count <= 15:
            recommendations.extend(['bar', 'horizontal_bar'])
        else:
            recommendations.extend(['horizontal_bar', 'scatter'])
        # Add scatter for correlation data
        if data_count >= 5:
            recommendations.append('scatter')
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for item in recommendations:
            if item not in seen:
                seen.add(item)
                unique_recommendations.append(item)
        # Ensure we have at least 6 options
        all_types = ['bar', 'horizontal_bar', 'donut', 'area', 'scatter', 'line', 'pie']
        for chart_type in all_types:
            if chart_type not in unique_recommendations:
                unique_recommendations.append(chart_type)
            if len(unique_recommendations) >= 6:
                break
        return unique_recommendations[:6]

    def _get_trigger_reason(self, score: float, has_patterns: bool, has_queries: bool) -> str:
        """Get reason why visualization was triggered"""
        if score >= 2:
            return "Direct visualization request detected"
        elif has_patterns and has_queries:
            return "Business query with numerical data detected"
        elif score >= 1 and has_patterns:
            return "Intent keywords + data patterns found"
        else:
            return "No auto-visualization trigger"

    def generate_title(self, data: List[Dict], intent: Dict, query: str, chart_type: str) -> str:
        """
        📝 Generate Mahindra business titles
        """
        data_count = len(data)
        primary_intent = intent['primary_intent']
        chart_name = self.chart_types.get(chart_type, 'Chart')
        # Extract key terms from query
        query_words = re.findall(r'\b[A-Za-z]{3,}\b', query.lower())
        key_terms = [word for word in query_words if word not in ['what', 'how', 'show', 'the', 'and', 'for', 'are', 'is']]
        # Chart-specific titles
        if chart_type == 'donut':
            return f"Distribution Analysis • {chart_name} ({data_count} segments)"
        elif chart_type == 'area':
            return f"Trend Analysis • {chart_name}"
        elif chart_type == 'scatter':
            return f"Data Correlation • {chart_name}"
        # Intent-based titles with chart type
        if primary_intent in intent_title_map:
            return f"{intent_title_map[primary_intent]} • {chart_name} ({data_count} items)"
        # Context-specific titles
        for term, title_part in context_title_map.items():
            if term in query.lower():
                return f"{title_part} Analysis • {chart_name} ({data_count} items)"
        # Default Mahindra title
        if key_terms:
            main_term = key_terms[0].title()
            return f"{main_term} Analysis • {chart_name} ({data_count} items)"
        else:
            return f"Intelligence Report • {chart_name} ({data_count} data points)"
