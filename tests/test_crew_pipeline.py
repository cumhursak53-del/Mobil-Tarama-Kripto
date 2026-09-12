from unittest.mock import patch

from engine.crew.pipeline import run_daily_crew


def test_dry_run_no_crash():
    with patch("engine.crew.pipeline.run_crew_research", return_value=("brief", [])):
        with patch("engine.crew.pipeline._generate_architect_recipes", return_value=[]):
            with patch("engine.crew.pipeline.backtest_recipes", return_value=[]):
                with patch("engine.crew.pipeline._try_crew_ai_narrative", return_value=""):
                    out = run_daily_crew(dry_run=True, send_email=False)
    assert out["dry_run"] is True
    assert "summary" in out
