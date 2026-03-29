from typing import List, Dict, Optional
from datetime import datetime
import json
import logging

class MahindraPlotlyGenerator:
    """Enhanced Plotly.js generator with multiple vibrant themes and interactivity"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Define multiple beautiful color palettes
        self.color_palettes = {
            'mahindra_reds': ['#C8102E', '#A00D26', '#D1242F', '#B01E2F', '#E6394A', '#FF6B7D'],
            'ocean_blues': ['#0077B6', '#0096C7', '#48CAE4', '#90E0EF', '#ADE8F4', '#03045E'],
            'vibrant_mix': ['#FF595E', '#FFCA3A', '#8AC926', '#1982C4', '#6A4C93', '#F15BB5'],
            'cyberpunk': ['#00FF9F', '#00B8FF', '#001EFF', '#BD00FF', '#D600FF', '#FF0055'],
            'pastel_dreams': ['#FFB5A7', '#FCD5CE', '#F8EDEB', '#F9DCC4', '#FEC89A', '#E29578']
        }

    def generate_plotly_chart(self, data: List[Dict], chart_type: str = 'auto', title: str = None, palette: str = 'vibrant_mix') -> str:
        """Generate a highly interactive Plotly chart with custom color palettes"""
        try:
            labels = [item.get('label', f'Item {i}') for i, item in enumerate(data)]
            values = [item.get('value', 0) for item in data]
            
            if chart_type == 'auto':
                chart_type = self._intelligent_chart_selection(data)
                
            chart_id = f"interactive_chart_{int(datetime.now().timestamp() * 1000)}"
            
            # Select colors based on user choice or default
            colors = self.color_palettes.get(palette, self.color_palettes['vibrant_mix'])
            
            # Generate trace
            trace = self._generate_plotly_trace(chart_type, labels, values, colors)
            
            # Enhanced layout for a beautiful modern UI
            layout = {
                'title': {
                    'text': title or f'Interactive {chart_type.title().replace("_", " ")} Overview',
                    'font': {'color': '#E0E0E0', 'size': 20, 'family': 'Arial, sans-serif'},
                    'y': 0.95
                },
                'paper_bgcolor': 'rgba(18, 18, 18, 1)', # Sleek dark background
                'plot_bgcolor': 'rgba(18, 18, 18, 1)',
                'font': {'color': '#B0B0B0', 'family': 'Arial, sans-serif'},
                'margin': {'l': 70, 'r': 50, 't': 80, 'b': 70},
                'showlegend': True,
                'legend': {'orientation': 'h', 'y': -0.2, 'font': {'color': '#E0E0E0'}},
                'hovermode': 'closest',
                'hoverlabel': {
                    'bgcolor': 'rgba(255, 255, 255, 0.95)',
                    'font': {'color': 'black', 'size': 14},
                    'bordercolor': 'transparent'
                }
            }
            
            if chart_type not in ['pie', 'donut']:
                layout.update({
                    'xaxis': {'color': '#E0E0E0', 'gridcolor': 'rgba(255,255,255,0.05)', 'zerolinecolor': 'rgba(255,255,255,0.1)'},
                    'yaxis': {'color': '#E0E0E0', 'gridcolor': 'rgba(255,255,255,0.05)', 'zerolinecolor': 'rgba(255,255,255,0.1)'}
                })

            export_button_html = f'''
            <button onclick="Plotly.downloadImage('{chart_id}', {{format: 'png', width: 1200, height: 800, filename: '{title or "chart"}'}});"
                style="position: absolute; top: 15px; right: 15px; z-index: 100; background: {colors[0]}; color: white; border: none; border-radius: 8px; padding: 8px 15px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: 0.3s; font-family: Arial, sans-serif;">
                <i class="fas fa-download"></i> Export Chart
            </button>
            '''

            return f'''
            <div style="position: relative; width: 100%; height: 100%;">
                {export_button_html}
                <div id="{chart_id}" style="width: 100%; height: 100%; min-height: 500px; background: rgba(18,18,18,1);"></div>
            </div>
            <script>
            (function() {{
                if (typeof Plotly === 'undefined') {{
                    console.error('Plotly not loaded.');
                    return;
                }}
                const data = [{json.dumps(trace)}];
                const layout = {json.dumps(layout)};
                const config = {{
                    responsive: true,
                    displayModeBar: true, 
                    displaylogo: false,
                    modeBarButtonsToRemove: ['lasso2d', 'select2d']
                }};
                Plotly.newPlot('{chart_id}', data, layout, config);
            }})();
            </script>'''
        except Exception as e:
            self.logger.error(f"Plotly chart generation failed: {e}")
            return None

    def _intelligent_chart_selection(self, data: List[Dict]) -> str:
        data_count = len(data)
        has_percentages = any('%' in str(item.get('unit', '')) for item in data)
        if has_percentages or data_count <= 5: return 'donut'
        elif data_count <= 12: return 'bar'
        else: return 'horizontal_bar'

    def _generate_plotly_trace(self, chart_type: str, labels: List, values: List, colors: List) -> Dict:
        # Loop colors if there are more labels than colors in the palette
        extended_colors = [colors[i % len(colors)] for i in range(len(labels))]
        
        base_trace = {
            'x': labels,
            'y': values,
            'hovertemplate': '<b>%{x}</b><br>Value: %{y:,}<extra></extra>' 
        }

        if chart_type == 'bar':
            base_trace.update({
                'type': 'bar',
                'marker': {'color': extended_colors, 'line': {'color': 'rgba(255,255,255,0.2)', 'width': 1}}
            })
        elif chart_type == 'horizontal_bar':
            base_trace.update({
                'type': 'bar', 'x': values, 'y': labels, 'orientation': 'h',
                'marker': {'color': extended_colors}
            })
        elif chart_type in ['pie', 'donut']:
            return {
                'type': 'pie', 'labels': labels, 'values': values,
                'hole': 0.5 if chart_type == 'donut' else 0,
                'marker': {'colors': extended_colors, 'line': {'color': '#121212', 'width': 2}},
                'hovertemplate': '<b>%{label}</b><br>Value: %{value:,}<br>Percentage: %{percent}<extra></extra>',
                'textinfo': 'percent+label'
            }
        elif chart_type == 'line':
            base_trace.update({
                'type': 'scatter', 'mode': 'lines+markers',
                'line': {'color': colors[0], 'width': 4, 'shape': 'spline'},
                'marker': {'size': 10, 'color': 'white', 'line': {'color': colors[0], 'width': 2}}
            })
        elif chart_type == 'area':
            base_trace.update({
                'type': 'scatter', 'mode': 'lines+markers', 'fill': 'tozeroy',
                'line': {'color': colors[1], 'width': 3, 'shape': 'spline'},
                'fillcolor': f"{colors[1]}4D" 
            })
        elif chart_type == 'scatter':
            return {
                'type': 'scatter', 'mode': 'markers',
                'x': labels, 'y': values,
                'marker': {
                    'size': [(v / max(values) * 50) + 10 for v in values] if max(values) > 0 else [10] * len(values),
                    'color': values,
                    'colorscale': 'Viridis',
                    'line': {'color': 'white', 'width': 1}
                },
                'hovertemplate': '<b>%{x}</b><br>Value: %{y:,}<extra></extra>'
            }
        
        return base_trace