#!/usr/bin/env python3
"""
Simple test script to verify Anthropic Claude integration works.
"""

import asyncio
import os
from src.ai_sales_eval_arena.config import get_config
from src.ai_sales_eval_arena.grading import AIGrader
from src.ai_sales_eval_arena.models import Participant, Transcript


async def test_anthropic_grading():
    """Test that we can grade a simple transcript with Claude."""
    
    # Check if API key is set
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set. Please set it in your .env file or environment.")
        print("Example: export ANTHROPIC_API_KEY='your-key-here'")
        return
    
    try:
        # Load configuration
        config = get_config()
        print(f"✅ Configuration loaded. Using model: {config.anthropic_model}")
        
        # Create grader
        grader = AIGrader(config)
        print("✅ AIGrader initialized")
        
        # Create test participant and transcript
        participant = Participant(
            name="test_participant",
            skill_level="intermediate"
        )
        
        transcript = Transcript(
            participant_id=participant.id,
            content="""
            Hello! Thank you for this opportunity to present Pyroscope, our continuous profiling solution.
            
            I've researched your company and noticed you're experiencing performance issues during peak traffic.
            Pyroscope can help you identify code-level bottlenecks in real-time, reducing your infrastructure
            costs by up to 30% while improving application performance.
            
            Our continuous profiling integrates seamlessly with your existing observability stack, providing
            the missing piece between your metrics, logs, and traces. This means faster incident resolution
            and more reliable applications for your customers.
            
            Would you like to see a demo of how Pyroscope identified and helped resolve a similar performance
            issue for another company in your industry?
            """,
            filename="test_transcript.txt",
            word_count=120
        )
        
        print("✅ Test data created")
        print(f"   Participant: {participant.name}")
        print(f"   Transcript length: {len(transcript.content)} characters")
        
        # Grade the transcript
        print("\n🤖 Calling Claude API to grade the transcript...")
        grade = await grader.grade_transcript(transcript, participant)
        
        print("✅ Grading completed successfully!")
        print(f"   Overall Score: {grade.overall_score:.2f}/4.0")
        print(f"   Model Used: {grade.grader_model}")
        print(f"   Criteria Graded: {len(grade.criterion_grades)}")
        
        # Show criterion scores
        print("\n📊 Detailed Scores:")
        for criterion_grade in grade.criterion_grades:
            print(f"   {criterion_grade.criterion.value}: {criterion_grade.score:.1f}/4.0")
        
        print(f"\n💭 Overall Feedback:")
        print(f"   {grade.overall_feedback}")
        
        return grade
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return None


async def test_anthropic_comparison():
    """Test that we can compare two transcripts with Claude."""
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set.")
        return
    
    try:
        config = get_config()
        grader = AIGrader(config)
        
        # Create two test participants and transcripts
        participant_a = Participant(name="alice_amazing", skill_level="expert")
        participant_b = Participant(name="bob_basic", skill_level="beginner")
        
        transcript_a = Transcript(
            participant_id=participant_a.id,
            content="""
            Good morning! I'm excited to present Pyroscope, and I can see from your recent blog posts 
            about scaling challenges that this solution directly addresses your pain points.
            
            Your engineering team mentioned 40% of incidents take over 2 hours to resolve due to 
            performance bottlenecks. Pyroscope provides continuous, code-level profiling that pinpoints 
            exactly which functions are consuming resources, reducing MTTR by up to 70%.
            
            Unlike traditional profiling that impacts performance, our always-on solution adds less than 
            2% overhead while capturing 100% of your application's behavior. This integrates with your 
            existing Grafana stack, giving your team the observability signal they're missing.
            
            Based on your current AWS spend, we estimate 25-30% cost reduction through optimization 
            insights. Shall we schedule a technical deep-dive with your platform team next week?
            """,
            filename="alice_transcript.txt",
            word_count=150
        )
        
        transcript_b = Transcript(
            participant_id=participant_b.id,
            content="""
            Hi there. So, um, Pyroscope is a profiling tool. It helps with performance stuff.
            
            I think it could be useful for your company because, you know, most companies have 
            performance issues. Our tool shows you where the problems are in your code.
            
            It's better than other tools because it's continuous. That means it runs all the time.
            Some other tools don't do that.
            
            The price is competitive and we have good support. Do you want to try it?
            """,
            filename="bob_transcript.txt",
            word_count=80
        )
        
        print("🤖 Comparing two transcripts with Claude...")
        winner_id, feedback, metadata = await grader.compare_transcripts(
            transcript_a, participant_a, transcript_b, participant_b
        )
        
        winner_name = participant_a.name if winner_id == str(participant_a.id) else participant_b.name
        
        print("✅ Comparison completed successfully!")
        print(f"   Winner: {winner_name}")
        print(f"   Reasoning: {feedback}")
        
        return winner_id, feedback, metadata
        
    except Exception as e:
        print(f"❌ Error during comparison: {e}")
        return None


if __name__ == "__main__":
    print("🧪 Testing Anthropic Claude Integration")
    print("=" * 50)
    
    # Test individual grading
    print("\n1️⃣ Testing Individual Transcript Grading:")
    result1 = asyncio.run(test_anthropic_grading())
    
    if result1:
        print("\n2️⃣ Testing Transcript Comparison:")
        result2 = asyncio.run(test_anthropic_comparison())
        
        if result2:
            print("\n🎉 All tests passed! Anthropic integration is working correctly.")
        else:
            print("\n⚠️ Comparison test failed.")
    else:
        print("\n⚠️ Individual grading test failed.") 