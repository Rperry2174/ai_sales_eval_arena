"""Interactive visualization engine for tournament results and analytics."""

import logging
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio

from .models import (
    Tournament, TournamentStandings, Participant, Match, 
    Grade, CriterionGrade, VisualizationConfig
)

logger = logging.getLogger(__name__)


class TournamentVisualizer:
    """Creates stunning visualizations for tournament results."""
    
    def __init__(self, config: VisualizationConfig):
        """Initialize visualizer with configuration."""
        self.config = config
        
        # Set default plotly template
        pio.templates.default = config.theme
        
        # Custom color palette
        self.colors = {
            "primary": "#1f77b4",
            "secondary": "#ff7f0e", 
            "success": "#2ca02c",
            "danger": "#d62728",
            "warning": "#ff7f0e",
            "info": "#17a2b8",
            "light": "#f8f9fa",
            "dark": "#343a40"
        }
        
        # Update colors with config
        if config.color_scheme:
            for i, color in enumerate(config.color_scheme):
                if i < len(self.colors):
                    list(self.colors.values())[i] = color

    def create_leaderboard_chart(
        self, 
        tournament: Tournament,
        title: Optional[str] = None
    ) -> go.Figure:
        """Create an interactive leaderboard chart."""
        if not title:
            title = f"{tournament.name} - Leaderboard"
        
        # Prepare data
        standings_data = []
        participant_names = {p.id: p.name for p in tournament.participants}
        
        for standing in tournament.standings:
            participant_name = participant_names.get(standing.participant_id, "Unknown")
            standings_data.append({
                "name": participant_name,
                "rank": standing.rank,
                "wins": standing.wins,
                "losses": standing.losses,
                "win_percentage": standing.win_percentage,
                "average_score": standing.average_score,
                "total_matches": standing.total_matches
            })
        
        df = pd.DataFrame(standings_data)
        
        # Create the figure
        fig = go.Figure()
        
        # Add bars for wins
        fig.add_trace(go.Bar(
            name="Wins",
            x=df["name"],
            y=df["wins"],
            marker_color=self.colors["success"],
            text=df["wins"],
            textposition="inside",
            hovertemplate="<b>%{x}</b><br>Wins: %{y}<br>Win Rate: %{customdata:.1f}%<extra></extra>",
            customdata=df["win_percentage"]
        ))
        
        # Add bars for losses
        fig.add_trace(go.Bar(
            name="Losses",
            x=df["name"],
            y=df["losses"],
            marker_color=self.colors["danger"],
            text=df["losses"],
            textposition="inside",
            hovertemplate="<b>%{x}</b><br>Losses: %{y}<br>Total Matches: %{customdata}<extra></extra>",
            customdata=df["total_matches"]
        ))
        
        # Update layout
        fig.update_layout(
            title={
                "text": title,
                "x": 0.5,
                "font": {"size": 24, "family": self.config.font_family}
            },
            xaxis={
                "title": "Participants",
                "tickangle": -45
            },
            yaxis={
                "title": "Number of Matches"
            },
            barmode="group",
            showlegend=True,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
            width=self.config.width,
            height=self.config.height,
            font={"family": self.config.font_family}
        )
        
        return fig

    def create_performance_radar_chart(
        self, 
        tournament: Tournament,
        participant_limit: int = 6
    ) -> go.Figure:
        """Create a radar chart showing participant performance across criteria."""
        # Get individual grades for analysis
        participant_grades = self._collect_participant_grades(tournament)
        
        # Limit to top performers for readability
        top_participants = sorted(
            tournament.standings, 
            key=lambda s: s.average_score, 
            reverse=True
        )[:participant_limit]
        
        participant_names = {p.id: p.name for p in tournament.participants}
        
        fig = go.Figure()
        
        criteria_names = [
            "ICP Alignment",
            "PBO Messaging", 
            "Profiling Explanation",
            "Observability Context",
            "Talk Track Alignment"
        ]
        
        for i, standing in enumerate(top_participants):
            participant_id = standing.participant_id
            participant_name = participant_names.get(participant_id, "Unknown")
            
            if participant_id in participant_grades:
                grades = participant_grades[participant_id]
                
                # Calculate average score for each criterion
                criterion_averages = []
                for criterion in ["icp_alignment", "pbo_messaging", "profiling_explanation", 
                                "observability_context", "talk_track_alignment"]:
                    scores = [g.score for g in grades if g.criterion.value == criterion]
                    avg_score = sum(scores) / len(scores) if scores else 0
                    criterion_averages.append(avg_score)
                
                # Close the radar chart
                criterion_averages.append(criterion_averages[0])
                criteria_display = criteria_names + [criteria_names[0]]
                
                fig.add_trace(go.Scatterpolar(
                    r=criterion_averages,
                    theta=criteria_display,
                    fill='toself',
                    name=participant_name,
                    line_color=self.config.color_scheme[i % len(self.config.color_scheme)],
                    hovertemplate="<b>%{fullData.name}</b><br>%{theta}: %{r:.2f}<extra></extra>"
                ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[1, 4],
                    tickvals=[1, 2, 3, 4],
                    ticktext=["Needs Improvement", "Good", "Very Good", "Excellent"]
                )),
            showlegend=True,
            title={
                "text": f"{tournament.name} - Performance Analysis",
                "x": 0.5,
                "font": {"size": 24, "family": self.config.font_family}
            },
            width=self.config.width,
            height=self.config.height,
            font={"family": self.config.font_family}
        )
        
        return fig

    def create_tournament_bracket(self, tournament: Tournament) -> go.Figure:
        """Create a tournament bracket visualization."""
        if tournament.format.value == "round_robin":
            return self._create_round_robin_matrix(tournament)
        else:
            return self._create_elimination_bracket(tournament)

    def _create_round_robin_matrix(self, tournament: Tournament) -> go.Figure:
        """Create a match results matrix for round-robin tournament."""
        participant_names = {p.id: p.name for p in tournament.participants}
        n_participants = len(tournament.participants)
        
        # Create matrix
        matrix = [[0 for _ in range(n_participants)] for _ in range(n_participants)]
        hover_text = [["" for _ in range(n_participants)] for _ in range(n_participants)]
        
        participant_list = list(tournament.participants)
        participant_indices = {p.id: i for i, p in enumerate(participant_list)}
        
        # Fill matrix with match results
        for match in tournament.matches:
            if match.status.value == "completed" and match.winner_id:
                p1_idx = participant_indices[match.participant1_id]
                p2_idx = participant_indices[match.participant2_id]
                
                p1_name = participant_names[match.participant1_id]
                p2_name = participant_names[match.participant2_id]
                
                if match.winner_id == match.participant1_id:
                    matrix[p1_idx][p2_idx] = 1  # Win
                    matrix[p2_idx][p1_idx] = -1  # Loss
                else:
                    matrix[p1_idx][p2_idx] = -1  # Loss
                    matrix[p2_idx][p1_idx] = 1  # Win
                
                hover_text[p1_idx][p2_idx] = f"{p1_name} vs {p2_name}"
                hover_text[p2_idx][p1_idx] = f"{p2_name} vs {p1_name}"
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=[participant_names[p.id] for p in participant_list],
            y=[participant_names[p.id] for p in participant_list],
            text=hover_text,
            colorscale=[[0, self.colors["danger"]], [0.5, "white"], [1, self.colors["success"]]],
            zmid=0,
            showscale=False,
            hovertemplate="<b>%{text}</b><br>Result: %{z}<extra></extra>"
        ))
        
        fig.update_layout(
            title={
                "text": f"{tournament.name} - Match Results Matrix",
                "x": 0.5,
                "font": {"size": 24, "family": self.config.font_family}
            },
            xaxis={"title": "Opponent", "side": "top"},
            yaxis={"title": "Participant"},
            width=self.config.width,
            height=self.config.height,
            font={"family": self.config.font_family}
        )
        
        return fig

    def _create_elimination_bracket(self, tournament: Tournament) -> go.Figure:
        """Create an elimination bracket visualization."""
        # This is a simplified bracket visualization
        # For a complete bracket, you'd need more sophisticated layout algorithms
        
        fig = go.Figure()
        
        participant_names = {p.id: p.name for p in tournament.participants}
        
        # Group matches by round
        rounds = {}
        for match in tournament.matches:
            # Simple round detection based on creation time or match ID patterns
            round_num = 1  # Simplified - would need better round detection
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(match)
        
        # Draw matches
        y_positions = list(range(len(tournament.matches)))
        
        for i, match in enumerate(tournament.matches):
            p1_name = participant_names.get(match.participant1_id, "Unknown")
            p2_name = participant_names.get(match.participant2_id, "Unknown")
            
            winner_name = ""
            if match.winner_id:
                winner_name = participant_names.get(match.winner_id, "Unknown")
            
            # Add match visualization
            fig.add_trace(go.Scatter(
                x=[0, 1],
                y=[y_positions[i], y_positions[i]],
                mode="lines+text",
                line=dict(color=self.colors["primary"], width=3),
                text=[p1_name, p2_name],
                textposition="middle center",
                name=f"Match {i+1}",
                hovertemplate=f"<b>{p1_name} vs {p2_name}</b><br>Winner: {winner_name}<extra></extra>",
                showlegend=False
            ))
        
        fig.update_layout(
            title={
                "text": f"{tournament.name} - Tournament Bracket",
                "x": 0.5,
                "font": {"size": 24, "family": self.config.font_family}
            },
            xaxis={"showticklabels": False, "showgrid": False},
            yaxis={"showticklabels": False, "showgrid": False},
            width=self.config.width,
            height=self.config.height,
            font={"family": self.config.font_family}
        )
        
        return fig

    def create_score_distribution(self, tournament: Tournament) -> go.Figure:
        """Create a score distribution visualization."""
        participant_grades = self._collect_participant_grades(tournament)
        participant_names = {p.id: p.name for p in tournament.participants}
        
        fig = make_subplots(
            rows=2, cols=3,
            subplot_titles=[
                "ICP Alignment", "PBO Messaging", "Profiling Explanation",
                "Observability Context", "Talk Track Alignment", "Overall Scores"
            ],
            specs=[[{"type": "histogram"} for _ in range(3)] for _ in range(2)]
        )
        
        criteria = ["icp_alignment", "pbo_messaging", "profiling_explanation", 
                   "observability_context", "talk_track_alignment"]
        
        positions = [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2)]
        
        # Add histograms for each criterion
        for i, criterion in enumerate(criteria):
            scores = []
            for participant_id, grades in participant_grades.items():
                criterion_scores = [g.score for g in grades if g.criterion.value == criterion]
                scores.extend(criterion_scores)
            
            row, col = positions[i]
            fig.add_trace(
                go.Histogram(
                    x=scores,
                    nbinsx=8,
                    marker_color=self.config.color_scheme[i % len(self.config.color_scheme)],
                    showlegend=False
                ),
                row=row, col=col
            )
        
        # Add overall scores
        overall_scores = []
        for standing in tournament.standings:
            overall_scores.append(standing.average_score)
        
        fig.add_trace(
            go.Histogram(
                x=overall_scores,
                nbinsx=8,
                marker_color=self.colors["primary"],
                showlegend=False
            ),
            row=2, col=3
        )
        
        fig.update_layout(
            title={
                "text": f"{tournament.name} - Score Distributions",
                "x": 0.5,
                "font": {"size": 24, "family": self.config.font_family}
            },
            width=self.config.width,
            height=self.config.height,
            font={"family": self.config.font_family}
        )
        
        return fig

    def create_improvement_insights(self, tournament: Tournament) -> go.Figure:
        """Create insights visualization for improvement opportunities."""
        participant_grades = self._collect_participant_grades(tournament)
        participant_names = {p.id: p.name for p in tournament.participants}
        
        # Calculate average scores per criterion per participant
        insights_data = []
        
        for participant_id, grades in participant_grades.items():
            participant_name = participant_names.get(participant_id, "Unknown")
            
            for criterion in ["icp_alignment", "pbo_messaging", "profiling_explanation", 
                            "observability_context", "talk_track_alignment"]:
                scores = [g.score for g in grades if g.criterion.value == criterion]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    insights_data.append({
                        "participant": participant_name,
                        "criterion": criterion.replace("_", " ").title(),
                        "score": avg_score,
                        "improvement_needed": 4 - avg_score
                    })
        
        df = pd.DataFrame(insights_data)
        
        # Create bubble chart
        fig = px.scatter(
            df, 
            x="criterion", 
            y="participant",
            size="improvement_needed",
            color="score",
            color_continuous_scale="RdYlGn",
            size_max=40,
            title=f"{tournament.name} - Improvement Opportunities"
        )
        
        fig.update_layout(
            title={
                "x": 0.5,
                "font": {"size": 24, "family": self.config.font_family}
            },
            xaxis={"title": "Evaluation Criteria", "tickangle": -45},
            yaxis={"title": "Participants"},
            coloraxis_colorbar={"title": "Score"},
            width=self.config.width,
            height=self.config.height,
            font={"family": self.config.font_family}
        )
        
        return fig

    def create_dashboard(self, tournament: Tournament) -> go.Figure:
        """Create a comprehensive dashboard combining multiple visualizations."""
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[
                "Leaderboard", "Performance Radar", 
                "Score Distribution", "Match Results"
            ],
            specs=[
                [{"type": "bar"}, {"type": "scatterpolar"}],
                [{"type": "histogram"}, {"type": "heatmap"}]
            ]
        )
        
        # Add simplified versions of each chart type
        # (This would be more complex in a real implementation)
        
        fig.update_layout(
            title={
                "text": f"{tournament.name} - Tournament Dashboard",
                "x": 0.5,
                "font": {"size": 28, "family": self.config.font_family}
            },
            width=self.config.width * 1.5,
            height=self.config.height * 1.2,
            font={"family": self.config.font_family}
        )
        
        return fig

    def export_visualizations(
        self, 
        tournament: Tournament, 
        output_dir: Path,
        formats: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """Export all visualizations in specified formats."""
        if formats is None:
            formats = self.config.export_formats
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exported_files = {}
        
        # Generate all visualizations
        visualizations = {
            "leaderboard": self.create_leaderboard_chart(tournament),
            "performance_radar": self.create_performance_radar_chart(tournament),
            "tournament_bracket": self.create_tournament_bracket(tournament),
            "score_distribution": self.create_score_distribution(tournament),
            "improvement_insights": self.create_improvement_insights(tournament),
            "dashboard": self.create_dashboard(tournament)
        }
        
        # Export each visualization in each format
        for viz_name, fig in visualizations.items():
            exported_files[viz_name] = []
            
            for format_type in formats:
                filename = f"{tournament.name}_{viz_name}.{format_type}"
                filepath = output_dir / filename
                
                try:
                    if format_type == "html":
                        fig.write_html(str(filepath))
                    elif format_type == "png":
                        fig.write_image(str(filepath), engine="kaleido")
                    elif format_type == "pdf":
                        fig.write_image(str(filepath), engine="kaleido")
                    elif format_type == "svg":
                        fig.write_image(str(filepath), engine="kaleido")
                    elif format_type == "json":
                        fig.write_json(str(filepath))
                    
                    exported_files[viz_name].append(str(filepath))
                    logger.info(f"Exported {viz_name} as {format_type}: {filepath}")
                    
                except Exception as e:
                    logger.error(f"Failed to export {viz_name} as {format_type}: {e}")
        
        return exported_files

    def _collect_participant_grades(self, tournament: Tournament) -> Dict[Any, List[CriterionGrade]]:
        """Collect all grades by participant for analysis."""
        participant_grades = {}
        
        for match in tournament.matches:
            if match.grade1:
                participant_id = match.participant1_id
                if participant_id not in participant_grades:
                    participant_grades[participant_id] = []
                participant_grades[participant_id].extend(match.grade1.criterion_grades)
            
            if match.grade2:
                participant_id = match.participant2_id
                if participant_id not in participant_grades:
                    participant_grades[participant_id] = []
                participant_grades[participant_id].extend(match.grade2.criterion_grades)
        
        return participant_grades


class VisualizationExporter:
    """Handles exporting visualizations for different use cases."""
    
    @staticmethod
    def create_blog_ready_exports(
        tournament: Tournament,
        output_dir: Path,
        config: VisualizationConfig
    ) -> Dict[str, str]:
        """Create blog-ready exports with optimal settings."""
        visualizer = TournamentVisualizer(config)
        
        # Create high-quality exports for blog
        blog_config = VisualizationConfig(
            width=1200,
            height=800,
            theme="plotly_white",
            export_formats=["html", "png"]
        )
        visualizer.config = blog_config
        
        exported = visualizer.export_visualizations(
            tournament, 
            output_dir,
            formats=["html", "png"]
        )
        
        # Return the main files for blog embedding
        return {
            "leaderboard_html": exported.get("leaderboard", [""])[0],
            "radar_html": exported.get("performance_radar", [""])[1] if len(exported.get("performance_radar", [])) > 1 else "",
            "dashboard_png": exported.get("dashboard", [""])[1] if len(exported.get("dashboard", [])) > 1 else ""
        } 