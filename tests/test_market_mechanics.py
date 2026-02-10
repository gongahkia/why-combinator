
import pytest
from why_combinator.engine.scenarios import MarketSaturation

def test_market_saturation_mechanics():
    """Test market saturation reduces growth."""
    
    # 1. Start: low share, low penetration -> 1.0 modifier
    mod = MarketSaturation.calculate_growth_modifier(market_share=0.1, penetration=0.1)
    assert mod == 1.0
    
    # 2. High Share (Monopoly), low penetration
    # Share 0.8 (>0.7) -> penalty 1.0 - (0.8-0.7) = 0.9
    mod = MarketSaturation.calculate_growth_modifier(market_share=0.8, penetration=0.1)
    # Floating point check
    assert abs(mod - 0.9) < 0.0001
    
    # 3. Low Share, High Penetration (Crowded/Saturated market)
    # Pen 0.9 (>0.8) -> penalty 1.0 - (0.9-0.8)*2.0 = 1.0 - 0.2 = 0.8
    mod = MarketSaturation.calculate_growth_modifier(market_share=0.1, penetration=0.9)
    assert abs(mod - 0.8) < 0.0001
    
    # 4. Both high (worst case)
    # Pen 1.0 -> 1.0 - 0.4 = 0.6
    # Share 1.0 -> 1.0 - 0.3 = 0.7
    # Min is 0.6
    mod = MarketSaturation.calculate_growth_modifier(market_share=1.0, penetration=1.0)
    assert abs(mod - 0.6) < 0.0001
    
    # 5. Full saturation? limit check
    # If pen=1.0, wait, max(0.0, 1.0 - (0.2)*2.0) = 0.6. It doesn't go to 0.
    # What if pen > 1.0? Shouldn't happen but logic allows.
    
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))
