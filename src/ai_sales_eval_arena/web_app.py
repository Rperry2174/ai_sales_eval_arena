"""FastAPI web application for the AI Sales Evaluation Arena."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .models import (
    Tournament, TournamentFormat, Participant, Transcript, 
    ArenaConfig, VisualizationConfig
)
from .tournament import TournamentManager
from .visualization import TournamentVisualizer
from .transcript_loader import create_sample_data

logger = logging.getLogger(__name__)


# API Models
class TournamentCreateRequest(BaseModel):
    """Request model for creating a tournament."""
    name: str
    description: Optional[str] = None
    format: TournamentFormat = TournamentFormat.ROUND_ROBIN
    num_participants: int = 8
    use_sample_data: bool = True


class TournamentResponse(BaseModel):
    """Response model for tournament data."""
    id: str
    name: str
    description: Optional[str]
    format: str
    participant_count: int
    match_count: int
    completion_percentage: float
    is_completed: bool
    winner_name: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class StandingsResponse(BaseModel):
    """Response model for tournament standings."""
    participant_name: str
    rank: int
    wins: int
    losses: int
    win_percentage: float
    average_score: float
    total_matches: int


# Create FastAPI app
app = FastAPI(
    title="AI Sales Evaluation Arena",
    description="Tournament framework for evaluating sales pitch performances using AI",
    version="0.1.0"
)

# Global state
try:
    config = get_config()
    tournament_manager = TournamentManager(config)
except ValueError as e:
    print(f"Configuration Error: {e}")
    print("Please set ANTHROPIC_API_KEY in your environment or .env file")
    # Create a dummy config for development
    config = ArenaConfig(
        anthropic_api_key="dummy-key",
        anthropic_model="claude-3-5-sonnet-20241022",
        max_concurrent_matches=3
    )
    tournament_manager = TournamentManager(config)
visualizer = TournamentVisualizer(VisualizationConfig())

# Templates and static files
templates = Jinja2Templates(directory="src/ai_sales_eval_arena/templates")
app.mount("/static", StaticFiles(directory="src/ai_sales_eval_arena/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with tournament overview."""
    tournaments = tournament_manager.list_tournaments()
    tournament_data = []
    
    for tournament in tournaments:
        participant_names = {p.id: p.name for p in tournament.participants}
        winner_name = None
        if tournament.winner_id:
            winner_name = participant_names.get(tournament.winner_id, "Unknown")
        
        tournament_data.append({
            "id": str(tournament.id),
            "name": tournament.name,
            "description": tournament.description,
            "format": tournament.format.value.replace("_", " ").title(),
            "participant_count": len(tournament.participants),
            "match_count": len(tournament.matches),
            "completion_percentage": tournament.completion_percentage,
            "is_completed": tournament.is_completed,
            "winner_name": winner_name,
            "created_at": tournament.created_at.isoformat()
        })
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "tournaments": tournament_data
    })


@app.get("/tournament/{tournament_id}", response_class=HTMLResponse)
async def tournament_detail(request: Request, tournament_id: str):
    """Tournament detail page with visualizations."""
    try:
        tournament = tournament_manager.get_tournament(UUID(tournament_id))
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        # Prepare tournament data
        participant_names = {p.id: p.name for p in tournament.participants}
        
        # Prepare standings data
        standings_data = []
        for standing in tournament.standings:
            participant_name = participant_names.get(standing.participant_id, "Unknown")
            standings_data.append({
                "participant_name": participant_name,
                "rank": standing.rank,
                "wins": standing.wins,
                "losses": standing.losses,
                "win_percentage": standing.win_percentage,
                "average_score": standing.average_score,
                "total_matches": standing.total_matches
            })
        
        # Prepare match data
        matches_data = []
        for match in tournament.matches:
            p1_name = participant_names.get(match.participant1_id, "Unknown")
            p2_name = participant_names.get(match.participant2_id, "Unknown")
            winner_name = None
            if match.winner_id:
                winner_name = participant_names.get(match.winner_id, "Unknown")
            
            matches_data.append({
                "participant1": p1_name,
                "participant2": p2_name,
                "winner": winner_name,
                "status": match.status.value.replace("_", " ").title(),
                "feedback": match.comparison_feedback[:200] + "..." if match.comparison_feedback and len(match.comparison_feedback) > 200 else match.comparison_feedback
            })
        
        # Generate visualizations as JSON for embedding
        leaderboard_fig = visualizer.create_leaderboard_chart(tournament)
        radar_fig = visualizer.create_performance_radar_chart(tournament)
        
        return templates.TemplateResponse("tournament_detail.html", {
            "request": request,
            "tournament": tournament,
            "standings": standings_data,
            "matches": matches_data,
            "leaderboard_json": leaderboard_fig.to_json(),
            "radar_json": radar_fig.to_json()
        })
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tournament ID")


@app.post("/api/tournaments", response_model=TournamentResponse)
async def create_tournament(
    request: TournamentCreateRequest, 
    background_tasks: BackgroundTasks
):
    """Create a new tournament."""
    try:
        if request.use_sample_data:
            # Generate sample data
            participants, transcripts = create_sample_data(
                num_participants=request.num_participants
            )
        else:
            # In a real implementation, this would handle uploaded data
            raise HTTPException(
                status_code=400, 
                detail="Custom data upload not implemented in demo"
            )
        
        # Create and run tournament in background
        tournament = await tournament_manager.create_and_run_tournament(
            name=request.name,
            description=request.description,
            participants=participants,
            transcripts=transcripts,
            tournament_format=request.format
        )
        
        # Prepare response
        participant_names = {p.id: p.name for p in tournament.participants}
        winner_name = None
        if tournament.winner_id:
            winner_name = participant_names.get(tournament.winner_id, "Unknown")
        
        return TournamentResponse(
            id=str(tournament.id),
            name=tournament.name,
            description=tournament.description,
            format=tournament.format.value,
            participant_count=len(tournament.participants),
            match_count=len(tournament.matches),
            completion_percentage=tournament.completion_percentage,
            is_completed=tournament.is_completed,
            winner_name=winner_name,
            created_at=tournament.created_at.isoformat(),
            started_at=tournament.started_at.isoformat() if tournament.started_at else None,
            completed_at=tournament.completed_at.isoformat() if tournament.completed_at else None
        )
        
    except Exception as e:
        logger.error(f"Error creating tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tournaments", response_model=List[TournamentResponse])
async def list_tournaments():
    """List all tournaments."""
    tournaments = tournament_manager.list_tournaments()
    result = []
    
    for tournament in tournaments:
        participant_names = {p.id: p.name for p in tournament.participants}
        winner_name = None
        if tournament.winner_id:
            winner_name = participant_names.get(tournament.winner_id, "Unknown")
        
        result.append(TournamentResponse(
            id=str(tournament.id),
            name=tournament.name,
            description=tournament.description,
            format=tournament.format.value,
            participant_count=len(tournament.participants),
            match_count=len(tournament.matches),
            completion_percentage=tournament.completion_percentage,
            is_completed=tournament.is_completed,
            winner_name=winner_name,
            created_at=tournament.created_at.isoformat(),
            started_at=tournament.started_at.isoformat() if tournament.started_at else None,
            completed_at=tournament.completed_at.isoformat() if tournament.completed_at else None
        ))
    
    return result


@app.get("/api/tournaments/{tournament_id}/standings", response_model=List[StandingsResponse])
async def get_tournament_standings(tournament_id: str):
    """Get tournament standings."""
    try:
        tournament = tournament_manager.get_tournament(UUID(tournament_id))
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        participant_names = {p.id: p.name for p in tournament.participants}
        result = []
        
        for standing in tournament.standings:
            participant_name = participant_names.get(standing.participant_id, "Unknown")
            result.append(StandingsResponse(
                participant_name=participant_name,
                rank=standing.rank,
                wins=standing.wins,
                losses=standing.losses,
                win_percentage=standing.win_percentage,
                average_score=standing.average_score,
                total_matches=standing.total_matches
            ))
        
        return result
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tournament ID")


@app.get("/api/tournaments/{tournament_id}/visualizations/{viz_type}")
async def get_visualization(tournament_id: str, viz_type: str):
    """Get tournament visualization as JSON."""
    try:
        tournament = tournament_manager.get_tournament(UUID(tournament_id))
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        if viz_type == "leaderboard":
            fig = visualizer.create_leaderboard_chart(tournament)
        elif viz_type == "radar":
            fig = visualizer.create_performance_radar_chart(tournament)
        elif viz_type == "bracket":
            fig = visualizer.create_tournament_bracket(tournament)
        elif viz_type == "distribution":
            fig = visualizer.create_score_distribution(tournament)
        elif viz_type == "insights":
            fig = visualizer.create_improvement_insights(tournament)
        elif viz_type == "dashboard":
            fig = visualizer.create_dashboard(tournament)
        else:
            raise HTTPException(status_code=400, detail="Invalid visualization type")
        
        return JSONResponse(content=json.loads(fig.to_json()))
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tournament ID")


@app.get("/create", response_class=HTMLResponse)
async def create_tournament_page(request: Request):
    """Create tournament page."""
    return templates.TemplateResponse("create_tournament.html", {
        "request": request
    })


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "AI Sales Evaluation Arena"}


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors with custom page."""
    return templates.TemplateResponse("404.html", {
        "request": request
    }, status_code=404)


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors with custom page."""
    logger.error(f"Internal server error: {exc}")
    return templates.TemplateResponse("500.html", {
        "request": request
    }, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 