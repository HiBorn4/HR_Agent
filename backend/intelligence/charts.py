import logging
from typing import List, Dict, Tuple, Optional
import seaborn as sns
import matplotlib.pyplot as plt
import io
import base64
import numpy as np

class MahindraChartGenerator:
    """Server-side chart generation with Mahindra red theme using matplotlib"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Mahindra color palette with reds
        self.colors = ['#C8102E', '#A00D26', '#D1242F', '#B01E2F', '#E6394A', '#FF6B7D', '#CC0000', '#990000']
        self.palette = sns.color_palette(self.colors)

    def generate_chart(self, data: List[Dict], chart_type: str = 'auto', title: str = None) -> str:
        """Generate chart with Mahindra theme"""
        try:
            if chart_type == 'auto':
                chart_type = self._intelligent_chart_selection(data)
            labels = [item['label'] for item in data]
            values = [item['value'] for item in data]
            
            plt.style.use('dark_background')
            # Increase figure size to accommodate legends if needed
            fig, ax = plt.subplots(figsize=(12, 7), facecolor='#1a1a1a')
            ax.set_facecolor='#1a1a1a'
            
            # Route to specific chart generation method
            chart_methods = {
                'bar': self._generate_bar_chart,
                'horizontal_bar': self._generate_horizontal_bar_chart,
                'pie': self._generate_pie_chart,
                'donut': self._generate_donut_chart,
                'line': self._generate_line_chart,
                'area': self._generate_area_chart,
                'scatter': self._generate_scatter_chart
            }
            if chart_type in chart_methods:
                chart_methods[chart_type](ax, labels, values, title)
            else:
                self._generate_bar_chart(ax, labels, values, title)
            
            # Save to base64
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', bbox_inches='tight',
                        facecolor='#1a1a1a', edgecolor='none', dpi=150)
            img_buffer.seek(0)
            img_str = base64.b64encode(img_buffer.getvalue()).decode()
            plt.close()
            return img_str
        except Exception as e:
            self.logger.error(f"Chart generation failed: {e}")
            return None

    def _intelligent_chart_selection(self, data: List[Dict]) -> str:
        """AI-powered chart type selection"""
        data_count = len(data)
        values = [item['value'] for item in data]
        labels = [item['label'] for item in data]
        
        has_percentages = any('%' in item.get('unit', '') for item in data)
        has_time_series = any(any(keyword in label.lower() for keyword in ['month', 'year', 'quarter', 'week', 'day']) for label in labels)
        
        if has_percentages and data_count <= 8:
            return 'donut'
        elif has_time_series:
            return 'area'
        elif data_count > 8: 
            return 'horizontal_bar' # Horizontal bar is best for many categories
        elif data_count <= 6:
            return 'donut'
        else:
            return 'bar'

    def _generate_bar_chart(self, ax, labels, values, title):
        colors = [self.colors[i % len(self.colors)] for i in range(len(labels))]
        bars = ax.bar(labels, values, color=colors, alpha=0.9, edgecolor='white', linewidth=0.5)
        self._apply_common_styling(ax, title, 'Values')
        self._add_value_labels(ax, bars, values, 'vertical')
        if len(labels) > 4:
            plt.xticks(rotation=45, ha='right')

    def _generate_horizontal_bar_chart(self, ax, labels, values, title):
        colors = [self.colors[i % len(self.colors)] for i in range(len(labels))]
        # Sort for better readability (Top items on top)
        zipped = sorted(zip(values, labels, colors), key=lambda x: x[0])
        values, labels, colors = zip(*zipped)
        
        bars = ax.barh(labels, values, color=colors, alpha=0.9, edgecolor='white', linewidth=0.5)
        self._apply_common_styling(ax, title, 'Values')
        self._add_value_labels(ax, bars, values, 'horizontal')

    def _generate_pie_chart(self, ax, labels, values, title):
        self._generate_circular_chart(ax, labels, values, title, is_donut=False)

    def _generate_donut_chart(self, ax, labels, values, title):
        self._generate_circular_chart(ax, labels, values, title, is_donut=True)

    def _generate_circular_chart(self, ax, labels, values, title, is_donut=True):
        """Unified logic for Pie/Donut with smart legend handling"""
        colors = [self.colors[i % len(self.colors)] for i in range(len(labels))]
        
        # SMART LEGEND LOGIC: If many slices, don't label slices directly
        use_legend = len(labels) > 5
        slice_labels = None if use_legend else labels
        
        # Calculate percentages for autopct
        total = sum(values)
        def make_autopct(pct):
            # Only show % if slice is big enough to hold text
            return f'{pct:.1f}%' if pct > 3 else ''

        wedges, texts, autotexts = ax.pie(
            values, 
            labels=slice_labels, 
            autopct=make_autopct,
            colors=colors, 
            startangle=45, 
            pctdistance=0.85 if is_donut else 0.6,
            explode=[0.05] * len(values) if len(values) < 10 else None, # Explode only if few items
            wedgeprops=dict(width=0.5, edgecolor='white', linewidth=1) if is_donut else dict(edgecolor='white', linewidth=1),
            textprops={'color': 'white', 'fontsize': 10}
        )

        if is_donut:
            # Add center circle and text
            centre_circle = plt.Circle((0, 0), 0.70, fc='#1a1a1a', ec='none')
            ax.add_artist(centre_circle)
            ax.text(0, 0, f'Total\n{int(total):,}', ha='center', va='center', fontsize=12, color='white', fontweight='bold')

        ax.set_title(title or 'Distribution', color='white', fontsize=16, fontweight='bold', pad=20)

        # Style percentage text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(9)
        
        # Style label text (if not using legend)
        if not use_legend:
            for text in texts:
                text.set_color('white')
        else:
            # Create a nice side legend
            ax.legend(
                wedges, 
                [f"{l} ({v:,})" for l, v in zip(labels, values)],
                title="Sectors",
                loc="center left",
                bbox_to_anchor=(1, 0, 0.5, 1),
                frameon=False,
                labelcolor='white'
            )

    def _generate_line_chart(self, ax, labels, values, title):
        ax.plot(labels, values, marker='o', linewidth=3, markersize=8, color='#C8102E')
        self._apply_common_styling(ax, title, 'Values')
        if len(labels) > 6: plt.xticks(rotation=45, ha='right')

    def _generate_area_chart(self, ax, labels, values, title):
        x_pos = range(len(labels))
        ax.fill_between(x_pos, values, alpha=0.6, color='#C8102E')
        ax.plot(x_pos, values, color='#ff9999', linewidth=2)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels)
        self._apply_common_styling(ax, title, 'Values')
        if len(labels) > 6: plt.xticks(rotation=45, ha='right')

    def _generate_scatter_chart(self, ax, labels, values, title):
        x_pos = range(len(labels))
        sizes = [(v / max(values) * 1000) + 50 for v in values]
        ax.scatter(x_pos, values, s=sizes, c=values, cmap='Reds', alpha=0.8, edgecolors='white')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels)
        self._apply_common_styling(ax, title, 'Values')
        if len(labels) > 6: plt.xticks(rotation=45, ha='right')

    def _apply_common_styling(self, ax, title, ylabel):
        ax.set_title(title or 'Analysis', color='white', fontsize=16, fontweight='bold', pad=20)
        ax.set_ylabel(ylabel, color='white', fontsize=12)
        ax.tick_params(colors='white', which='both')
        ax.grid(True, alpha=0.2, color='white', linestyle='--')
        for spine in ax.spines.values():
            spine.set_color('white')
            spine.set_alpha(0.3)

    def _add_value_labels(self, ax, bars, values, orientation):
        for bar, value in zip(bars, values):
            if orientation == 'vertical':
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{value:,}', ha='center', va='bottom', color='white', fontsize=9, fontweight='bold')
            else:
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2.,
                        f' {value:,}', ha='left', va='center', color='white', fontsize=9, fontweight='bold')